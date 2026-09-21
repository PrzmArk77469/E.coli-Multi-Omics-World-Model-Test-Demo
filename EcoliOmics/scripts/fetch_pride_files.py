#!/usr/bin/env python3
"""Inventory PRIDE project files and optionally download small processed results."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


csv.field_size_limit(1024 * 1024 * 1024)

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "manifests" / "pride_ecoli_projects.tsv.gz"
INVENTORY = ROOT / "manifests" / "pride_file_inventory.jsonl.gz"
SUMMARY = ROOT / "reports" / "coverage" / "pride_file_inventory_summary.json"
QUEUE_DIR = ROOT / "manifests" / "download_queue"
REPORTS = ROOT / "reports" / "downloads"
RAW = ROOT / "raw" / "proteomics" / "PRIDE"
API = "https://www.ebi.ac.uk/pride/ws/archive/v2/projects"

PROCESSED_EXTENSIONS = {
    ".mztab",
    ".mzid",
    ".tsv",
    ".csv",
    ".txt",
    ".xml",
    ".json",
    ".xlsx",
    ".zip",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def curl_base() -> list[str]:
    return [
        "curl.exe",
        "-sS",
        "-L",
        "--fail",
        "-4",
        "--http1.1",
        "--connect-timeout",
        "20",
        "--speed-time",
        "180",
        "--speed-limit",
        "1024",
        "--retry",
        "3",
        "--retry-all-errors",
        "--ssl-no-revoke",
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_with_retry(source: Path, destination: Path, attempts: int = 12) -> None:
    for attempt in range(1, attempts + 1):
        try:
            source.replace(destination)
            return
        except PermissionError:
            if attempt == attempts:
                raise
            time.sleep(min(5, 0.25 * attempt))


def download_url(value: str) -> str:
    if value.lower().startswith("ftp://"):
        return "https://" + value[6:]
    return value


def remote_content_length(url: str) -> int | None:
    completed = subprocess.run(
        curl_base() + ["--head", download_url(url)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    for line in reversed(completed.stdout.splitlines()):
        name, separator, value = line.partition(":")
        if separator and name.strip().lower() == "content-length":
            try:
                return int(value.strip())
            except ValueError:
                return None
    return None


def request_json(url: str, timeout: int = 180) -> object:
    completed = subprocess.run(
        curl_base() + [url],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return json.loads(completed.stdout)


def project_files(accession: str) -> list[dict]:
    files: list[dict] = []
    page = 0
    page_size = 100
    while True:
        url = (
            f"{API}/{quote(accession)}/files?"
            f"pageSize={page_size}&page={page}"
        )
        payload = request_json(url)
        if not isinstance(payload, list):
            raise RuntimeError(f"unexpected PRIDE response for {accession}")
        files.extend(payload)
        if len(payload) < page_size:
            break
        page += 1
        time.sleep(0.05)
    return files


def normalize_file(project_accession: str, item: dict) -> dict:
    category = item.get("fileCategory") or {}
    locations = item.get("publicFileLocations") or []
    ftp_url = ""
    for location in locations:
        value = location.get("value") or ""
        if value.startswith("ftp://"):
            ftp_url = value
            break
    filename = item.get("fileName") or ""
    extension = Path(filename).suffix.lower()
    return {
        "project_accession": project_accession,
        "file_accession": item.get("accession") or "",
        "file_name": filename,
        "extension": extension,
        "category": category.get("value") or "",
        "category_name": category.get("name") or "",
        "file_size_bytes": int(item.get("fileSizeBytes") or 0),
        "ftp_url": ftp_url,
        "publication_date": item.get("publicationDate") or "",
        "submission_date": item.get("submissionDate") or "",
        "updated_date": item.get("updatedDate") or "",
        "processed_candidate": int(
            ftp_url
            and category.get("value") in {"SEARCH", "RESULT"}
            and extension in PROCESSED_EXTENSIONS
        ),
    }


def fetch_project(accession: str) -> tuple[str, list[dict], str]:
    try:
        return accession, [normalize_file(accession, item) for item in project_files(accession)], ""
    except Exception as exc:  # noqa: BLE001
        return accession, [], str(exc)


def build_inventory(workers: int) -> list[dict]:
    if not PROJECTS.exists():
        raise SystemExit(f"missing PRIDE project manifest: {PROJECTS}")
    with gzip.open(PROJECTS, "rt", encoding="utf-8-sig", newline="") as handle:
        projects = [row["accession"] for row in csv.DictReader(handle, delimiter="\t") if row.get("accession")]

    files: list[dict] = []
    failures: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(fetch_project, accession): accession for accession in projects}
        completed_count = 0
        for future in as_completed(futures):
            accession, project_file_rows, error = future.result()
            completed_count += 1
            if error:
                failures.append({"project_accession": accession, "error": error})
            else:
                files.extend(project_file_rows)
            if completed_count % 50 == 0 or completed_count == len(projects):
                print(
                    f"PRIDE inventory: {completed_count}/{len(projects)} projects, "
                    f"{len(files)} files, {len(failures)} failures",
                    flush=True,
                )

    INVENTORY.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(INVENTORY, "wt", encoding="utf-8", newline="") as handle:
        for item in files:
            handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")

    category_counts: dict[str, dict[str, int]] = {}
    for item in files:
        category = item["category"] or "UNKNOWN"
        bucket = category_counts.setdefault(category, {"files": 0, "bytes": 0, "processed": 0})
        bucket["files"] += 1
        bucket["bytes"] += item["file_size_bytes"]
        bucket["processed"] += item["processed_candidate"]
    summary = {
        "retrieved_at": utc_now(),
        "projects_requested": len(projects),
        "projects_succeeded": len(projects) - len(failures),
        "projects_failed": len(failures),
        "files": len(files),
        "file_bytes": sum(item["file_size_bytes"] for item in files),
        "processed_candidates": sum(item["processed_candidate"] for item in files),
        "by_category": category_counts,
        "inventory": str(INVENTORY.relative_to(ROOT)),
        "inventory_bytes": INVENTORY.stat().st_size,
        "inventory_sha256": sha256_file(INVENTORY),
        "failures": failures[:200],
        "license_status": "license_unverified",
        "redistribution_status": "blocked_until_reviewed",
    }
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return files


def load_inventory() -> list[dict]:
    if not INVENTORY.exists():
        return build_inventory(6)
    with gzip.open(INVENTORY, "rt", encoding="utf-8", newline="") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_processed_queue(
    files: list[dict],
    target_files: int,
    min_file_mib: float,
    max_file_gib: float,
    budget_gib: float,
    excluded_projects: set[str],
) -> list[dict]:
    candidates = [
        item
        for item in files
        if item["processed_candidate"]
        and item["project_accession"] not in excluded_projects
        and item["file_size_bytes"] >= int(min_file_mib * 1024**2)
        and item["file_size_bytes"] <= int(max_file_gib * 1024**3)
    ]
    candidates.sort(
        key=lambda item: (
            item["file_size_bytes"],
            item["project_accession"],
            item["file_name"],
        )
    )
    selected: list[dict] = []
    projects: set[str] = set()
    total_bytes = 0
    for item in candidates:
        if item["project_accession"] in projects:
            continue
        if len(selected) >= target_files:
            break
        if total_bytes + item["file_size_bytes"] > int(budget_gib * 1024**3):
            continue
        selected.append(item)
        projects.add(item["project_accession"])
        total_bytes += item["file_size_bytes"]
    return selected


def load_excluded_projects(prefixes: list[str]) -> set[str]:
    projects: set[str] = set()
    for prefix in prefixes:
        path = QUEUE_DIR / f"{prefix}_files.tsv"
        if not path.exists():
            raise FileNotFoundError(f"missing exclusion queue: {path}")
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                projects.add(row["project_accession"])
    return projects


def write_processed_queue(selected: list[dict], prefix: str) -> Path:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    queue_path = QUEUE_DIR / f"{prefix}_files.tsv"
    fields = [
        "project_accession",
        "file_name",
        "category",
        "file_size_bytes",
        "ftp_url",
        "local_relative_path",
        "license_status",
        "redistribution_status",
        "download_status",
    ]
    with queue_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for item in selected:
            local_relative = (
                Path("raw")
                / "proteomics"
                / "PRIDE"
                / item["project_accession"]
                / item["file_name"]
            )
            writer.writerow(
                {
                    "project_accession": item["project_accession"],
                    "file_name": item["file_name"],
                    "category": item["category"],
                    "file_size_bytes": item["file_size_bytes"],
                    "ftp_url": item["ftp_url"],
                    "local_relative_path": local_relative.as_posix(),
                    "license_status": "license_unverified",
                    "redistribution_status": "blocked_until_reviewed",
                    "download_status": "pending",
                }
            )
    return queue_path


def download_one(item: dict, retries: int) -> dict:
    relative = (
        Path("raw")
        / "proteomics"
        / "PRIDE"
        / item["project_accession"]
        / item["file_name"]
    )
    destination = ROOT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")
    if part.exists() and part.stat().st_size == 0:
        part.unlink()
    elif part.exists() and not destination.exists():
        try:
            expected_remote_bytes = remote_content_length(item["ftp_url"])
            if expected_remote_bytes is not None and part.stat().st_size == expected_remote_bytes:
                replace_with_retry(part, destination)
                return {
                    **item,
                    "status": "downloaded",
                    "local_relative_path": relative.as_posix(),
                    "downloaded_bytes": destination.stat().st_size,
                    "sha256": sha256_file(destination),
                    "attempts": 0,
                    "finished_at": utc_now(),
                }
        except Exception:  # noqa: BLE001
            pass
    if (
        destination.exists()
        and destination.stat().st_size == item["file_size_bytes"]
    ):
        return {
            **item,
            "status": "skipped_size_verified",
            "local_relative_path": relative.as_posix(),
            "downloaded_bytes": 0,
            "sha256": sha256_file(destination),
            "finished_at": utc_now(),
        }
    last_error = ""
    for attempt in range(1, retries + 1):
        command = curl_base() + [
            "--continue-at",
            "-",
            "--output",
            str(part),
            download_url(item["ftp_url"]),
        ]
        try:
            subprocess.run(command, check=True, timeout=7200)
        except subprocess.CalledProcessError as exc:
            last_error = f"curl exit {exc.returncode}; partial file retained"
            if attempt < retries:
                time.sleep(min(20, 2 * attempt))
            continue
        actual = part.stat().st_size if part.exists() else 0
        if actual != item["file_size_bytes"]:
            last_error = f"size mismatch: expected {item['file_size_bytes']}, got {actual}"
            if attempt < retries:
                time.sleep(min(20, 2 * attempt))
            continue
        replace_with_retry(part, destination)
        return {
            **item,
            "status": "downloaded",
            "local_relative_path": relative.as_posix(),
            "downloaded_bytes": actual,
            "sha256": sha256_file(destination),
            "attempts": attempt,
            "finished_at": utc_now(),
        }
    return {
        **item,
        "status": "failed",
        "error": last_error,
        "downloaded_bytes": 0,
        "finished_at": utc_now(),
    }


def download_selected(selected: list[dict], workers: int, retries: int) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    status_path = REPORTS / "pride_processed_download_status.jsonl"
    summary_path = REPORTS / "pride_processed_download_summary.json"
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(download_one, item, retries): item for item in selected}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                result = {
                    **item,
                    "status": "failed",
                    "error": f"unhandled worker error: {exc}",
                    "downloaded_bytes": 0,
                    "finished_at": utc_now(),
                }
            results.append(result)
            print(f"{result['status']}: {result['project_accession']}/{result['file_name']}")
            with status_path.open("w", encoding="utf-8", newline="") as handle:
                for item in results:
                    handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
    counts: dict[str, int] = {}
    downloaded_bytes = 0
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
        downloaded_bytes += int(item.get("downloaded_bytes", 0))
    summary = {
        "finished_at": utc_now(),
        "files": len(results),
        "counts": counts,
        "downloaded_bytes": downloaded_bytes,
        "license_status": "license_unverified",
        "redistribution_status": "blocked_until_reviewed",
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--queue-prefix", default="pride_processed_batch01")
    parser.add_argument("--target-files", type=int, default=20)
    parser.add_argument("--min-file-mib", type=float, default=1.0)
    parser.add_argument("--max-file-gib", type=float, default=1.0)
    parser.add_argument("--budget-gib", type=float, default=8.0)
    parser.add_argument(
        "--exclude-prefix",
        action="append",
        default=[],
        help="exclude projects already present in an existing queue prefix",
    )
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    files = build_inventory(args.workers) if args.refresh else load_inventory()
    excluded_projects = load_excluded_projects(args.exclude_prefix)
    selected = build_processed_queue(
        files,
        args.target_files,
        args.min_file_mib,
        args.max_file_gib,
        args.budget_gib,
        excluded_projects,
    )
    queue_path = write_processed_queue(selected, args.queue_prefix)
    print(
        json.dumps(
            {
                "queue": str(queue_path.relative_to(ROOT)),
                "files": len(selected),
                "bytes": sum(item["file_size_bytes"] for item in selected),
                "excluded_queues": args.exclude_prefix,
                "excluded_projects": len(excluded_projects),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.download:
        download_selected(selected, args.workers, args.retries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

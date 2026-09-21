#!/usr/bin/env python3
"""Inventory MetaboLights studies and download small E. coli metadata files."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "manifests"
REPORTS = ROOT / "reports" / "coverage"
DOWNLOAD_REPORTS = ROOT / "reports" / "downloads"
QUEUE_DIR = ROOT / "manifests" / "download_queue"
RAW = ROOT / "raw" / "metabolomics" / "MetaboLights"
INVENTORY = MANIFESTS / "metabolights_ecoli_studies.jsonl.gz"
API = "https://www.ebi.ac.uk/metabolights/ws/studies"

ECOLI_PATTERN = re.compile(
    r"Escherichia\s+coli|E\.\s*coli|K-?12|MG1655|BW25113|W3110|BL21|"
    r"REL606|O157:H7|CFT073",
    re.IGNORECASE,
)
METADATA_TYPES = {
    "metadata_assay",
    "metadata_investigation",
    "metadata_maf",
    "metadata_sample",
    "metadata_study",
}
METADATA_NAME_PATTERN = re.compile(
    r"^(?:i|s|a)_.+\.txt$|^m_.+\.tsv$",
    re.IGNORECASE,
)
FTP_STUDY_ROOT = "https://ftp.ebi.ac.uk/pub/databases/metabolights/studies/public"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


def remote_content_length(url: str) -> int | None:
    completed = subprocess.run(
        curl_base() + ["--head", url],
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


def request_text(url: str, timeout: int = 180) -> str:
    completed = subprocess.run(
        curl_base() + [url],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return completed.stdout


def study_detail(accession: str) -> dict:
    detail = request_json(f"{API}/{quote(accession)}")
    files_payload = request_json(f"{API}/{quote(accession)}/files")
    study = detail.get("mtblsStudy") or {}
    investigation = detail.get("isaInvestigation") or {}
    studies = investigation.get("studies") or []
    study_metadata = studies[0] if studies else {}
    title = study_metadata.get("title") or investigation.get("title") or ""
    description = study_metadata.get("description") or investigation.get("description") or ""
    text = json.dumps(
        {
            "title": title,
            "description": description,
            "protocols": study_metadata.get("protocols") or [],
            "assays": study_metadata.get("assays") or [],
        },
        ensure_ascii=False,
    )
    is_ecoli = bool(ECOLI_PATTERN.search(text))
    files = []
    for item in files_payload.get("study") or []:
        if item.get("directory"):
            continue
        files.append(
            {
                "file": item.get("file") or "",
                "type": item.get("type") or "",
                "status": item.get("status") or "",
                "created_at": item.get("createdAt") or "",
            }
        )
    return {
        "accession": accession,
        "title": title,
        "description": description,
        "study_status": study.get("studyStatus"),
        "study_category": study.get("studyCategory"),
        "dataset_license": study.get("datasetLicense"),
        "dataset_license_url": study.get("datasetLicenseUrl"),
        "study_http_url": study.get("studyHttpUrl"),
        "publication_date": study_metadata.get("publicReleaseDate")
        or investigation.get("publicReleaseDate"),
        "submission_date": study_metadata.get("submissionDate")
        or investigation.get("submissionDate"),
        "publications": [
            {
                "title": item.get("title"),
                "doi": item.get("doi"),
                "pmid": item.get("pubMedID"),
            }
            for item in (study_metadata.get("publications") or [])
        ],
        "assays": [
            {
                "technology": (item.get("technologyType") or {}).get("annotationValue"),
                "platform": item.get("technologyPlatform"),
                "measurement": (item.get("measurementType") or {}).get("annotationValue"),
                "metadata_file": item.get("filename"),
            }
            for item in (study_metadata.get("assays") or [])
        ],
        "factors": [
            item.get("factorName") for item in (study_metadata.get("factors") or [])
        ],
        "is_ecoli": int(is_ecoli),
        "files": files,
    }


def fetch_one(accession: str) -> tuple[str, dict | None, str]:
    try:
        return accession, study_detail(accession), ""
    except Exception as exc:  # noqa: BLE001
        return accession, None, str(exc)


def build_inventory(workers: int) -> list[dict]:
    payload = request_json(f"{API}")
    accessions = payload.get("content") or []
    if not isinstance(accessions, list):
        raise RuntimeError("unexpected MetaboLights study list")

    matched: list[dict] = []
    failures: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(fetch_one, accession): accession for accession in accessions}
        completed_count = 0
        for future in as_completed(futures):
            accession, detail, error = future.result()
            completed_count += 1
            if error:
                failures.append({"accession": accession, "error": error})
            elif detail and detail["is_ecoli"]:
                matched.append(detail)
            if completed_count % 100 == 0 or completed_count == len(accessions):
                print(
                    f"MetaboLights: {completed_count}/{len(accessions)} studies, "
                    f"{len(matched)} E. coli candidates, {len(failures)} failures",
                    flush=True,
                )

    matched.sort(key=lambda item: item["accession"])
    INVENTORY.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(INVENTORY, "wt", encoding="utf-8", newline="") as handle:
        for item in matched:
            handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
    summary = {
        "retrieved_at": utc_now(),
        "studies_scanned": len(accessions),
        "studies_failed": len(failures),
        "ecoli_studies": len(matched),
        "ecoli_files": sum(len(item["files"]) for item in matched),
        "inventory": str(INVENTORY.relative_to(ROOT)),
        "inventory_bytes": INVENTORY.stat().st_size,
        "inventory_sha256": sha256_file(INVENTORY),
        "failures": failures[:200],
        "license_policy": "per_study_dataset_license",
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "metabolights_ecoli_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return matched


def load_inventory() -> list[dict]:
    if not INVENTORY.exists():
        return build_inventory(8)
    with gzip.open(INVENTORY, "rt", encoding="utf-8", newline="") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def metadata_type(file_name: str) -> str:
    if file_name.startswith("i_"):
        return "metadata_investigation"
    if file_name.startswith("s_"):
        return "metadata_sample"
    if file_name.startswith("a_"):
        return "metadata_assay"
    if file_name.startswith("m_"):
        return "metadata_maf"
    return "metadata"


def list_study_files(accession: str) -> list[str]:
    """Read the actual public directory instead of trusting API filenames."""
    listing = request_text(f"{FTP_STUDY_ROOT}/{quote(accession)}/")
    names = set()
    for match in re.finditer(r'<a\s+href="([^"]+)"', listing, re.IGNORECASE):
        href = html.unescape(match.group(1))
        if (
            not href
            or href.startswith(("?", "/", "#"))
            or href.endswith("/")
            or href in {".", ".."}
        ):
            continue
        file_name = unquote(href)
        if METADATA_NAME_PATTERN.fullmatch(file_name):
            names.add(file_name)
    return sorted(names)


def build_metadata_queue(studies: list[dict], workers: int) -> tuple[list[dict], list[dict]]:
    queue: list[dict] = []
    failures: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(list_study_files, study["accession"]): study
            for study in studies
        }
        for future in as_completed(futures):
            study = futures[future]
            try:
                file_names = future.result()
            except Exception as exc:  # noqa: BLE001
                failures.append({"accession": study["accession"], "error": str(exc)})
                continue
            base_url = f"{FTP_STUDY_ROOT}/{quote(study['accession'])}"
            for file_name in file_names:
                file_type = metadata_type(file_name)
                if file_type not in METADATA_TYPES:
                    continue
                queue.append(
                    {
                        "accession": study["accession"],
                        "file_name": file_name,
                        "file_type": file_type,
                        "url": f"{base_url}/{quote(file_name, safe='')}",
                        "dataset_license": study.get("dataset_license") or "",
                        "dataset_license_url": study.get("dataset_license_url") or "",
                    }
                )
    queue.sort(key=lambda item: (item["accession"], item["file_name"]))
    failures.sort(key=lambda item: item["accession"])
    return queue, failures


def write_queue(queue: list[dict], prefix: str) -> Path:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    path = QUEUE_DIR / f"{prefix}_files.tsv"
    fields = [
        "accession",
        "file_name",
        "file_type",
        "url",
        "local_relative_path",
        "dataset_license",
        "dataset_license_url",
        "license_status",
        "redistribution_status",
        "download_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for item in queue:
            relative = Path("raw") / "metabolomics" / "MetaboLights" / item["accession"] / item["file_name"]
            writer.writerow(
                {
                    **item,
                    "local_relative_path": relative.as_posix(),
                    "license_status": "per_study_terms",
                    "redistribution_status": "conditional_until_reviewed",
                    "download_status": "pending",
                }
            )
    return path


def download_one(item: dict, retries: int) -> dict:
    destination = RAW / item["accession"] / item["file_name"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")
    if part.exists() and part.stat().st_size == 0:
        part.unlink()
    elif part.exists():
        try:
            expected_remote_bytes = remote_content_length(item["url"])
            if expected_remote_bytes is not None and part.stat().st_size == expected_remote_bytes:
                replace_with_retry(part, destination)
                return {
                    **item,
                    "status": "downloaded",
                    "local_relative_path": str(destination.relative_to(ROOT)),
                    "bytes": destination.stat().st_size,
                    "sha256": sha256_file(destination),
                    "attempts": 0,
                    "finished_at": utc_now(),
                }
        except Exception:  # noqa: BLE001
            pass
    if destination.exists() and destination.stat().st_size > 0:
        return {
            **item,
            "status": "skipped_existing",
            "local_relative_path": str(destination.relative_to(ROOT)),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "finished_at": utc_now(),
        }
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            subprocess.run(
                curl_base() + ["--continue-at", "-", "--output", str(part), item["url"]],
                check=True,
                timeout=1800,
            )
        except subprocess.CalledProcessError as exc:
            last_error = f"curl exit {exc.returncode}; partial file retained"
            if attempt < retries:
                time.sleep(min(20, 2 * attempt))
            continue
        if not part.exists() or part.stat().st_size == 0:
            last_error = "empty response"
            if attempt < retries:
                time.sleep(min(20, 2 * attempt))
            continue
        replace_with_retry(part, destination)
        return {
            **item,
            "status": "downloaded",
            "local_relative_path": str(destination.relative_to(ROOT)),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "attempts": attempt,
            "finished_at": utc_now(),
        }
    return {
        **item,
        "status": "failed",
        "error": last_error,
        "bytes": 0,
        "finished_at": utc_now(),
    }


def download_queue(queue: list[dict], workers: int, retries: int) -> None:
    DOWNLOAD_REPORTS.mkdir(parents=True, exist_ok=True)
    status_path = DOWNLOAD_REPORTS / "metabolights_metadata_download_status.jsonl"
    summary_path = DOWNLOAD_REPORTS / "metabolights_metadata_download_summary.json"
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(download_one, item, retries): item for item in queue}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                result = {
                    **item,
                    "status": "failed",
                    "error": f"unhandled worker error: {exc}",
                    "bytes": 0,
                    "finished_at": utc_now(),
                }
            results.append(result)
            print(f"{result['status']}: {result['accession']}/{result['file_name']}")
            with status_path.open("w", encoding="utf-8", newline="") as handle:
                for item in results:
                    handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
    counts: dict[str, int] = {}
    total_bytes = 0
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
        total_bytes += int(item.get("bytes", 0))
    summary = {
        "finished_at": utc_now(),
        "files": len(results),
        "counts": counts,
        "total_bytes": total_bytes,
        "license_policy": "per_study_dataset_license",
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--queue-prefix", default="metabolights_ecoli_metadata")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    studies = build_inventory(args.workers) if args.refresh else load_inventory()
    queue, listing_failures = build_metadata_queue(studies, args.workers)
    queue_path = write_queue(queue, args.queue_prefix)
    listing_report = {
        "finished_at": utc_now(),
        "studies_requested": len(studies),
        "studies_with_metadata": len({item["accession"] for item in queue}),
        "studies_failed": len(listing_failures),
        "files": len(queue),
        "failures": listing_failures,
    }
    DOWNLOAD_REPORTS.mkdir(parents=True, exist_ok=True)
    (DOWNLOAD_REPORTS / "metabolights_ftp_listing_summary.json").write_text(
        json.dumps(listing_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "queue": str(queue_path.relative_to(ROOT)),
                "files": len(queue),
                "studies": len({item["accession"] for item in queue}),
                "studies_without_metadata": len(studies)
                - len({item["accession"] for item in queue}),
                "listing_failures": len(listing_failures),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.download:
        download_queue(queue, args.workers, args.retries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

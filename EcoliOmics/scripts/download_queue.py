#!/usr/bin/env python3
"""Download a file queue with resume, checksum verification and failure isolation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from download_single_resume import download as download_http


csv.field_size_limit(1024 * 1024 * 1024)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE = ROOT / "manifests" / "download_queue" / "pilot_mg1655_files.tsv"
DEFAULT_STATUS_DIR = ROOT / "reports" / "downloads"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def curl_base() -> list[str]:
    executable = shutil.which("curl.exe") or shutil.which("curl")
    if not executable:
        raise RuntimeError("curl executable not found")
    command = [
        executable,
        "-sS",
        "-L",
        "--fail",
        "-4",
        "--http1.1",
        "--connect-timeout",
        "20",
        "--max-time",
        "1800",
        "--retry",
        "3",
        "--retry-all-errors",
        "--speed-time",
        "180",
        "--speed-limit",
        "1024",
    ]
    if platform.system().lower() == "windows":
        command.append("--ssl-no-revoke")
    return command


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_destination(relative: str) -> Path:
    candidate = (ROOT / relative).resolve()
    root = ROOT.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"unsafe local path: {relative}")
    return candidate


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def verify(path: Path, expected_md5: str) -> bool:
    return path.exists() and path.stat().st_size > 0 and md5_file(path) == expected_md5.lower()


def download_one(
    item: dict,
    retries: int,
    backend: str,
    proxy: str | None,
    http_timeout: int,
) -> dict:
    destination = safe_destination(item["local_relative_path"])
    expected_md5 = item["md5"].lower()
    expected_bytes = int(item["bytes"])
    part = destination.with_suffix(destination.suffix + ".part")
    ensure_parent(destination)

    if verify(destination, expected_md5):
        return {
            **item,
            "status": "skipped_verified",
            "downloaded_bytes": 0,
            "finished_at": utc_now(),
        }

    if destination.exists():
        return {
            **item,
            "status": "failed_existing_file_mismatch",
            "error": f"existing file failed checksum: {destination}",
            "downloaded_bytes": 0,
            "finished_at": utc_now(),
        }

    if backend == "urllib":
        try:
            download_http(
                item["url"],
                destination,
                expected_bytes,
                expected_md5,
                retries,
                http_timeout,
                proxy,
            )
            return {
                **item,
                "status": "downloaded",
                "downloaded_bytes": destination.stat().st_size,
                "attempts": retries,
                "finished_at": utc_now(),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                **item,
                "status": "failed",
                "error": str(exc),
                "downloaded_bytes": 0,
                "finished_at": utc_now(),
            }

    last_error = ""
    for attempt in range(1, retries + 1):
        command = curl_base() + ["--continue-at", "-", "--output", str(part), item["url"]]
        try:
            subprocess.run(command, check=True, timeout=7200)
        except subprocess.CalledProcessError as exc:
            last_error = f"curl exit {exc.returncode}; partial file retained for resume"
            if attempt < retries:
                time.sleep(min(30, 3 * attempt))
            continue

        try:
            actual_bytes = part.stat().st_size
            actual_md5 = md5_file(part)
            if actual_bytes != expected_bytes:
                raise RuntimeError(
                    f"size mismatch: expected {expected_bytes}, got {actual_bytes}"
                )
            if actual_md5 != expected_md5:
                raise RuntimeError(
                    f"md5 mismatch: expected {expected_md5}, got {actual_md5}"
                )
            part.replace(destination)
            return {
                **item,
                "status": "downloaded",
                "downloaded_bytes": actual_bytes,
                "attempts": attempt,
                "finished_at": utc_now(),
            }
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            # A completed but corrupt transfer must restart; network failures keep
            # the partial file so curl can resume on the next attempt.
            if part.exists():
                part.unlink()
            if attempt < retries:
                time.sleep(min(30, 3 * attempt))

    return {
        **item,
        "status": "failed",
        "error": last_error,
        "downloaded_bytes": 0,
        "finished_at": utc_now(),
    }


def load_queue(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_status(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")


def output_paths(queue_path: Path, status_dir: Path) -> tuple[Path, Path]:
    stem = queue_path.stem
    return (
        status_dir / f"{stem}_status.jsonl",
        status_dir / f"{stem}_summary.json",
    )


def write_summary(items: list[dict], queue_path: Path, summary_path: Path) -> None:
    counts: dict[str, int] = {}
    bytes_by_status: dict[str, int] = {}
    for item in items:
        status = item["status"]
        counts[status] = counts.get(status, 0) + 1
        bytes_by_status[status] = bytes_by_status.get(status, 0) + int(item.get("downloaded_bytes", 0))
    summary = {
        "finished_at": utc_now(),
        "queue": str(queue_path.relative_to(ROOT)),
        "files": len(items),
        "counts": counts,
        "downloaded_bytes_by_status": bytes_by_status,
        "downloaded_bytes": sum(bytes_by_status.values()),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--backend",
        choices=("curl", "urllib"),
        default="curl",
        help="HTTP transport; use urllib with --proxy when curl cannot resume",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="HTTP(S) proxy URL for the urllib backend",
    )
    parser.add_argument("--http-timeout", type=int, default=120)
    parser.add_argument("--status-dir", type=Path, default=DEFAULT_STATUS_DIR)
    parser.add_argument("--min-free-gib", type=float, default=10.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    queue_path = args.queue.resolve()
    if not queue_path.exists():
        raise SystemExit(f"missing download queue: {queue_path}")
    queue = load_queue(queue_path)
    queue_bytes = sum(int(item["bytes"]) for item in queue)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "queue": str(queue_path),
                    "files": len(queue),
                    "bytes": queue_bytes,
                    "destinations": [item["local_relative_path"] for item in queue],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    free_bytes = shutil.disk_usage(ROOT).free
    required_bytes = queue_bytes + int(args.min_free_gib * 1024**3)
    if free_bytes < required_bytes:
        raise SystemExit(
            "insufficient free disk: "
            f"{free_bytes / 1024**3:.2f} GiB free, "
            f"{required_bytes / 1024**3:.2f} GiB required including reserve"
        )

    status_jsonl, summary_json = output_paths(queue_path, args.status_dir.resolve())
    results: list[dict] = []
    failures = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                download_one,
                item,
                args.retries,
                args.backend,
                args.proxy,
                args.http_timeout,
            ): item
            for item in queue
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            status = result["status"]
            print(
                f"{status}: {result['run_accession']} {result['local_relative_path']}",
                flush=True,
            )
            write_status(status_jsonl, results)
            if status.startswith("failed"):
                failures += 1

    write_summary(results, queue_path, summary_json)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Summarize queue expectations, local file presence and download statuses."""

from __future__ import annotations

import csv
import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


csv.field_size_limit(1024 * 1024 * 1024)

ROOT = Path(__file__).resolve().parents[1]
QUEUE_DIR = ROOT / "manifests" / "download_queue"
REPORT_DIR = ROOT / "reports" / "downloads"
COVERAGE_DIR = ROOT / "reports" / "coverage"

QUEUES = {
    "core_mg1655_batch01": "ENA MG1655 sequencing",
    "core_mg1655_batch02": "ENA MG1655 sequencing",
    "core_mg1655_translatomics01": "ENA MG1655 translatomics",
    "pride_processed_batch01": "PRIDE processed proteomics",
    "pride_processed_batch02": "PRIDE processed proteomics",
    "metabolights_ecoli_metadata": "MetaboLights metadata",
}

STATUS_OVERRIDES = {
    "pride_processed_batch01": REPORT_DIR / "pride_processed_download_status.jsonl",
    "pride_processed_batch02": REPORT_DIR / "pride_processed_download_status.jsonl",
    "metabolights_ecoli_metadata": REPORT_DIR / "metabolights_metadata_download_status.jsonl",
}

STATUS_ARCHIVE_LOST = {
    # The original PRIDE adapter reused one status file for both batches.
    "pride_processed_batch01",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_status(path: Path) -> Counter:
    counts: Counter = Counter()
    if not path.exists():
        return counts
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                counts["status_json_invalid"] += 1
                continue
            counts[item.get("status") or "unknown"] += 1
    return counts


def queue_summary(prefix: str, description: str) -> dict:
    path = QUEUE_DIR / f"{prefix}_files.tsv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    expected_bytes = 0
    present_bytes = 0
    complete_files = 0
    missing_files = 0
    zero_byte_files = 0
    mismatched_files = 0
    local_paths: set[str] = set()
    studies: set[str] = set()
    runs: set[str] = set()
    omics: Counter = Counter()

    for row in rows:
        relative = row.get("local_relative_path") or ""
        if relative:
            local_paths.add(relative)
        study = row.get("study_accession") or row.get("accession") or row.get(
            "project_accession"
        )
        if study:
            studies.add(study)
        run = row.get("run_accession")
        if run:
            runs.add(run)
        omics[row.get("omics_type") or row.get("file_type") or row.get("category") or "unknown"] += 1

        expected_value = row.get("bytes") or row.get("file_size_bytes") or "0"
        try:
            expected = int(expected_value)
        except ValueError:
            expected = 0
        expected_bytes += expected

        if not relative:
            continue
        local_path = ROOT / relative
        if not local_path.exists():
            missing_files += 1
            continue
        actual = local_path.stat().st_size
        present_bytes += actual
        if actual == 0:
            zero_byte_files += 1
        elif expected and actual != expected:
            mismatched_files += 1
        else:
            complete_files += 1

    if prefix in STATUS_ARCHIVE_LOST:
        status_counts = Counter({"size_verified": complete_files})
        status_note = (
            "Original status file was overwritten by a later PRIDE batch; "
            "counts are derived from current local size verification."
        )
    else:
        status_path = STATUS_OVERRIDES.get(prefix, REPORT_DIR / f"{prefix}_files_status.jsonl")
        status_counts = read_status(status_path)
        status_note = ""
    return {
        "prefix": prefix,
        "description": description,
        "queue": str(path.relative_to(ROOT)),
        "files_expected": len(rows),
        "bytes_expected": expected_bytes,
        "files_present_and_complete": complete_files,
        "bytes_present": present_bytes,
        "files_missing": missing_files,
        "files_zero_byte": zero_byte_files,
        "files_size_mismatch": mismatched_files,
        "unique_runs": len(runs),
        "unique_studies": len(studies),
        "omics_file_counts": dict(sorted(omics.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "status_note": status_note,
    }


def load_json_if_present(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def regulondb_normalized_summary() -> dict:
    root = ROOT / "reference" / "RegulonDB" / "current" / "normalized"
    files = list(root.rglob("*.json.gz"))
    rows = 0
    rows_by_type: Counter = Counter()
    invalid_files = 0
    total_bytes = 0
    for path in files:
        total_bytes += path.stat().st_size
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
            count = int(payload.get("row_count") or 0)
            rows += count
            rows_by_type[payload.get("dataset_type") or "unknown"] += count
        except Exception:  # noqa: BLE001
            invalid_files += 1
    return {
        "normalized_files": len(files),
        "normalized_bytes": total_bytes,
        "normalized_rows": rows,
        "rows_by_type": dict(sorted(rows_by_type.items())),
        "invalid_files": invalid_files,
    }


def tree_summary(root: Path) -> dict:
    files = [path for path in root.rglob("*") if path.is_file()]
    by_top: dict[str, dict[str, int]] = {}
    for path in files:
        relative = path.relative_to(root)
        top = relative.parts[0] if relative.parts else "root"
        bucket = by_top.setdefault(top, {"files": 0, "bytes": 0})
        bucket["files"] += 1
        bucket["bytes"] += path.stat().st_size
    return {
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "by_top_level": dict(sorted(by_top.items())),
    }


def main() -> int:
    summaries = [queue_summary(prefix, description) for prefix, description in QUEUES.items()]
    seen_paths: set[str] = set()
    raw_files = 0
    raw_bytes = 0
    for queue in QUEUES:
        path = QUEUE_DIR / f"{queue}_files.tsv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                relative = row.get("local_relative_path") or ""
                if not relative or relative in seen_paths:
                    continue
                seen_paths.add(relative)
                local_path = ROOT / relative
                if local_path.exists():
                    raw_files += 1
                    raw_bytes += local_path.stat().st_size

    report = {
        "generated_at": utc_now(),
        "queues": summaries,
        "unique_downloaded_files_across_selected_queues": raw_files,
        "unique_downloaded_bytes_across_selected_queues": raw_bytes,
        "supplemental": {
            "metabolomics_workbench": load_json_if_present(
                REPORT_DIR / "metabolomics_workbench_download_summary.json"
            ),
            "regulondb": regulondb_normalized_summary(),
        },
        "local_tree": {
            "raw": tree_summary(ROOT / "raw"),
            "reference": tree_summary(ROOT / "reference"),
            "processed": tree_summary(ROOT / "processed"),
        },
        "verification_note": (
            "This report verifies queue presence and size. ENA files additionally carry "
            "MD5 values and can be rechecked with download_queue.py."
        ),
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    COVERAGE_DIR.mkdir(parents=True, exist_ok=True)
    json_path = COVERAGE_DIR / "download_inventory.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tsv_path = COVERAGE_DIR / "download_inventory.tsv"
    fields = [
        "prefix",
        "description",
        "files_expected",
        "files_present_and_complete",
        "files_missing",
        "bytes_expected",
        "bytes_present",
        "unique_runs",
        "unique_studies",
    ]
    with tsv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for item in summaries:
            writer.writerow({field: item.get(field, "") for field in fields})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

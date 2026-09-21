#!/usr/bin/env python3
"""Select a small, diverse MG1655 pilot download set."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


csv.field_size_limit(1024 * 1024 * 1024)

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "manifests" / "ena_mg1655_files.tsv.gz"
QUEUE_DIR = ROOT / "manifests" / "download_queue"
REPORTS = ROOT / "reports" / "coverage"

STRATEGY_LIMITS = {
    "RNA-Seq": 10,
    "ChIP-Seq": 6,
    "Tn-Seq": 6,
    "Bisulfite-Seq": 4,
    "RIP-Seq": 3,
    "SELEX": 3,
    "MNase-Seq": 2,
    "ncRNA-Seq": 2,
    "ssRNA-seq": 2,
}

OMICS_MAP = {
    "RNA-Seq": "transcriptomics",
    "ssRNA-seq": "transcriptomics",
    "ncRNA-Seq": "transcriptomics",
    "ChIP-Seq": "regulomics",
    "RIP-Seq": "regulomics",
    "SELEX": "regulomics",
    "MNase-Seq": "regulomics",
    "Tn-Seq": "functional_genomics",
    "Bisulfite-Seq": "methylomics",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def split_values(value: str | None) -> list[str]:
    return [item for item in (value or "").split(";") if item]


def normalize_url(value: str) -> str:
    if "://" in value:
        return value
    return "https://" + value


def parse_int(value: str | None) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def select_rows(input_path: Path, budget_bytes: int, target_runs: int) -> list[dict]:
    candidates: dict[str, list[dict]] = defaultdict(list)
    with gzip.open(input_path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            strategy = row.get("library_strategy") or ""
            if strategy not in STRATEGY_LIMITS:
                continue
            urls = split_values(row.get("fastq_ftp"))
            md5s = split_values(row.get("fastq_md5"))
            sizes = [parse_int(item) for item in split_values(row.get("fastq_bytes"))]
            if not urls or len(urls) != len(md5s) or len(urls) != len(sizes):
                continue
            total_bytes = sum(sizes)
            if total_bytes < 20 * 1024 * 1024 or total_bytes > 4 * 1024 * 1024 * 1024:
                continue
            if parse_int(row.get("read_count")) < 100_000:
                continue
            if parse_int(row.get("base_count")) < 10_000_000:
                continue
            candidates[strategy].append(
                {
                    "run_accession": row["run_accession"],
                    "study_accession": row.get("study_accession", ""),
                    "sample_accession": row.get("sample_accession", ""),
                    "scientific_name": row.get("scientific_name", ""),
                    "library_strategy": strategy,
                    "omics_type": OMICS_MAP[strategy],
                    "total_bytes": total_bytes,
                    "read_count": parse_int(row.get("read_count")),
                    "base_count": parse_int(row.get("base_count")),
                    "urls": urls,
                    "md5s": md5s,
                    "sizes": sizes,
                }
            )

    for strategy in candidates:
        candidates[strategy].sort(key=lambda item: (item["total_bytes"], item["run_accession"]))

    selected: list[dict] = []
    selected_runs: set[str] = set()
    study_counts: dict[str, int] = defaultdict(int)
    total_bytes = 0

    def try_select(item: dict) -> bool:
        nonlocal total_bytes
        if item["run_accession"] in selected_runs:
            return False
        if study_counts[item["study_accession"]] >= 2:
            return False
        projected = total_bytes + item["total_bytes"]
        if projected > budget_bytes:
            return False
        if len(selected) >= target_runs:
            return False
        selected.append(item)
        selected_runs.add(item["run_accession"])
        study_counts[item["study_accession"]] += 1
        total_bytes = projected
        return True

    strategy_names = sorted(
        candidates,
        key=lambda name: (STRATEGY_LIMITS[name] / max(len(candidates[name]), 1)),
        reverse=True,
    )
    for strategy in strategy_names:
        for item in candidates[strategy][: STRATEGY_LIMITS[strategy]]:
            try_select(item)

    if len(selected) < target_runs:
        remaining = [
            item
            for strategy in candidates
            for item in candidates[strategy]
            if item["run_accession"] not in selected_runs
        ]
        remaining.sort(key=lambda item: (item["total_bytes"], item["omics_type"]))
        for item in remaining:
            try_select(item)
            if len(selected) >= target_runs:
                break

    selected.sort(key=lambda item: (item["omics_type"], item["total_bytes"], item["run_accession"]))
    return selected


def write_outputs(selected: list[dict], prefix: str) -> None:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    runs_path = QUEUE_DIR / f"{prefix}_runs.tsv"
    files_path = QUEUE_DIR / f"{prefix}_files.tsv"
    run_fields = [
        "selection_rank",
        "run_accession",
        "study_accession",
        "sample_accession",
        "scientific_name",
        "library_strategy",
        "omics_type",
        "fastq_bytes",
        "read_count",
        "base_count",
        "selection_reason",
        "license_tag",
        "download_status",
    ]
    file_fields = [
        "run_accession",
        "study_accession",
        "omics_type",
        "url",
        "md5",
        "bytes",
        "local_relative_path",
        "license_tag",
        "download_status",
    ]
    with runs_path.open("w", encoding="utf-8", newline="") as runs_handle, files_path.open(
        "w", encoding="utf-8", newline=""
    ) as files_handle:
        runs_writer = csv.DictWriter(runs_handle, fieldnames=run_fields, delimiter="\t")
        files_writer = csv.DictWriter(files_handle, fieldnames=file_fields, delimiter="\t")
        runs_writer.writeheader()
        files_writer.writeheader()
        for rank, item in enumerate(selected, start=1):
            runs_writer.writerow(
                {
                    "selection_rank": rank,
                    "run_accession": item["run_accession"],
                    "study_accession": item["study_accession"],
                    "sample_accession": item["sample_accession"],
                    "scientific_name": item["scientific_name"],
                    "library_strategy": item["library_strategy"],
                    "omics_type": item["omics_type"],
                    "fastq_bytes": item["total_bytes"],
                    "read_count": item["read_count"],
                    "base_count": item["base_count"],
                    "selection_reason": "pilot_pipeline_smoke_test",
                    "license_tag": "download_only",
                    "download_status": "pending",
                }
            )
            for url, md5, size in zip(item["urls"], item["md5s"], item["sizes"]):
                filename = Path(urlparse(normalize_url(url)).path).name
                local_relative = (
                    Path("raw")
                    / "sequencing"
                    / "MG1655"
                    / item["run_accession"]
                    / filename
                )
                files_writer.writerow(
                    {
                        "run_accession": item["run_accession"],
                        "study_accession": item["study_accession"],
                        "omics_type": item["omics_type"],
                        "url": normalize_url(url),
                        "md5": md5,
                        "bytes": size,
                        "local_relative_path": local_relative.as_posix(),
                        "license_tag": "download_only",
                        "download_status": "pending",
                    }
                )

    summary = {
        "selected_at": utc_now(),
        "selection_reason": "pilot_pipeline_smoke_test",
        "runs": len(selected),
        "files": sum(len(item["urls"]) for item in selected),
        "fastq_bytes": sum(item["total_bytes"] for item in selected),
        "studies": len({item["study_accession"] for item in selected}),
        "by_strategy": {
            strategy: {
                "runs": sum(item["library_strategy"] == strategy for item in selected),
                "fastq_bytes": sum(
                    item["total_bytes"] for item in selected if item["library_strategy"] == strategy
                ),
            }
            for strategy in sorted({item["library_strategy"] for item in selected})
        },
        "runs_manifest": str(runs_path.relative_to(ROOT)),
        "files_manifest": str(files_path.relative_to(ROOT)),
        "note": "Pilot data is for pipeline validation, not the scientific core matrix.",
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{prefix}_selection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget-gib", type=float, default=20.0)
    parser.add_argument("--target-runs", type=int, default=36)
    parser.add_argument("--prefix", default="pilot_mg1655")
    args = parser.parse_args()
    if not INPUT.exists():
        raise SystemExit(f"missing file manifest: {INPUT}")
    selected = select_rows(INPUT, int(args.budget_gib * 1024**3), args.target_runs)
    write_outputs(selected, args.prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a conservative, layered download queue from the L0 SQLite catalog."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


csv.field_size_limit(1024 * 1024 * 1024)

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "manifests" / "ecoli_catalog.sqlite"
QUEUE_DIR = ROOT / "manifests" / "download_queue"
REPORT_DIR = ROOT / "reports" / "downloads"

DEFAULT_CAPS = {
    "transcriptomics": 15,
    "regulomics": 12,
    "functional_genomics": 8,
    "translatomics": 5,
    "methylomics": 4,
    "chromatin_accessibility": 3,
    "structural_genomics": 2,
    "genomics": 5,
}

STRATEGY_CAPS = {
    "RNA-Seq": 8,
    "ssRNA-seq": 3,
    "ncRNA-Seq": 3,
    "ChIP-Seq": 7,
    "RIP-Seq": 3,
    "SELEX": 2,
    "MNase-Seq": 2,
    "Tn-Seq": 7,
    "Bisulfite-Seq": 3,
    "MeDIP-Seq": 2,
    "ATAC-seq": 2,
    "Hi-C": 2,
    "WGS": 3,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_caps(values: list[str]) -> dict[str, int]:
    if not values:
        return DEFAULT_CAPS
    caps: dict[str, int] = {}
    for value in values:
        name, separator, count = value.partition("=")
        if not separator or not name or not count:
            raise ValueError(f"invalid cap: {value}; expected omics_type=N")
        caps[name] = int(count)
    return caps


def load_candidates(
    connection: sqlite3.Connection,
    strain: str,
    min_confidence: float,
) -> list[dict]:
    query = """
        SELECT
            r.run_accession,
            r.study_accession,
            r.sample_accession,
            r.scientific_name,
            r.strain_guess,
            r.data_tier,
            r.library_strategy,
            r.library_source,
            r.omics_type,
            r.omics_priority,
            r.omics_confidence,
            r.needs_manual_review,
            r.read_count,
            r.base_count,
            r.fastq_bytes,
            f.file_id,
            f.source_url,
            f.fastq_md5,
            f.file_bytes,
            f.local_relative_path
        FROM runs AS r
        JOIN files AS f ON f.run_accession = r.run_accession
        WHERE r.strain_guess = ?
          AND r.omics_confidence >= ?
          AND r.needs_manual_review = 0
          AND r.omics_type IN ({})
          AND f.download_eligible = 1
          AND f.file_bytes > 0
        ORDER BY r.omics_priority DESC, r.omics_confidence DESC, f.file_bytes, f.file_id
    """.format(",".join("?" for _ in DEFAULT_CAPS))
    params = [strain, min_confidence, *DEFAULT_CAPS]

    runs: dict[str, dict] = {}
    for row in connection.execute(query, params):
        (
            run_accession,
            study_accession,
            sample_accession,
            scientific_name,
            strain_guess,
            data_tier,
            strategy,
            source,
            omics_type,
            priority,
            confidence,
            needs_review,
            read_count,
            base_count,
            fastq_bytes,
            file_id,
            source_url,
            md5,
            file_bytes,
            local_relative_path,
        ) = row
        run = runs.setdefault(
            run_accession,
            {
                "run_accession": run_accession,
                "study_accession": study_accession,
                "sample_accession": sample_accession,
                "scientific_name": scientific_name,
                "strain_guess": strain_guess,
                "data_tier": data_tier,
                "library_strategy": strategy,
                "library_source": source,
                "omics_type": omics_type,
                "omics_priority": priority,
                "omics_confidence": confidence,
                "needs_manual_review": needs_review,
                "read_count": read_count,
                "base_count": base_count,
                "fastq_bytes": fastq_bytes,
                "files": [],
            },
        )
        run["files"].append(
            {
                "file_id": file_id,
                "source_url": source_url,
                "md5": md5,
                "file_bytes": file_bytes,
                "local_relative_path": local_relative_path,
            }
        )

    eligible: list[dict] = []
    for run in runs.values():
        total_bytes = sum(item["file_bytes"] for item in run["files"])
        if total_bytes != run["fastq_bytes"]:
            continue
        if total_bytes < 20 * 1024 * 1024 or total_bytes > 4 * 1024**3:
            continue
        if run["read_count"] < 100_000 or run["base_count"] < 10_000_000:
            continue
        run["total_bytes"] = total_bytes
        eligible.append(run)
    return eligible


def select_queue(
    candidates: list[dict],
    budget_bytes: int,
    target_runs: int,
    caps: dict[str, int],
    strategy_caps: dict[str, int],
) -> list[dict]:
    candidates.sort(
        key=lambda item: (
            -item["omics_priority"],
            item["total_bytes"],
            item["run_accession"],
        )
    )
    selected: list[dict] = []
    selected_runs: set[str] = set()
    omics_counts: dict[str, int] = defaultdict(int)
    strategy_counts: dict[str, int] = defaultdict(int)
    study_counts: dict[str, int] = defaultdict(int)
    total_bytes = 0

    def can_take(item: dict) -> bool:
        return (
            item["run_accession"] not in selected_runs
            and omics_counts[item["omics_type"]] < caps.get(item["omics_type"], 0)
            and strategy_counts[item["library_strategy"]]
            < strategy_caps.get(item["library_strategy"], 2)
            and study_counts[item["study_accession"]] < 2
            and len(selected) < target_runs
            and total_bytes + item["total_bytes"] <= budget_bytes
        )

    # Round-robin by omics type prevents one abundant assay from filling the batch.
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in candidates:
        groups[item["omics_type"]].append(item)
    omics_order = sorted(
        groups,
        key=lambda name: (-max(item["omics_priority"] for item in groups[name]), name),
    )
    progress = True
    while progress and len(selected) < target_runs:
        progress = False
        for omics_type in omics_order:
            for item in groups[omics_type]:
                if can_take(item):
                    selected.append(item)
                    selected_runs.add(item["run_accession"])
                    omics_counts[omics_type] += 1
                    strategy_counts[item["library_strategy"]] += 1
                    study_counts[item["study_accession"]] += 1
                    total_bytes += item["total_bytes"]
                    progress = True
                    break

    selected.sort(
        key=lambda item: (
            item["omics_type"],
            item["library_strategy"],
            item["total_bytes"],
            item["run_accession"],
        )
    )
    return selected


def load_exclusions(prefixes: list[str]) -> dict[str, set[str]]:
    exclusions = {"runs": set(), "urls": set(), "local_paths": set()}
    for prefix in prefixes:
        path = QUEUE_DIR / f"{prefix}_files.tsv"
        if not path.exists():
            raise FileNotFoundError(f"missing exclusion queue: {path}")
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                exclusions["runs"].add(row["run_accession"])
                exclusions["urls"].add(row["url"])
                exclusions["local_paths"].add(row["local_relative_path"])
    return exclusions


def apply_exclusions(candidates: list[dict], exclusions: dict[str, set[str]]) -> list[dict]:
    filtered: list[dict] = []
    for run in candidates:
        if run["run_accession"] in exclusions["runs"]:
            continue
        kept_files = [
            item
            for item in run["files"]
            if item["source_url"] not in exclusions["urls"]
            and item["local_relative_path"] not in exclusions["local_paths"]
        ]
        if not kept_files:
            continue
        total_bytes = sum(item["file_bytes"] for item in kept_files)
        if total_bytes != run["fastq_bytes"]:
            continue
        if total_bytes < 20 * 1024 * 1024 or total_bytes > 4 * 1024**3:
            continue
        updated = dict(run)
        updated["files"] = kept_files
        updated["total_bytes"] = total_bytes
        filtered.append(updated)
    return filtered


def write_outputs(
    selected: list[dict],
    prefix: str,
    strain: str,
    exclusion_prefixes: list[str],
    excluded_candidates: int,
) -> None:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    runs_path = QUEUE_DIR / f"{prefix}_runs.tsv"
    files_path = QUEUE_DIR / f"{prefix}_files.tsv"
    run_fields = [
        "selection_rank",
        "run_accession",
        "study_accession",
        "sample_accession",
        "scientific_name",
        "strain_guess",
        "data_tier",
        "library_strategy",
        "library_source",
        "omics_type",
        "omics_confidence",
        "needs_manual_review",
        "fastq_bytes",
        "read_count",
        "base_count",
        "selection_reason",
        "license_status",
        "redistribution_status",
        "download_status",
    ]
    file_fields = [
        "run_accession",
        "study_accession",
        "strain_guess",
        "data_tier",
        "omics_type",
        "url",
        "md5",
        "bytes",
        "local_relative_path",
        "license_status",
        "redistribution_status",
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
                    "strain_guess": item["strain_guess"],
                    "data_tier": item["data_tier"],
                    "library_strategy": item["library_strategy"],
                    "library_source": item["library_source"],
                    "omics_type": item["omics_type"],
                    "omics_confidence": f"{item['omics_confidence']:.3f}",
                    "needs_manual_review": item["needs_manual_review"],
                    "fastq_bytes": item["total_bytes"],
                    "read_count": item["read_count"],
                    "base_count": item["base_count"],
                    "selection_reason": "local_core_analysis_candidate_pending_study_terms",
                    "license_status": "license_unverified",
                    "redistribution_status": "blocked_until_reviewed",
                    "download_status": "pending",
                }
            )
            for file_item in item["files"]:
                files_writer.writerow(
                    {
                        "run_accession": item["run_accession"],
                        "study_accession": item["study_accession"],
                        "strain_guess": item["strain_guess"],
                        "data_tier": item["data_tier"],
                        "omics_type": item["omics_type"],
                        "url": file_item["source_url"],
                        "md5": file_item["md5"],
                        "bytes": file_item["file_bytes"],
                        "local_relative_path": file_item["local_relative_path"],
                        "license_status": "license_unverified",
                        "redistribution_status": "blocked_until_reviewed",
                        "download_status": "pending",
                    }
                )

    summary = {
        "built_at": utc_now(),
        "prefix": prefix,
        "strain": strain,
        "runs": len(selected),
        "files": sum(len(item["files"]) for item in selected),
        "fastq_bytes": sum(item["total_bytes"] for item in selected),
        "studies": len({item["study_accession"] for item in selected}),
        "by_omics_type": {
            name: {
                "runs": sum(item["omics_type"] == name for item in selected),
                "fastq_bytes": sum(
                    item["total_bytes"] for item in selected if item["omics_type"] == name
                ),
            }
            for name in sorted({item["omics_type"] for item in selected})
        },
        "by_strategy": {
            name: sum(item["library_strategy"] == name for item in selected)
            for name in sorted({item["library_strategy"] for item in selected})
        },
        "runs_manifest": str(runs_path.relative_to(ROOT)),
        "files_manifest": str(files_path.relative_to(ROOT)),
        "excluded_queues": exclusion_prefixes,
        "excluded_candidates": excluded_candidates,
        "license_note": (
            "Approved only for local pipeline development. Redistribution remains "
            "blocked until each study's terms are reviewed."
        ),
    }
    (REPORT_DIR / f"{prefix}_selection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--strain", default="MG1655")
    parser.add_argument("--prefix", default="core_mg1655_batch01")
    parser.add_argument("--budget-gib", type=float, default=12.0)
    parser.add_argument("--target-runs", type=int, default=60)
    parser.add_argument("--min-confidence", type=float, default=0.8)
    parser.add_argument(
        "--exclude-prefix",
        action="append",
        default=[],
        help="exclude all runs already present in an existing queue prefix",
    )
    parser.add_argument(
        "--cap",
        action="append",
        default=[],
        help="override an omics cap, e.g. --cap transcriptomics=20",
    )
    parser.add_argument(
        "--strategy-cap",
        action="append",
        default=[],
        help="override a library-strategy cap, e.g. --strategy-cap OTHER=8",
    )
    parser.add_argument(
        "--omics",
        action="append",
        default=[],
        help="include only the named omics type; repeat for more than one",
    )
    args = parser.parse_args()
    if not args.db.exists():
        raise SystemExit(f"missing catalog database: {args.db}")

    caps = parse_caps(args.cap)
    strategy_caps = dict(STRATEGY_CAPS)
    if args.strategy_cap:
        strategy_caps.update(parse_caps(args.strategy_cap))
    connection = sqlite3.connect(args.db)
    try:
        candidates = load_candidates(connection, args.strain, args.min_confidence)
    finally:
        connection.close()
    exclusions = load_exclusions(args.exclude_prefix)
    if args.omics:
        included_omics = set(args.omics)
        candidates = [
            candidate for candidate in candidates if candidate["omics_type"] in included_omics
        ]
    original_candidate_count = len(candidates)
    if args.exclude_prefix:
        candidates = apply_exclusions(candidates, exclusions)
    selected = select_queue(
        candidates,
        int(args.budget_gib * 1024**3),
        args.target_runs,
        caps,
        strategy_caps,
    )
    if not selected:
        raise SystemExit("no eligible runs found")
    write_outputs(
        selected,
        args.prefix,
        args.strain,
        args.exclude_prefix,
        original_candidate_count - len(candidates),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

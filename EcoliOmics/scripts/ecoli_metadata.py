#!/usr/bin/env python3
"""Metadata-first collectors for the EcoliOmics data lake.

The script intentionally uses only the Python standard library and the system
curl executable. It writes compressed manifests and small JSON summaries.
"""

from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "manifests"
REPORTS = ROOT / "reports" / "coverage"
QUERY_SNAPSHOTS = ROOT / "registry" / "query_snapshots"
TMP = ROOT / "tmp" / "downloads"

ENA_FIELDS = [
    "run_accession",
    "study_accession",
    "sample_accession",
    "tax_id",
    "scientific_name",
    "library_strategy",
    "library_source",
    "fastq_bytes",
    "read_count",
    "base_count",
]
ENA_FILE_FIELDS = ENA_FIELDS + [
    "fastq_ftp",
    "fastq_md5",
]
ENA_CONTEXT_FIELDS = ENA_FILE_FIELDS + [
    "study_title",
    "experiment_title",
    "sample_title",
    "library_construction_protocol",
    "instrument_platform",
    "instrument_model",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_dirs() -> None:
    for path in (MANIFESTS, REPORTS, QUERY_SNAPSHOTS, TMP):
        path.mkdir(parents=True, exist_ok=True)


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
        "--speed-time",
        "120",
        "--speed-limit",
        "1024",
        "--retry",
        "5",
        "--retry-all-errors",
    ]
    if platform.system().lower() == "windows":
        command.append("--ssl-no-revoke")
    return command


def run_curl_text(args: Iterable[str], timeout: int = 180) -> str:
    command = curl_base() + list(args)
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return completed.stdout


def run_curl_to_file(args: Iterable[str], output: Path, timeout: int = 3600) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    part = output.with_suffix(output.suffix + ".part")
    if part.exists():
        part.unlink()
    command = curl_base() + list(args) + ["--output", str(part)]
    subprocess.run(command, check=True, timeout=timeout)
    part.replace(output)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_semicolon_ints(value: str | None) -> list[int]:
    if not value:
        return []
    result: list[int] = []
    for item in value.split(";"):
        item = item.strip()
        if not item:
            continue
        try:
            result.append(int(item))
        except ValueError:
            continue
    return result


def gzip_tsv(input_path: Path, output_path: Path, header: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open("r", encoding="utf-8-sig", newline="") as source, gzip.open(
        output_path, "wt", encoding="utf-8", newline=""
    ) as target:
        reader = csv.DictReader(source, delimiter="\t")
        writer = csv.DictWriter(target, fieldnames=header, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in reader:
            writer.writerow(row)


def summarize_ena(input_path: Path, prefix: str) -> dict:
    strategy = collections.defaultdict(lambda: {"runs": 0, "studies": set(), "bytes": 0, "bases": 0})
    source = collections.defaultdict(lambda: {"runs": 0, "studies": set(), "bytes": 0, "bases": 0})
    scientific_names = collections.defaultdict(lambda: {"runs": 0, "bytes": 0})
    studies = collections.defaultdict(
        lambda: {"runs": 0, "bytes": 0, "bases": 0, "strategies": set(), "scientific_names": set()}
    )
    totals = {
        "rows": 0,
        "unique_studies": 0,
        "fastq_bytes": 0,
        "read_count": 0,
        "base_count": 0,
        "rows_with_fastq_bytes": 0,
        "rows_missing_fastq_bytes": 0,
        "mg1655_rows": 0,
        "mg1655_fastq_bytes": 0,
    }
    all_studies: set[str] = set()
    mg1655_path = MANIFESTS / f"{prefix}_mg1655_runs.tsv.gz"

    with gzip.open(input_path, "rt", encoding="utf-8-sig", newline="") as source_handle, gzip.open(
        mg1655_path, "wt", encoding="utf-8", newline=""
    ) as mg1655_handle:
        reader = csv.DictReader(source_handle, delimiter="\t")
        if not reader.fieldnames:
            raise RuntimeError(f"missing header in {input_path}")
        mg1655_writer = csv.DictWriter(
            mg1655_handle, fieldnames=reader.fieldnames, delimiter="\t", extrasaction="ignore"
        )
        mg1655_writer.writeheader()

        for row in reader:
            totals["rows"] += 1
            study = row.get("study_accession") or ""
            strategy_name = row.get("library_strategy") or "MISSING"
            source_name = row.get("library_source") or "MISSING"
            scientific_name = row.get("scientific_name") or "MISSING"
            bytes_value = sum(parse_semicolon_ints(row.get("fastq_bytes")))
            read_count = int((row.get("read_count") or "0").split(";")[0] or 0)
            base_count = int((row.get("base_count") or "0").split(";")[0] or 0)
            has_bytes = bytes_value > 0

            all_studies.add(study)
            totals["fastq_bytes"] += bytes_value
            totals["read_count"] += read_count
            totals["base_count"] += base_count
            totals["rows_with_fastq_bytes"] += int(has_bytes)
            totals["rows_missing_fastq_bytes"] += int(not has_bytes)

            for bucket, key in ((strategy, strategy_name), (source, source_name)):
                item = bucket[key]
                item["runs"] += 1
                item["studies"].add(study)
                item["bytes"] += bytes_value
                item["bases"] += base_count

            scientific = scientific_names[scientific_name]
            scientific["runs"] += 1
            scientific["bytes"] += bytes_value

            study_item = studies[study]
            study_item["runs"] += 1
            study_item["bytes"] += bytes_value
            study_item["bases"] += base_count
            study_item["strategies"].add(strategy_name)
            study_item["scientific_names"].add(scientific_name)

            is_mg1655 = row.get("tax_id") == "511145" or "MG1655" in scientific_name.upper()
            if is_mg1655:
                mg1655_writer.writerow(row)
                totals["mg1655_rows"] += 1
                totals["mg1655_fastq_bytes"] += bytes_value

    totals["unique_studies"] = len(all_studies)
    study_table = MANIFESTS / f"{prefix}_study_summary.tsv.gz"
    with gzip.open(study_table, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["study_accession", "runs", "fastq_bytes", "base_count", "strategies", "scientific_names"])
        for study, item in sorted(studies.items(), key=lambda pair: pair[1]["bytes"], reverse=True):
            writer.writerow(
                [
                    study,
                    item["runs"],
                    item["bytes"],
                    item["bases"],
                    ";".join(sorted(item["strategies"])),
                    ";".join(sorted(item["scientific_names"])),
                ]
            )

    def top_bucket(bucket: dict, limit: int = 50) -> list[dict]:
        values = []
        for name, item in bucket.items():
            values.append(
                {
                    "name": name,
                    "runs": item["runs"],
                    "studies": len(item["studies"]),
                    "fastq_bytes": item["bytes"],
                    "base_count": item["bases"],
                }
            )
        return sorted(values, key=lambda item: item["fastq_bytes"], reverse=True)[:limit]

    summary = {
        "source": "ENA Portal API",
        "prefix": prefix,
        "snapshot_date": utc_now(),
        "input_file": str(input_path.relative_to(ROOT)),
        "input_bytes": input_path.stat().st_size,
        "input_sha256": sha256_file(input_path),
        "totals": totals,
        "top_library_strategies": top_bucket(strategy),
        "top_library_sources": top_bucket(source),
        "top_scientific_names": sorted(
            (
                {"name": name, "runs": item["runs"], "fastq_bytes": item["bytes"]}
                for name, item in scientific_names.items()
            ),
            key=lambda item: item["fastq_bytes"],
            reverse=True,
        )[:50],
        "top_studies": [
            {
                "study_accession": study,
                "runs": item["runs"],
                "fastq_bytes": item["bytes"],
                "base_count": item["bases"],
                "strategies": sorted(item["strategies"]),
                "scientific_names": sorted(item["scientific_names"]),
            }
            for study, item in sorted(studies.items(), key=lambda pair: pair[1]["bytes"], reverse=True)[:100]
        ],
    }
    write_json(REPORTS / f"{prefix}_summary.json", summary)

    mg1655_summary = {
        "source": "ENA Portal API",
        "definition": "tax_id=511145 or scientific_name contains MG1655",
        "snapshot_date": summary["snapshot_date"],
        "rows": totals["mg1655_rows"],
        "fastq_bytes": totals["mg1655_fastq_bytes"],
        "output_file": str(mg1655_path.relative_to(ROOT)),
        "output_bytes": mg1655_path.stat().st_size,
        "output_sha256": sha256_file(mg1655_path),
    }
    write_json(REPORTS / f"{prefix}_mg1655_summary.json", mg1655_summary)
    return summary


def fetch_ena(
    query: str,
    prefix: str,
    force: bool,
    include_files: bool = False,
    include_context: bool = False,
) -> None:
    ensure_dirs()
    destination = MANIFESTS / f"{prefix}.tsv.gz"
    if include_context:
        fields = ENA_CONTEXT_FIELDS
    elif include_files:
        fields = ENA_FILE_FIELDS
    else:
        fields = ENA_FIELDS
    if destination.exists() and not force:
        print(f"ENA manifest already exists, summarizing: {destination}")
        summarize_ena(destination, prefix)
        return

    params = {
        "result": "read_run",
        "query": query,
        "fields": ",".join(fields),
        "format": "tsv",
        "limit": "0",
    }
    url = "https://www.ebi.ac.uk/ena/portal/api/search?" + urlencode(params)
    temp_tsv = TMP / f"{prefix}.tsv"
    if temp_tsv.exists():
        temp_tsv.unlink()
    print(f"Fetching ENA metadata query: {query}")
    run_curl_to_file([url], temp_tsv)
    print(f"Compressing manifest: {destination}")
    gzip_tsv(temp_tsv, destination, fields)
    temp_tsv.unlink()
    summary = summarize_ena(destination, prefix)
    snapshot = {
        "source": "ENA Portal API",
        "retrieved_at": utc_now(),
        "query": query,
        "fields": fields,
        "manifest": str(destination.relative_to(ROOT)),
        "manifest_bytes": destination.stat().st_size,
        "manifest_sha256": sha256_file(destination),
    }
    write_json(QUERY_SNAPSHOTS / f"{prefix}.json", snapshot)
    print(json.dumps(summary["totals"], ensure_ascii=False, indent=2))


def ncbi_count(term: str, database: str, api_key: str | None) -> int:
    params = {
        "db": database,
        "term": term,
        "retmode": "json",
        "rettype": "count",
    }
    if api_key:
        params["api_key"] = api_key
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urlencode(params)
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            payload = json.loads(run_curl_text([url], timeout=120))
            return int(payload["esearchresult"]["count"])
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"NCBI query failed for {database}/{term}: {last_error}")


def fetch_ncbi_counts(api_key: str | None) -> None:
    ensure_dirs()
    queries = {
        "sra_species": ("sra", "txid562[Organism:exp]"),
        "sra_mg1655": ("sra", "txid511145[Organism:exp]"),
        "bioproject_species": ("bioproject", "txid562[Organism:exp]"),
        "biosample_species": ("biosample", "txid562[Organism:exp]"),
        "assembly_species": ("assembly", "txid562[Organism:exp]"),
        "assembly_mg1655": ("assembly", "txid511145[Organism:exp]"),
        "geo_species": ("gds", "txid562[Organism:exp]"),
        "geo_mg1655": ("gds", "txid511145[Organism:exp]"),
    }
    delay = 0.12 if api_key else 0.4
    results: dict[str, object] = {}
    for name, (database, term) in queries.items():
        try:
            count = ncbi_count(term, database, api_key)
            results[name] = {
                "database": database,
                "term": term,
                "count": count,
                "status": "ok",
            }
            print(f"NCBI {name}: {count}")
        except Exception as exc:  # noqa: BLE001
            results[name] = {
                "database": database,
                "term": term,
                "count": None,
                "status": "error",
                "error": str(exc),
            }
            print(f"NCBI {name}: ERROR: {exc}", file=sys.stderr)
        time.sleep(delay)
    payload = {
        "source": "NCBI E-utilities",
        "retrieved_at": utc_now(),
        "api_key_used": bool(api_key),
        "counts": results,
    }
    write_json(REPORTS / "ncbi_counts.json", payload)


def append_jsonl_gz(handle, item: dict) -> None:
    handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")


def fetch_pride(keyword: str, force: bool) -> None:
    ensure_dirs()
    raw_path = MANIFESTS / "pride_ecoli_projects.jsonl.gz"
    normalized_path = MANIFESTS / "pride_ecoli_projects.tsv.gz"
    if raw_path.exists() and normalized_path.exists() and not force:
        print(f"PRIDE manifests already exist: {raw_path}")
        return

    page_size = 100
    page = 0
    total_records: int | None = None
    project_count = 0
    normalized_fields = [
        "accession",
        "title",
        "organisms",
        "publicationDate",
        "submissionDate",
        "updatedDate",
        "submissionType",
        "instruments",
        "experimentTypes",
        "keywords",
        "projectDescription",
        "projectFileNames",
        "doi",
    ]
    with gzip.open(raw_path, "wt", encoding="utf-8", newline="") as raw_handle, gzip.open(
        normalized_path, "wt", encoding="utf-8", newline=""
    ) as normalized_handle:
        writer = csv.DictWriter(
            normalized_handle,
            fieldnames=normalized_fields,
            delimiter="\t",
            extrasaction="ignore",
        )
        writer.writeheader()
        while True:
            params = urlencode({"keyword": keyword, "pageSize": page_size, "page": page})
            url = f"https://www.ebi.ac.uk/pride/ws/archive/v2/search/projects?{params}"
            header_path = TMP / f"pride_page_{page}.headers"
            body_path = TMP / f"pride_page_{page}.json"
            for path in (header_path, body_path):
                if path.exists():
                    path.unlink()

            curl_args = [
                "-H",
                "Accept: application/json",
                "--dump-header",
                str(header_path),
                url,
            ]
            command = curl_base() + curl_args
            with body_path.open("wb") as body_handle:
                subprocess.run(command, check=True, stdout=body_handle, timeout=180)
            headers = header_path.read_text(encoding="utf-8", errors="replace")
            if total_records is None:
                for line in headers.splitlines():
                    if line.lower().startswith("total_records:"):
                        total_records = int(line.split(":", 1)[1].strip())
                        break
            payload = json.loads(body_path.read_text(encoding="utf-8"))
            if not payload:
                break
            for project in payload:
                append_jsonl_gz(raw_handle, project)
                normalized = {}
                for field in normalized_fields:
                    value = project.get(field)
                    if isinstance(value, list):
                        value = "|".join(str(item) for item in value)
                    normalized[field] = value
                writer.writerow(normalized)
                project_count += 1
            print(f"PRIDE page {page}: {len(payload)} projects")
            if len(payload) < page_size:
                break
            page += 1
            time.sleep(0.2)
            for path in (header_path, body_path):
                if path.exists():
                    path.unlink()

    summary = {
        "source": "PRIDE Archive REST API",
        "retrieved_at": utc_now(),
        "keyword": keyword,
        "total_records_reported": total_records,
        "projects_written": project_count,
        "raw_manifest": str(raw_path.relative_to(ROOT)),
        "raw_bytes": raw_path.stat().st_size,
        "raw_sha256": sha256_file(raw_path),
        "normalized_manifest": str(normalized_path.relative_to(ROOT)),
        "normalized_bytes": normalized_path.stat().st_size,
        "normalized_sha256": sha256_file(normalized_path),
    }
    write_json(REPORTS / "pride_ecoli_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    ena = subparsers.add_parser("ena", help="fetch and summarize an ENA read_run manifest")
    ena.add_argument("--query", default="tax_tree(562)")
    ena.add_argument("--prefix", default="ena_all_runs")
    ena.add_argument("--force", action="store_true")
    ena.add_argument("--include-files", action="store_true")
    ena.add_argument(
        "--include-context",
        action="store_true",
        help="include titles, protocol and instrument fields (implies --include-files)",
    )

    ncbi = subparsers.add_parser("ncbi-counts", help="snapshot NCBI E-utilities counts")
    ncbi.add_argument("--api-key", default=os.environ.get("NCBI_API_KEY"))

    pride = subparsers.add_parser("pride", help="fetch the PRIDE E. coli project catalog")
    pride.add_argument("--keyword", default="Escherichia coli")
    pride.add_argument("--force", action="store_true")

    all_command = subparsers.add_parser("all", help="run the P0 metadata collectors")
    all_command.add_argument("--force", action="store_true")
    all_command.add_argument("--api-key", default=os.environ.get("NCBI_API_KEY"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "ena":
        fetch_ena(
            args.query,
            args.prefix,
            args.force,
            args.include_files or args.include_context,
            args.include_context,
        )
    elif args.command == "ncbi-counts":
        fetch_ncbi_counts(args.api_key)
    elif args.command == "pride":
        fetch_pride(args.keyword, args.force)
    elif args.command == "all":
        fetch_ena("tax_tree(562)", "ena_all_runs", args.force, include_files=False)
        fetch_ncbi_counts(args.api_key)
        fetch_pride("Escherichia coli", args.force)
    else:
        raise RuntimeError(f"unknown command: {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

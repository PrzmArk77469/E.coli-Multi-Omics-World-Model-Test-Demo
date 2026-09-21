#!/usr/bin/env python3
"""Fetch E. coli study metadata and processed matrices from Metabolomics Workbench."""

from __future__ import annotations

import argparse
import csv
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
API = "https://www.metabolomicsworkbench.org/rest/study"
RAW = ROOT / "raw" / "metabolomics" / "MetabolomicsWorkbench"
PROCESSED = ROOT / "processed" / "metabolomics" / "MetabolomicsWorkbench"
MANIFESTS = ROOT / "manifests"
REPORTS = ROOT / "reports" / "downloads"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        "--max-time",
        "900",
        "--retry",
        "4",
        "--retry-all-errors",
        "--ssl-no-revoke",
    ]


def request_json(url: str) -> object:
    completed = subprocess.run(
        curl_base() + [url],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=960,
    )
    return json.loads(completed.stdout)


def request_text(url: str) -> str:
    completed = subprocess.run(
        curl_base() + [url],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=960,
    )
    return completed.stdout


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def fetch_study_list(keyword: str) -> list[dict]:
    payload = request_json(f"{API}/study_title/{quote(keyword, safe='')}/summary")
    if not isinstance(payload, dict):
        raise RuntimeError("unexpected Metabolomics Workbench study list")
    studies = []
    for item in payload.values():
        if not isinstance(item, dict):
            continue
        if "escherichia coli" not in (item.get("species") or "").lower():
            continue
        studies.append(item)
    studies.sort(key=lambda item: item["study_id"])
    return studies


def fetch_endpoint(study_id: str, endpoint: str) -> object:
    return request_json(f"{API}/study_id/{quote(study_id)}/{endpoint}")


def fetch_study(study: dict) -> tuple[str, dict[str, object], list[str]]:
    study_id = study["study_id"]
    payloads: dict[str, object] = {"summary": study}
    errors: list[str] = []
    for endpoint in ("analysis", "factors", "datatable", "data"):
        try:
            if endpoint == "datatable":
                payloads[endpoint] = request_text(f"{API}/study_id/{quote(study_id)}/datatable")
            else:
                payloads[endpoint] = fetch_endpoint(study_id, endpoint)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{endpoint}: {exc}")
        time.sleep(0.15)
    return study_id, payloads, errors


def records(payload: object) -> list[dict]:
    if isinstance(payload, dict):
        return [item for item in payload.values() if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def write_samples(study_id: str, factors: object) -> int:
    rows = records(factors)
    if not rows:
        return 0
    fields = [
        "study_id",
        "local_sample_id",
        "mb_sample_id",
        "sample_source",
        "factors",
        "raw_data",
    ]
    path = PROCESSED / f"{study_id}_samples.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def write_metabolites_long(study_id: str, data_payload: object) -> int:
    rows = records(data_payload)
    if not rows:
        return 0
    path = PROCESSED / f"{study_id}_metabolites_long.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "study_id",
        "analysis_id",
        "analysis_summary",
        "metabolite_name",
        "metabolite_id",
        "refmet_name",
        "units",
        "sample_id",
        "value",
    ]
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for row in rows:
            samples = row.get("DATA") or {}
            if not isinstance(samples, dict):
                continue
            for sample_id, value in sorted(samples.items()):
                writer.writerow(
                    {
                        "study_id": row.get("study_id") or study_id,
                        "analysis_id": row.get("analysis_id") or "",
                        "analysis_summary": row.get("analysis_summary") or "",
                        "metabolite_name": row.get("metabolite_name") or "",
                        "metabolite_id": row.get("metabolite_id") or "",
                        "refmet_name": row.get("refmet_name") or "",
                        "units": row.get("units") or "",
                        "sample_id": sample_id,
                        "value": value,
                    }
                )
                count += 1
    return count


def write_manifest(studies: list[dict]) -> Path:
    path = MANIFESTS / "download_queue" / "metabolomics_workbench_ecoli_studies.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "study_id",
        "study_title",
        "species",
        "analysis_type",
        "number_of_samples",
        "release_date",
        "license",
        "license_url",
        "study_url",
        "license_status",
        "redistribution_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for study in studies:
            writer.writerow(
                {
                    **study,
                    "license_status": "open_attribution_cc_by_4_0",
                    "redistribution_status": "allowed_with_attribution",
                }
            )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keyword", default="Escherichia coli")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    studies = fetch_study_list(args.keyword)
    manifest_path = write_manifest(studies)
    failures: list[dict] = []
    endpoint_errors: list[dict] = []
    metabolite_rows = 0
    sample_rows = 0
    downloaded_studies = 0

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(fetch_study, study): study for study in studies}
        for future in as_completed(futures):
            study = futures[future]
            study_id = study["study_id"]
            try:
                _, payloads, errors = future.result()
            except Exception as exc:  # noqa: BLE001
                failures.append({"study_id": study_id, "error": str(exc)})
                continue
            for endpoint, payload in payloads.items():
                if endpoint == "datatable":
                    path = RAW / study_id / "datatable.tsv"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(str(payload), encoding="utf-8")
                else:
                    write_json(RAW / study_id / f"{endpoint}.json", payload)
            if errors:
                endpoint_errors.append({"study_id": study_id, "errors": errors})
            sample_rows += write_samples(study_id, payloads.get("factors"))
            metabolite_rows += write_metabolites_long(study_id, payloads.get("data"))
            downloaded_studies += 1
            print(
                f"downloaded: {study_id} endpoints={','.join(sorted(payloads))}",
                flush=True,
            )

    summary = {
        "source": "Metabolomics Workbench REST API",
        "finished_at": utc_now(),
        "keyword": args.keyword,
        "ecoli_studies": len(studies),
        "studies_downloaded": downloaded_studies,
        "study_failures": failures,
        "endpoint_errors": endpoint_errors,
        "sample_rows": sample_rows,
        "metabolite_long_rows": metabolite_rows,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "manifest_sha256": sha256_file(manifest_path),
        "raw_root": str(RAW.relative_to(ROOT)),
        "processed_root": str(PROCESSED.relative_to(ROOT)),
        "license_policy": "CC BY 4.0 for listed studies; preserve attribution",
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    summary_path = REPORTS / "metabolomics_workbench_download_summary.json"
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

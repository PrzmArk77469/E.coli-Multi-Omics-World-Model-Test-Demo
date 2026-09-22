#!/usr/bin/env python3
"""Fetch ENA BioSample XML with resume support and an optional HTTP proxy."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


API_ROOT = "https://www.ebi.ac.uk/ena/browser/api/xml"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def sample_accessions(path: Path) -> list[str]:
    accessions: set[str] = set()
    with open_text(path) as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if (row.get("source") or "").strip().upper() != "ENA":
                continue
            accession = (row.get("sample_accession") or "").strip()
            if accession:
                accessions.add(accession)
    return sorted(accessions)


def valid_cached_xml(path: Path, accession: str) -> bool:
    if not path.exists():
        return False
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return False
    sample = root.find(".//SAMPLE")
    return sample is not None and sample.attrib.get("accession") == accession


def fetch_one(
    accession: str,
    cache_dir: Path,
    proxy: str,
    timeout: int,
    retries: int,
) -> tuple[str, str]:
    destination = cache_dir / f"{accession}.xml"
    if valid_cached_xml(destination, accession):
        return accession, "cached"
    partial = cache_dir / f"{accession}.xml.part"
    request = urllib.request.Request(
        f"{API_ROOT}/{accession}",
        headers={"User-Agent": "Project13-ENA-BioSample-Fetcher/1.0"},
    )
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    else:
        opener = urllib.request.build_opener()
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            with opener.open(request, timeout=timeout) as response:
                payload = response.read()
            root = ET.fromstring(payload)
            sample = root.find(".//SAMPLE")
            if sample is None or sample.attrib.get("accession") != accession:
                raise ValueError("response does not contain the requested SAMPLE")
            partial.write_bytes(payload)
            partial.replace(destination)
            return accession, "downloaded"
        except (urllib.error.URLError, TimeoutError, ValueError, ET.ParseError) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(min(20.0, 0.75 * (2 ** (attempt - 1))))
    return accession, f"failed: {last_error}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-master", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--proxy", default="")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--retries", type=int, default=4)
    args = parser.parse_args()

    accessions = sample_accessions(args.sample_master)
    if args.limit is not None:
        accessions = accessions[: args.limit]
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    counts: Counter = Counter()
    failures: list[dict[str, str]] = []
    started_at = utc_now()

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                fetch_one,
                accession,
                args.cache_dir,
                args.proxy,
                args.timeout,
                args.retries,
            ): accession
            for accession in accessions
        }
        for index, future in enumerate(as_completed(futures), start=1):
            accession, status = future.result()
            counts[status.split(":", 1)[0]] += 1
            if status.startswith("failed:"):
                failures.append({"accession": accession, "error": status})
            if index % 100 == 0 or index == len(accessions):
                print(
                    f"BioSample: {index}/{len(accessions)} "
                    f"cached={counts['cached']} "
                    f"downloaded={counts['downloaded']} "
                    f"failed={counts['failed']}",
                    flush=True,
                )

    summary = {
        "started_at": started_at,
        "finished_at": utc_now(),
        "sample_rows_requested": len(accessions),
        "cache_dir": str(args.cache_dir),
        "counts": dict(counts),
        "failures": failures,
        "api_root": API_ROOT,
    }
    report = args.cache_dir.parent / "ena_biosample_fetch_summary.json"
    report.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

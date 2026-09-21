#!/usr/bin/env python3
"""Verify local files against the SHA256 integrity manifest."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT / "reports" / "integrity" / "local_sha256_manifest.tsv.gz"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_one(row: dict) -> dict:
    relative = row["relative_path"]
    path = ROOT / relative
    if not path.exists():
        return {"relative_path": relative, "status": "missing"}
    expected_bytes = int(row["size_bytes"])
    actual_bytes = path.stat().st_size
    if actual_bytes != expected_bytes:
        return {
            "relative_path": relative,
            "status": "size_mismatch",
            "expected": expected_bytes,
            "actual": actual_bytes,
        }
    actual_sha256 = sha256_file(path)
    if actual_sha256 != row["sha256"]:
        return {
            "relative_path": relative,
            "status": "sha256_mismatch",
            "expected": row["sha256"],
            "actual": actual_sha256,
        }
    return {"relative_path": relative, "status": "verified"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    manifest = args.manifest.resolve()
    if not manifest.exists():
        raise SystemExit(f"missing manifest: {manifest}")
    rows: list[dict] = []
    with gzip.open(manifest, "rt", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if args.limit:
        rows = rows[: args.limit]

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(verify_one, row) for row in rows]
        for future in as_completed(futures):
            results.append(future.result())

    counts: dict[str, int] = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    bad = [
        result
        for result in results
        if result["status"] != "verified"
    ]
    summary = {
        "manifest": str(manifest.relative_to(ROOT)),
        "checked": len(results),
        "counts": counts,
        "failures": bad[:200],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

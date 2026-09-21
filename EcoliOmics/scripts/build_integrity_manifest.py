#!/usr/bin/env python3
"""Build a SHA256 snapshot manifest and data card for the local data lake."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = (
    "manifests",
    "raw",
    "reference",
    "processed",
    "integrated",
    "registry",
)
OUTPUT_DIR = ROOT / "reports" / "integrity"
MANIFEST_PATH = OUTPUT_DIR / "local_sha256_manifest.tsv.gz"
SUMMARY_PATH = OUTPUT_DIR / "local_sha256_manifest_summary.json"
DATA_CARD_PATH = ROOT / "reports" / "data_cards" / "ECOLI_OMICS_DATA_CARD.md"
INVENTORY_PATH = ROOT / "reports" / "coverage" / "download_inventory.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_queue_metadata() -> dict[str, dict]:
    index: dict[str, dict] = {}
    queue_dir = ROOT / "manifests" / "download_queue"
    for path in sorted(queue_dir.glob("*_files.tsv")):
        for row in read_tsv(path):
            relative = row.get("local_relative_path") or ""
            if relative:
                index[relative.replace("\\", "/")] = row
    return index


def load_workbench_licenses() -> dict[str, dict]:
    path = (
        ROOT
        / "manifests"
        / "download_queue"
        / "metabolomics_workbench_ecoli_studies.tsv"
    )
    return {
        row.get("study_id", ""): row
        for row in read_tsv(path)
        if row.get("study_id")
    }


def source_metadata(
    relative_path: str,
    queue_index: dict[str, dict],
    workbench_licenses: dict[str, dict],
) -> dict:
    normalized = relative_path.replace("\\", "/")
    parts = Path(normalized).parts
    layer = parts[0] if parts else ""
    row = queue_index.get(normalized, {})
    source = ""
    accession = ""
    license_status = "source_defined"
    redistribution_status = "review_required"

    if layer == "raw" and len(parts) > 2:
        if parts[1] == "sequencing":
            source = "ENA"
        else:
            source = parts[2]
    elif layer in {"manifests", "reference", "processed", "integrated", "registry"}:
        source = layer

    if row:
        accession = (
            row.get("run_accession")
            or row.get("project_accession")
            or row.get("study_accession")
            or row.get("accession")
            or ""
        )

    if layer == "raw" and source in {"ENA", "PRIDE", "MetaboLights"}:
        license_status = "license_unverified"
        redistribution_status = "blocked_until_reviewed"
    elif layer == "raw" and source == "MetabolomicsWorkbench":
        study_id = next(
            (
                part
                for part in parts
                if part.startswith("ST") and part[2:].isdigit()
            ),
            "",
        )
        study = workbench_licenses.get(study_id, {})
        license_status = study.get("license_status") or "source_defined"
        redistribution_status = (
            study.get("redistribution_status") or "review_required"
        )
        accession = accession or study_id
    elif layer in {"processed", "integrated"}:
        license_status = "derived_from_source"
        redistribution_status = "source_terms_apply"
    elif layer in {"manifests", "registry"}:
        license_status = "metadata_only"
        redistribution_status = "review_required"
    elif layer == "reference":
        license_status = "source_defined"
        redistribution_status = "review_required"

    return {
        "layer": layer,
        "source": source,
        "accession": accession,
        "license_status": license_status,
        "redistribution_status": redistribution_status,
    }


def iter_files(roots: list[str]) -> list[Path]:
    files: list[Path] = []
    for root_name in roots:
        root = ROOT / root_name
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def hash_one(path: Path, queue_index: dict[str, dict], workbench: dict[str, dict]) -> dict:
    relative = path.relative_to(ROOT).as_posix()
    before = path.stat()
    digest = sha256_file(path)
    after = path.stat()
    metadata = source_metadata(relative, queue_index, workbench)
    return {
        "relative_path": relative,
        **metadata,
        "size_bytes": after.st_size,
        "mtime_utc": datetime.fromtimestamp(
            after.st_mtime, timezone.utc
        ).isoformat(timespec="seconds"),
        "sha256": digest,
        "stable_during_hash": int(
            before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns
        ),
    }


def write_manifest(rows: list[dict]) -> tuple[str, int, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        "relative_path",
        "layer",
        "source",
        "accession",
        "license_status",
        "redistribution_status",
        "size_bytes",
        "mtime_utc",
        "sha256",
        "stable_during_hash",
    ]
    with gzip.open(MANIFEST_PATH, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    return (
        sha256_file(MANIFEST_PATH),
        MANIFEST_PATH.stat().st_size,
        str(MANIFEST_PATH.relative_to(ROOT)),
    )


def render_count_table(values: dict[str, dict]) -> list[str]:
    lines = ["| Layer | Files | Bytes |", "|---|---:|---:|"]
    for name, item in sorted(values.items()):
        lines.append(
            f"| `{name}` | {item['files']:,} | {item['bytes']:,} |"
        )
    return lines


def write_data_card(
    snapshot_id: str,
    rows: list[dict],
    manifest_sha256: str,
    manifest_bytes: int,
) -> None:
    by_layer: dict[str, dict] = {}
    by_license: Counter = Counter()
    by_source: Counter = Counter()
    for row in rows:
        bucket = by_layer.setdefault(
            row["layer"], {"files": 0, "bytes": 0}
        )
        bucket["files"] += 1
        bucket["bytes"] += int(row["size_bytes"])
        by_license[row["license_status"]] += 1
        if row["source"]:
            by_source[row["source"]] += 1

    inventory = read_json(INVENTORY_PATH)
    coverage_lines = [
        "| Queue | Complete / Expected | Present Bytes | Missing | Mismatch |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in inventory.get("queues", []):
        coverage_lines.append(
            "| {prefix} | {present}/{expected} | {bytes:,} | {missing} | "
            "{mismatch} |".format(
                prefix=item.get("prefix", ""),
                present=item.get("files_present_and_complete", 0),
                expected=item.get("files_expected", 0),
                bytes=item.get("bytes_present", 0),
                missing=item.get("files_missing", 0),
                mismatch=item.get("files_size_mismatch", 0),
            )
        )

    lines = [
        "# EcoliOmics Data Card",
        "",
        f"- Snapshot ID: `{snapshot_id}`",
        f"- Manifest: `{MANIFEST_PATH.relative_to(ROOT).as_posix()}`",
        f"- Manifest SHA256: `{manifest_sha256}`",
        f"- Manifest bytes: `{manifest_bytes:,}`",
        f"- Data files: `{len(rows):,}`",
        f"- Data bytes: `{sum(int(row['size_bytes']) for row in rows):,}`",
        f"- Unstable during hashing: `{sum(1 for row in rows if not row['stable_during_hash']):,}`",
        "",
        "## Snapshot Scope",
        "",
        "The snapshot covers immutable evidence, references, processed tables, "
        "integration products, source manifests and registry policy files. Reports "
        "are derived and can be regenerated from the manifest.",
        "",
        *render_count_table(by_layer),
        "",
        "## License Counts",
        "",
        "| License status | Files |",
        "|---|---:|",
    ]
    for name, count in sorted(by_license.items()):
        lines.append(f"| `{name}` | {count:,} |")
    lines.extend(
        [
            "",
            "## Covered Queues",
            "",
            *coverage_lines,
            "",
            "## Main Sources",
            "",
            "| Source | Files |",
            "|---|---:|",
        ]
    )
    for name, count in by_source.most_common(20):
        lines.append(f"| `{name}` | {count:,} |")
    lines.extend(
        [
            "",
            "## Use and Redistribution",
            "",
            "- ENA, PRIDE and RegulonDB remain `license_unverified` for local "
            "analysis until study-level review is complete.",
            "- Metabolomics Workbench studies listed with CC BY 4.0 require "
            "attribution.",
            "- The SHA256 manifest verifies local bytes; it does not change the "
            "source license.",
            "- No vendor raw proteomics or metabolomics files are included unless "
            "explicitly present in the manifest.",
        ]
    )
    DATA_CARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_CARD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roots",
        nargs="+",
        default=list(DEFAULT_ROOTS),
        help="top-level data directories to include",
    )
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    queue_index = load_queue_metadata()
    workbench = load_workbench_licenses()
    files = iter_files(args.roots)
    if not files:
        raise SystemExit("no files matched the requested roots")

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(hash_one, path, queue_index, workbench): path
            for path in files
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            path = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"failed to hash {path}: {exc}") from exc
            if completed % 100 == 0 or completed == len(files):
                print(f"hashed {completed}/{len(files)} files", flush=True)

    rows.sort(key=lambda row: row["relative_path"])
    manifest_sha256, manifest_bytes, manifest_relative = write_manifest(rows)
    snapshot_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + manifest_sha256[:12]
    )
    by_layer: dict[str, dict] = {}
    by_license: Counter = Counter()
    for row in rows:
        bucket = by_layer.setdefault(
            row["layer"], {"files": 0, "bytes": 0}
        )
        bucket["files"] += 1
        bucket["bytes"] += int(row["size_bytes"])
        by_license[row["license_status"]] += 1
    summary = {
        "snapshot_id": snapshot_id,
        "generated_at": utc_now(),
        "roots": args.roots,
        "files": len(rows),
        "bytes": sum(int(row["size_bytes"]) for row in rows),
        "unstable_files": sum(
            1 for row in rows if not row["stable_during_hash"]
        ),
        "by_layer": dict(sorted(by_layer.items())),
        "by_license": dict(sorted(by_license.items())),
        "manifest": manifest_relative,
        "manifest_bytes": manifest_bytes,
        "manifest_sha256": manifest_sha256,
        "data_card": str(DATA_CARD_PATH.relative_to(ROOT)),
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_data_card(snapshot_id, rows, manifest_sha256, manifest_bytes)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

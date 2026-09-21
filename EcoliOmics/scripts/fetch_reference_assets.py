#!/usr/bin/env python3
"""Download small, versioned reference and identifier assets."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp" / "downloads"

ASSETS = [
    {
        "name": "iML1515.xml",
        "url": "https://bigg.ucsd.edu/static/models/iML1515.xml",
        "destination": ROOT / "reference" / "BiGG" / "iML1515" / "iML1515.xml",
        "license_tag": "download_only",
        "expected_format": "text",
    },
    {
        "name": "iML1515.json",
        "url": "https://bigg.ucsd.edu/static/models/iML1515.json",
        "destination": ROOT / "reference" / "BiGG" / "iML1515" / "iML1515.json",
        "license_tag": "download_only",
        "expected_format": "json",
    },
    {
        "name": "bigg_model_metadata.json",
        "url": "https://bigg.ucsd.edu/api/v2/models/iML1515",
        "destination": ROOT / "reference" / "BiGG" / "iML1515" / "bigg_model_metadata.json",
        "license_tag": "download_only",
        "expected_format": "json",
    },
    {
        "name": "uniprot_mg1655_UP000000625.tsv.gz",
        "url": (
            "https://rest.uniprot.org/uniprotkb/stream?"
            "query=proteome%3AUP000000625&format=tsv&compressed=true"
            "&fields=accession,id,reviewed,protein_name,gene_primary,gene_oln,"
            "xref_geneid,xref_refseq,xref_kegg,ec,go,length,sequence"
        ),
        "destination": ROOT
        / "reference"
        / "MG1655"
        / "UniProt"
        / "uniprot_mg1655_UP000000625.tsv.gz",
        "license_tag": "open_attribution",
        "expected_format": "gzip",
        "minimum_bytes": 100_000,
    },
]


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
        "5",
        "--retry-all-errors",
        "--speed-time",
        "180",
        "--speed-limit",
        "512",
    ]
    if platform.system().lower() == "windows":
        command.append("--ssl-no-revoke")
    return command


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(path: Path, expected_format: str, minimum_bytes: int = 0) -> None:
    if path.stat().st_size == 0:
        raise RuntimeError(f"empty file: {path}")
    if minimum_bytes and path.stat().st_size < minimum_bytes:
        raise RuntimeError(
            f"file smaller than expected: {path} ({path.stat().st_size} < {minimum_bytes})"
        )
    if expected_format == "json":
        json.loads(path.read_text(encoding="utf-8"))
    elif expected_format == "gzip":
        with gzip.open(path, "rb") as handle:
            if not handle.read(1024):
                raise RuntimeError(f"empty gzip payload: {path}")
    elif expected_format == "text":
        if not path.read_text(encoding="utf-8", errors="replace").strip():
            raise RuntimeError(f"empty text file: {path}")


def download(item: dict, force: bool) -> dict:
    destination = item["destination"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    part = TMP / (destination.name + ".part")
    if destination.exists() and not force:
        validate(destination, item["expected_format"], int(item.get("minimum_bytes", 0)))
        return {
            "name": item["name"],
            "url": item["url"],
            "destination": str(destination.relative_to(ROOT)),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "license_tag": item["license_tag"],
            "status": "skipped_existing",
        }
    if part.exists():
        part.unlink()
    command = curl_base() + ["--output", str(part), item["url"]]
    subprocess.run(command, check=True, timeout=3600)
    validate(part, item["expected_format"], int(item.get("minimum_bytes", 0)))
    part.replace(destination)
    return {
        "name": item["name"],
        "url": item["url"],
        "destination": str(destination.relative_to(ROOT)),
        "bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
        "license_tag": item["license_tag"],
        "status": "downloaded",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    records = [download(item, args.force) for item in ASSETS]
    manifest = {
        "retrieved_at": utc_now(),
        "assets": records,
    }
    output = ROOT / "reference" / "reference_assets_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

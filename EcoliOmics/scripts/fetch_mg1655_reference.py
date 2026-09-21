#!/usr/bin/env python3
"""Download and verify the NCBI MG1655 reference bundle."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "reference" / "MG1655" / "NCBI" / "GCF_000005845.2"
TMP = ROOT / "tmp" / "downloads"
ASSEMBLY = "GCF_000005845.2_ASM584v2"
BASE_URL = f"https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/005/845/{ASSEMBLY}/"
FILES = [
    "GCF_000005845.2_ASM584v2_genomic.fna.gz",
    "GCF_000005845.2_ASM584v2_genomic.gbff.gz",
    "GCF_000005845.2_ASM584v2_genomic.gff.gz",
    "GCF_000005845.2_ASM584v2_genomic.gtf.gz",
    "GCF_000005845.2_ASM584v2_protein.faa.gz",
    "GCF_000005845.2_ASM584v2_protein.gpff.gz",
    "GCF_000005845.2_ASM584v2_rna_from_genomic.fna.gz",
    "GCF_000005845.2_ASM584v2_cds_from_genomic.fna.gz",
    "GCF_000005845.2_ASM584v2_translated_cds.faa.gz",
    "GCF_000005845.2_ASM584v2_feature_table.txt.gz",
    "GCF_000005845.2_ASM584v2_feature_count.txt",
    "GCF_000005845.2_ASM584v2_assembly_report.txt",
    "GCF_000005845.2_ASM584v2_assembly_stats.txt",
    "GCF_000005845.2_ASM584v2_ani_report.txt",
    "GCF_000005845.2_ASM584v2_fcs_report.txt",
    "README.txt",
    "assembly_status.txt",
    "annotation_hashes.txt",
    "md5checksums.txt",
]
OPTIONAL_FILES = {
    "GCF_000005845.2_ASM584v2_ani_report.txt",
    "GCF_000005845.2_ASM584v2_fcs_report.txt",
    "README.txt",
    "assembly_status.txt",
    "annotation_hashes.txt",
}


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


def download(url: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    part = output.with_suffix(output.suffix + ".part")
    if part.exists():
        part.unlink()
    if output.exists():
        return
    command = curl_base() + ["--output", str(part), url]
    subprocess.run(command, check=True, timeout=1800)
    part.replace(output)


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_checksums(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        checksum, name = parts
        checksums[Path(name.lstrip("./")).name] = checksum.lower()
    return checksums


def verify_gzip(path: Path) -> None:
    if path.suffix != ".gz":
        return
    with gzip.open(path, "rb") as handle:
        for _ in iter(lambda: handle.read(1024 * 1024), b""):
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    if args.force:
        for name in FILES:
            path = OUTDIR / name
            if path.exists():
                path.unlink()

    for name in FILES:
        print(f"Downloading {name}")
        try:
            download(BASE_URL + name, OUTDIR / name)
        except subprocess.CalledProcessError as exc:
            if name in OPTIONAL_FILES:
                print(f"  optional file unavailable: {name}: {exc}", file=sys.stderr)
                continue
            raise

    checksums = parse_checksums(OUTDIR / "md5checksums.txt")
    records = []
    failures = []
    for name in FILES:
        path = OUTDIR / name
        if not path.exists():
            if name in OPTIONAL_FILES:
                records.append(
                    {
                        "file": name,
                        "bytes": 0,
                        "md5": None,
                        "expected_md5": checksums.get(name),
                        "md5_ok": None,
                        "gzip_ok": None,
                        "gzip_error": None,
                        "sha256": None,
                        "url": BASE_URL + name,
                        "status": "optional_unavailable",
                    }
                )
                continue
            raise FileNotFoundError(path)
        expected = checksums.get(name)
        actual = md5_file(path)
        ok = expected is None or expected == actual
        gzip_ok = True
        gzip_error = None
        try:
            verify_gzip(path)
        except Exception as exc:  # noqa: BLE001
            gzip_ok = False
            gzip_error = str(exc)
        record = {
            "file": name,
            "bytes": path.stat().st_size,
            "md5": actual,
            "expected_md5": expected,
            "md5_ok": ok,
            "gzip_ok": gzip_ok,
            "gzip_error": gzip_error,
            "sha256": sha256_file(path),
            "url": BASE_URL + name,
            "status": "ok" if ok and gzip_ok else "verification_failed",
        }
        records.append(record)
        if not ok or not gzip_ok:
            failures.append(record)
        print(f"  md5_ok={ok} gzip_ok={gzip_ok} bytes={record['bytes']}")

    manifest = {
        "source": "NCBI RefSeq FTP",
        "retrieved_at": utc_now(),
        "assembly": "GCF_000005845.2",
        "assembly_name": "ASM584v2",
        "base_url": BASE_URL,
        "files": records,
        "failures": failures,
    }
    output = OUTDIR / "download_manifest.json"
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    required_failures = [item for item in failures if item["file"] not in OPTIONAL_FILES]
    if required_failures:
        print(f"{len(required_failures)} required reference files failed verification", file=sys.stderr)
        return 1
    print(f"MG1655 reference bundle verified: {OUTDIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

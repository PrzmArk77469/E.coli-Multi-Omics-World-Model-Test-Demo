# EcoliOmics

This directory implements the feasible, layered E. coli omics download plan.
See `CLASSIFICATION.md` for the omics taxonomy and rules that keep metadata,
raw evidence, processed matrices, and integrated products separate.
The latest covered/paused queue state is in
`reports/coverage/DATASET_STATUS.md`.

## Layers

- `registry/`: frozen scope, source, license and selection policies.
- `manifests/`: metadata-first catalogs. No raw FASTQ belongs here.
- `reference/`: reference genomes, annotation releases and knowledge snapshots.
- `raw/`: selected immutable source files.
- `processed/`: standardized outputs produced by versioned pipelines.
- `integrated/`: cross-omics masters and matched sample tables.
- `reports/`: coverage, QC, cost and data-card reports.
- `tmp/`: resumable downloads and scratch data.

## Bootstrap order

```text
1. ENA metadata manifest
2. NCBI count snapshot
3. PRIDE project catalog
4. MG1655 reference and annotation
5. Coverage report and download queue
6. Small pilot download of 20-50 MG1655 assays
7. Source-specific proteomics and metabolomics adapters
8. Reference and regulatory snapshots
9. Local SHA256 integrity manifest and data card
10. Sample, experiment and feature crosswalk integration tables
```

## Commands

The bundled workspace Python has no third-party dependencies installed, so the
bootstrap scripts use only the Python standard library plus the system curl.

```powershell
D:\Python314\python.exe .\scripts\ecoli_metadata.py all
D:\Python314\python.exe .\scripts\ecoli_metadata.py ena --query "tax_id=511145" --prefix ena_mg1655_context --include-context
D:\Python314\python.exe .\scripts\fetch_mg1655_reference.py
D:\Python314\python.exe .\scripts\build_l0_catalog.py
D:\Python314\python.exe .\scripts\build_download_queue.py --prefix core_mg1655_batch01
D:\Python314\python.exe .\scripts\download_queue.py --queue .\manifests\download_queue\core_mg1655_batch01_files.tsv --workers 2
D:\Python314\python.exe .\scripts\fetch_regulondb.py --download
D:\Python314\python.exe .\scripts\fetch_pride_files.py --download
D:\Python314\python.exe .\scripts\fetch_metabolights.py --download
D:\Python314\python.exe .\scripts\fetch_metabolomics_workbench.py
D:\Python314\python.exe .\scripts\summarize_downloads.py
D:\Python314\python.exe .\scripts\build_integrity_manifest.py --workers 4
D:\Python314\python.exe .\scripts\verify_integrity_manifest.py --workers 4
D:\Python314\python.exe .\scripts\build_integrated_master.py
D:\Python314\python.exe .\scripts\fetch_ena_biosamples.py --sample-master .\integrated\sample_master.tsv.gz --cache-dir .\manifests\biosample_xml --proxy http://127.0.0.1:7897 --limit 100
$env:PYTHONPATH = '..\Git\src'
D:\Python314\python.exe -m ecoli_world.conditions --sample-master .\integrated\sample_master.tsv.gz --output-dir .\integrated\condition_completion --biosample-cache .\manifests\biosample_xml
```

Network access may require running these commands outside the sandbox.
The `python` executable first on this machine may belong to MGLTools and is not
Python 3 compatible; use `D:\Python314\python.exe` for all EcoliOmics scripts.

## Rules

- Never write directly into a final raw-data path. Download to `.part`, verify,
  then rename.
- Keep raw files immutable.
- Record source URL, retrieval time, and checksums.
- A dataset without a license tag and provenance is metadata-only.
- `license_unverified` permits local analysis only; redistribution is blocked
  until the study or record terms are reviewed.
- Full species-wide FASTQ is an on-demand operation, not a default mirror.
- On Windows, use low concurrency for EBI long files and HTTPS instead of FTP
  for PRIDE; partial files are retained and the same queue can be resumed.

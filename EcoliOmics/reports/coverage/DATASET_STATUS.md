# EcoliOmics Dataset Status

Snapshot: 2026-09-14 UTC

## Completed

| Component | Result |
|---|---:|
| ENA species metadata | 604,829 runs, 1,141,149 file records, 9,881 studies |
| MG1655 context metadata | 20,864 records |
| Core MG1655 sequencing batch 01 | 64/64 files, 4.79 GB, 45 runs |
| Core MG1655 sequencing batch 02 | 68/68 files, 4.86 GB, 46 runs |
| MG1655 translatomics queue | 8/8 files, 1.27 GB, 5 runs |
| PRIDE processed batch 01 | 20/20 files, 21.4 MB |
| PRIDE processed batch 02 | 300/300 files, 2.06 GB, 300 projects |
| MetaboLights E. coli package | 813/813 files, 138 studies, 224.8 MB |
| Metabolomics Workbench | 16 studies, 676 sample rows, 36,747 metabolite rows |
| RegulonDB normalized export | 581 files, 109,831 rows |
| MG1655 reference | NCBI GCF_000005845.2, UniProt UP000000625 |
| BiGG iML1515 | JSON and SBML model files |
| Local SHA256 snapshot | 2,039 files, 14.25 GB, 0 unstable files |
| Integrated sample master | 602,778 sample rows |
| Integrated experiment master | 606,392 run/project/study rows |
| MG1655 feature crosswalk | 4,524 loci, 4,306 with UniProt links |

The completed queue paths have zero missing files and zero size mismatches at
the time of this snapshot. ENA queue verification also checks source MD5.
The six registered queues contain 1,273 unique complete files and
13,231,501,627 bytes. No `.part` file remains.

PRIDE batch 01 originally shared its status file with batch 02; that file was
overwritten when batch 02 finished. The consolidated report therefore derives
batch 01 status from current local size verification.

## Integration Status

Snapshot `20260915T074535Z-a9c2816e016e` includes the raw, reference,
processed, integrated, manifest and registry layers. The sample and experiment
masters are complete as structural joins, but they intentionally do not assign
omics integration levels yet.

Current metadata gaps:

- `condition`: 6.6% populated
- `genotype`: 4.0% populated
- `timepoint`: 0.01% populated
- `treatment`, `medium` and `replicate`: not yet populated

The next integration task is to extract ENA BioSample condition attributes and
map proteomics and metabolomics sample names to the same sample or condition
identifiers. `A`/`B`/`C` integration levels remain unassigned until that mapping
is explicit.

## Remaining Scope Decisions

There is no paused or failed automated download queue. The remaining items are
storage and license decisions rather than transfer failures:

| Item | Current treatment |
|---|---|
| MetaboLights vendor raw files | Metadata, MAF, sample and assay tables are local; vendor raw is not mirrored |
| Metabolomics Workbench vendor raw | 16 processed study packages are local; vendor raw is not mirrored |
| PRIDE raw and mzML files | Processed search/result files are local; raw instrument data require a project whitelist |
| EcoCyc, KEGG, BRENDA, SABIO-RK | Pending access and redistribution terms |
| ENA, PRIDE and RegulonDB redistribution | `license_unverified`; local analysis only until reviewed |

## Verification and Resume Commands

Recheck or extend the ENA queues with the proxy-capable backend:

```powershell
D:\Python314\python.exe .\scripts\download_queue.py --queue .\manifests\download_queue\core_mg1655_batch02_files.tsv --workers 4 --retries 8 --backend urllib --proxy http://127.0.0.1:7897
D:\Python314\python.exe .\scripts\download_queue.py --queue .\manifests\download_queue\core_mg1655_translatomics01_files.tsv --workers 2 --retries 8 --backend urllib --proxy http://127.0.0.1:7897
D:\Python314\python.exe .\scripts\fetch_pride_files.py --queue-prefix pride_processed_batch02 --target-files 300 --min-file-mib 1 --max-file-gib 1 --budget-gib 8 --exclude-prefix pride_processed_batch01 --workers 6 --download
D:\Python314\python.exe .\scripts\summarize_downloads.py
D:\Python314\python.exe .\scripts\build_integrity_manifest.py --workers 4
D:\Python314\python.exe .\scripts\verify_integrity_manifest.py --workers 4
D:\Python314\python.exe .\scripts\build_integrated_master.py
```

## Main Reports

- `reports/coverage/download_inventory.json`
- `reports/coverage/download_inventory.tsv`
- `reports/downloads/regulondb_download_summary.json`
- `reports/downloads/metabolights_metadata_download_summary.json`
- `reports/downloads/metabolomics_workbench_download_summary.json`
- `reports/downloads/pride_processed_download_summary.json`
- `reports/HUMAN_ACTIONS.md`
- `RESUME_DOWNLOADS.md`
- `reports/integrity/local_sha256_manifest.tsv.gz`
- `reports/integrity/local_sha256_manifest_summary.json`
- `reports/data_cards/ECOLI_OMICS_DATA_CARD.md`
- `integrated/sample_master.tsv.gz`
- `integrated/experiment_master.tsv.gz`
- `integrated/feature_crosswalk.tsv.gz`
- `reports/coverage/integration_build.json`
- `reports/coverage/integration_gaps.md`

All sequencing, PRIDE, and RegulonDB files remain local-analysis data with
license review required before redistribution. Metabolomics Workbench studies
listed in the manifest carry CC BY 4.0 metadata.

# EcoliOmics Data Card

- Snapshot ID: `20260915T074535Z-a9c2816e016e`
- Manifest: `reports/integrity/local_sha256_manifest.tsv.gz`
- Manifest SHA256: `a9c2816e016e773a7f00ecc7360245b29e2e6a8bc5ac9cca1b09bafbc8e9ecf2`
- Manifest bytes: `121,962`
- Data files: `2,039`
- Data bytes: `14,247,167,866`
- Unstable during hashing: `0`

## Snapshot Scope

The snapshot covers immutable evidence, references, processed tables, integration products, source manifests and registry policy files. Reports are derived and can be regenerated from the manifest.

| Layer | Files | Bytes |
|---|---:|---:|
| `integrated` | 3 | 36,559,972 |
| `manifests` | 34 | 935,554,240 |
| `processed` | 29 | 4,128,577 |
| `raw` | 1,353 | 13,233,212,624 |
| `reference` | 612 | 37,703,610 |
| `registry` | 8 | 8,843 |

## License Counts

| License status | Files |
|---|---:|
| `derived_from_source` | 32 |
| `license_unverified` | 1,273 |
| `metadata_only` | 42 |
| `open_attribution_cc_by_4_0` | 80 |
| `source_defined` | 612 |

## Covered Queues

| Queue | Complete / Expected | Present Bytes | Missing | Mismatch |
|---|---:|---:|---:|---:|
| core_mg1655_batch01 | 64/64 | 4,794,168,235 | 0 | 0 |
| core_mg1655_batch02 | 68/68 | 4,856,039,912 | 0 | 0 |
| core_mg1655_translatomics01 | 8/8 | 1,270,614,243 | 0 | 0 |
| pride_processed_batch01 | 20/20 | 21,399,003 | 0 | 0 |
| pride_processed_batch02 | 300/300 | 2,064,461,519 | 0 | 0 |
| metabolights_ecoli_metadata | 813/813 | 224,818,715 | 0 | 0 |

## Main Sources

| Source | Files |
|---|---:|
| `MetaboLights` | 813 |
| `reference` | 612 |
| `PRIDE` | 320 |
| `ENA` | 140 |
| `MetabolomicsWorkbench` | 80 |
| `manifests` | 34 |
| `processed` | 29 |
| `registry` | 8 |
| `integrated` | 3 |

## Use and Redistribution

- ENA, PRIDE and RegulonDB remain `license_unverified` for local analysis until study-level review is complete.
- Metabolomics Workbench studies listed with CC BY 4.0 require attribution.
- The SHA256 manifest verifies local bytes; it does not change the source license.
- No vendor raw proteomics or metabolomics files are included unless explicitly present in the manifest.

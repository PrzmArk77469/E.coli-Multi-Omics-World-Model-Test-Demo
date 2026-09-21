# EcoliOmics Classification and Storage Layers

This tree separates discovery metadata, selected evidence, processed matrices,
integration products, and on-demand raw data. A file is never promoted to a
higher layer without source provenance, size or checksum metadata, and a
license status.

## Storage Layers

| Layer | Directory | Content | Current policy |
|---|---|---|---|
| L0 | `manifests/`, `registry/`, `reports/coverage/` | species-wide accession, query and coverage metadata | retain broadly |
| L1 | `raw/sequencing/MG1655/` | selected MG1655 raw sequencing evidence | curated batches only |
| L1 | `raw/proteomics/PRIDE/` | selected PRIDE processed search results | small files first; vendor raw is manual |
| L1 | `raw/metabolomics/` | MetaboLights ISA/MAF metadata and Workbench snapshots | processed and metadata first |
| Reference | `reference/` | genome, annotation, regulatory, protein and model snapshots | fixed release per subdirectory |
| Processed | `processed/` | source-normalized matrices and sample tables | versioned transformations |
| Integrated | `integrated/` | cross-omics identifiers and matched tables | only after source-level QC |
| L2 | future `reference/universe/` | species-wide assembly and pangenome catalog | assemblies before raw WGS |
| L3 | not mirrored by default | other species-wide raw sequencing | retrieve when an analysis requires it |

## Omics Taxonomy

| omics_type | Included assays | Primary source | Current project state |
|---|---|---|---|
| `genomics` | WGS, WGA, genome finishing and validation | ENA/NCBI assembly | MG1655 selected runs plus reference |
| `transcriptomics` | RNA-Seq, ssRNA-seq, ncRNA-seq, EST | ENA/GEO | selected MG1655 runs |
| `regulomics` | ChIP-seq, RIP-seq, SELEX, TF binding | ENA/RegulonDB | selected runs plus normalized RegulonDB export |
| `translatomics` | Ribo-seq and related ribosome profiling | ENA | selected MG1655 runs |
| `functional_genomics` | Tn-seq, TraDIS and fitness assays | ENA | selected MG1655 runs |
| `methylomics` | Bisulfite-seq, MeDIP-seq and methylation calls | ENA/REBASE | selected MG1655 runs |
| `chromatin_accessibility` | ATAC-seq and MNase-seq | ENA | selected MG1655 runs |
| `structural_genomics` | Hi-C and chromosome conformation | ENA | selected MG1655 runs |
| `proteomics` | protein identification, quantification and PTM evidence | PRIDE | selected processed results; raw retention is pending |
| `metabolomics` | LC-MS, GC-MS, NMR and metabolite matrices | MetaboLights/Workbench | metadata and processed matrices |
| `fluxomics` | isotope tracing and metabolic flux | literature/specialist repositories | manual topic selection |
| `interactomics` | experimental PPI and complexes | IntAct/BioGRID | not yet downloaded |
| `phenomics` | growth, stress and phenotype tables | literature/specialist repositories | not yet downloaded |

## Classification Fields

The L0 SQLite catalog uses rule set `rule_v2_strategy_taxonomy_2026_09`.
Every run carries:

```text
omics_type
omics_priority
omics_confidence
classification_reason
needs_manual_review
data_tier
license_status
redistribution_status
```

Runs with unresolved strain identity, low classification confidence, no
checksum, or unclear assay type remain metadata-only.

## Promotion Rule

A downloaded file enters the local evidence lake only when it has:

1. A stable accession and source URL.
2. A known omics category and strain resolution.
3. A complete file with a retained download status.
4. A size or checksum verification when the source exposes one.
5. A license tag and a separate redistribution decision.

Processed derivatives must record the source accession, transformation script,
reference build, and creation time. Integrated tables must preserve `A`, `B`,
or `C` integration level and must not describe condition-matched samples as
same-sample matched data.

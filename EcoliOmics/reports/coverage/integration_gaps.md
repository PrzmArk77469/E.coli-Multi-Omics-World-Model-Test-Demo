# Integration Gap Report

Generated: `2026-09-15T07:45:22+00:00`

## Outputs

- `sample_master.tsv.gz`: 602,778 rows
- `experiment_master.tsv.gz`: 606,392 rows
- `feature_crosswalk.tsv.gz`: 4,524 MG1655 loci
- Feature crosswalk UniProt entries represented: 4,403

## Record Sources

| Source | Rows |
|---|---:|
| `ENA` | 562,314 |
| `MetaboLights` | 39,788 |
| `MetabolomicsWorkbench` | 676 |

## Highest-Priority Gaps

The sample master is structurally complete, but most ENA records still lack experimental condition fields. The following fields are populated in fewer than half of all sample rows:

- `condition`: 39,616/602,778 (6.6%)
- `treatment`: 0/602,778 (0.0%)
- `timepoint`: 54/602,778 (0.0%)
- `medium`: 0/602,778 (0.0%)
- `genotype`: 24,075/602,778 (4.0%)
- `replicate`: 0/602,778 (0.0%)

Recommended order:

1. Resolve MG1655 and K-12 strain records before species-wide matching.
2. Extract ENA BioSample attributes for medium, genotype, treatment, timepoint and replicate.
3. Map processed proteomics and metabolomics sample names to the same sample or condition identifiers.
4. Assign integration level `A`, `B` or `C` only after condition matching is explicit.

No record in this report is promoted to an integrated cross-omics pair merely because accessions share the same study.

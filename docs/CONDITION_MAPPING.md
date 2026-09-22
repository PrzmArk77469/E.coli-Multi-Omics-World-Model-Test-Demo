# Condition Mapping Architecture

## Purpose

This document's original architecture is extended by
[condition-map-v2 migration](SCIENTIFIC_INTEGRITY.md#rebuild-condition-mappings).
Rebuild old maps in a new directory; v1 and v2 condition IDs are incompatible.

The integrated sample master is structurally complete but condition fields are
sparse. This mapping layer gives every source sample a stable internal ID while
keeping observed metadata, inferred metadata, conflicts, and later synthetic
fixtures distinguishable.

The mapping layer does not overwrite `sample_master.tsv.gz`.

## Two identifiers

### `unified_sample_id`

```text
ECOLI_S_<sha256(source + source_record_key)[:24]>
```

This identifies one source record. Two database records are not merged merely
because they have the same study, title, or organism.

`source_record_key` uses the accession plus `sample_name` when the source's
`Source Name` is a generic group such as `cell lysate` or `purified enzyme`.
This prevents many MetaboLights samples from collapsing into one identifier.

### `condition_id`

```text
ECOLI_C_<sha256(version, extended condition signature)[:24]>
```

`replicate` is intentionally excluded. Replicates of the same condition share
one `condition_id`, while retaining different `unified_sample_id` values and
different replicate labels.

The signature includes medium, genotype, treatment, timepoint, strain,
temperature, oxygen, pH, and growth phase. Missing fields are `UNKNOWN`; any
incomplete signature is additionally scoped to its source sample to avoid
merging unrelated experiments. Fully populated signatures can share an ID
across replicates, but this alone does not approve cross-study integration.

## Current source adapters

| Source | Current evidence | Next evidence |
|---|---|---|
| ENA | Existing sample master columns; optional cached BioSample XML | Fetch BioSample XML for all selected ENA samples |
| MetaboLights | Existing columns and `metadata_json.factors` | Parse sample and assay factor values more completely |
| Metabolomics Workbench | Existing columns and factor dictionaries | Parse treatment, medium, and replicate factors |
| PRIDE | Project-level metadata only | Add sample-level SDRF or project supplement mapping before integration |

For ENA, the preferred tags are:

```text
medium: growth_medium, growth medium, culture_medium, culture medium, medium
genotype: genotype, strain genotype, substrain, sub_strain
treatment: treatment, experimental_treatment, perturbation, agent, stress
timepoint: timepoint, time_point, sampling_time, time elapsed
replicate: replicate, biological_replicate, replicate_number
```

The mapper also reads a genotype or medium sentence from the BioSample
description. Such values receive lower confidence than explicit attributes.

## Normalization

- Unicode is normalized, repeated whitespace is collapsed.
- Point timepoints are converted to minutes only with explicit units; intervals
  and unitless values are preserved without assuming minutes.
- Common media such as LB, LB Lennox, M9, M9 + glucose, M9 + glycerol, MOPS,
  and Terrific Broth are canonicalized.
- Common treatments such as untreated/control, IPTG, glucose limitation, and
  heat shock are canonicalized.
- Organism-only strings such as `Escherichia coli str. K-12 substr. MG1655`
  are not accepted as a genotype unless a mutation or explicit genotype is
  present.
- Replicate labels are normalized to `rep1`, `rep2`, and so on when possible.

Media/treatment aliases must match the entire value. Doses, supplements and
qualifiers are retained. `N/A` is missing metadata, not an untreated control.

Every field stores:

- selected canonical value;
- origin, such as `sample_master:genotype`, `biosample:genotype`, or
  `metadata.factors:Genotype`;
- evidence confidence;
- conflicting alternative values, if any.

## Build observed mapping

The mapper uses only the Python standard library:

```bash
cd /mnt/d/CodexApp/Project13/Git
PYTHONPATH=src python3 -m ecoli_world.conditions \
  --sample-master /mnt/d/CodexApp/Project13/EcoliOmics/integrated/sample_master.tsv.gz \
  --output-dir /mnt/d/CodexApp/Project13/EcoliOmics/integrated/condition_completion \
  --biosample-cache /mnt/d/CodexApp/Project13/EcoliOmics/manifests/biosample_xml
```

Outputs:

- `unified_sample_map.tsv.gz`
- `condition_mapping_summary.json`

## Fetch selected ENA BioSample XML

The fetch command is resumable and validates each cached XML response:

```bash
python3 EcoliOmics/scripts/fetch_ena_biosamples.py \
  --sample-master /mnt/d/CodexApp/Project13/EcoliOmics/integrated/sample_master.tsv.gz \
  --cache-dir /mnt/d/CodexApp/Project13/EcoliOmics/manifests/biosample_xml \
  --workers 4 \
  --proxy http://127.0.0.1:7897 \
  --limit 100
```

Remove `--limit` only after checking request rate, storage, and EBI usage
policy. The full ENA set contains more than 560,000 sample records, so the
initial Demo should fetch a stratified pilot rather than issue the full request
set.

## Conflict and confidence rules

1. An explicit BioSample attribute is stronger than a sentence inferred from a
   description.
2. Source columns already extracted by the project are weaker than an explicit
   BioSample attribute but stronger than a free-text derivation.
3. Multiple distinct normalized values are retained in `conflicts_json`; the
   highest-confidence value is selected.
4. A condition is `complete` only when medium, genotype, treatment, and
   timepoint are observed.
5. A condition is `core` when medium and genotype are observed.
6. No field with `data_origin=OBSERVED` may be populated from synthetic data.

## Integration boundary

This layer is the authority for observed conditions. Synthetic gap filling is a
separate sidecar built in the next stage. A simulation or model must join both
explicitly and record which fields are observed and which are synthetic.

# Scientific integrity and v0.2 migration

## What this release establishes

This is a **static synthetic event-engine demonstration**, with observed or
synthetic *condition metadata*. It is not a calibrated E. coli digital twin.
All molecular types, counts, coordinates, sizes, and reaction probabilities
remain synthetic. Condition labels do not change kinetic parameters. The
`rate` field is reserved metadata, not an implemented hazard rate; event delay
and cooldown are in steps. Diffusion, excluded volume, reversible binding,
mass/energy balances, and continued complex reactions are not implemented.

The software now enforces these contracts:

- Forward-cell pair traversal does not filter on agent-ID order. Every local
  candidate is visited once, including after agents are renumbered. A cell
  size smaller than the largest contact distance is rejected.
- Cell length includes both end caps. Every initialized agent sphere is
  inside the same x-axis spherocylinder shown in the viewer.
- A complex uses the smallest sphere enclosing its two unchanged member
  spheres. This envelope is not a structure-derived molecular radius. It can
  include empty space and protrude beyond a curved cell boundary even when its
  members fit; it is not an additional material particle or an excluded-volume
  packing constraint.
- Each simulation uses one source sample/condition context. A multi-sample
  cohort is a metadata catalog, not a collection of molecules in one cell.
- `data_origin` describes molecular data and remains `SYNTHETIC`.
  `condition_data_origin` separately describes attached condition metadata.
- Each exported object carries `coordinate_unit=um` and `radius_definition`.
  `copy_weight` still represents synthetic coarse-grained multiplicity.
  Bound members are retained with `active=false`; do not count both members
  and their complex as separate physical objects.

## Running and verifying

From the repository root, with Python 3.10 or newer:

```bash
python -m pip install -e '.[test]'
python -m unittest discover -s tests -v
python -m ecoli_world.cli --agents 2000 --steps 80 --seed 42 \
  --output artifacts/integrity-v2-seed42
```

Use a new output directory for every run. Existing nonempty directories are
rejected; logs use unique run IDs. Output includes `agents.jsonl`,
`complexes.jsonl`, `events.jsonl`, `summary.json`, and `run_manifest.json`.
Agent IDs are unique within a simulation; combine the manifest run ID with an
agent or complex ID when storing multiple runs together. The full JSONL files
retain unrounded coordinates. Viewer payloads round
agent coordinates for display and must not replace the spatial exports.

Each stage records input SHA256 hashes, source-data version, Git commit,
source-tree fingerprint (including dirty source), configuration, seed,
Python/platform, and container-image identifier. For a container run, supply
`--container-image repository@sha256:...` or `ECOLI_CONTAINER_IMAGE`; without
one, the manifest records `not_provided`. Seeds reproduce numerical outputs,
not wall-clock timestamps or run IDs. Gzip payloads omit timestamps and
filenames so repeatable data have repeatable hashes.

The CI workflow tests Python 3.10 and 3.12. Optional `jsonschema` test tooling
validates real agents, events, complexes, rules, and behaviors against all five
schemas. Runtime simulation and condition mapping still use only the standard
library. Without `.[test]`, the schema-conformance test is explicitly skipped.

## Rebuild condition mappings

Version `condition-map-v2` changes condition IDs. **Do not join v1 and v2 IDs.**
Rebuild from the original sample master/BioSample evidence, never from already
lossy normalized fields alone:

```bash
PYTHONPATH=src python -m ecoli_world.conditions \
  --sample-master /path/to/sample_master.tsv.gz \
  --biosample-cache /path/to/biosample_xml \
  --output-dir /path/to/condition-map-v2

PYTHONPATH=src python -m ecoli_world.demo_pipeline \
  --observed-map /path/to/condition-map-v2/unified_sample_map.tsv.gz \
  --output-dir /path/to/demo-v2-seed42 --agents 2000 --steps 80 --seed 42
```

The identity signature contains medium, genotype, treatment, timepoint,
strain, temperature, oxygen, pH, and growth phase; replicate is excluded.
Only exact aliases are collapsed. Dose, supplements, temperature qualifiers,
unitless times and time intervals are preserved rather than guessed. Missing
metadata such as `N/A` is not an untreated control. Unit-bearing point times
are converted to minutes, including negative times relative to a perturbation.
Temperature/pH/oxygen values remain conservative strings: unit equivalence
requires later explicit curation.

If any identity field is missing, the mapped condition ID is scoped to its
source sample. Two `UNKNOWN` values do not establish experimental equivalence.
`condition_status` retains its old four-field completeness meaning;
`condition_identity_complete` reports the extended identity completeness.
Neither field is approval for cross-study integration. Conflicts still require
review; platform, batch, dose semantics, and matched biological samples need
study-specific curation.

The sidecar preserves observed values, and its dependent synthetic choices use
those values. It no longer assigns MG1655 genotypes to unspecified/other strains.
Temperature, oxygen, pH, and growth phase are never synthesized by this fixture.
The cohort size is an upper bound, so a small input can drive a full synthetic
simulation. The pipeline selects one sample (preferring explicit MG1655, then
observed metadata), records it in `simulation_context.json`, and shares that
context across synthetic agents. `--sample-id` selects a sample from the
exported cohort. Sharing a context does not create new biological observations.

## Changed results and remaining research work

Local acceptance run: 2,000 agents, 80 steps, seed 42. The 30-test suite,
including JSON Schema checks, passes. Additional full-size checks produced:

| Check | Result |
|---|---:|
| Initial contacts found by brute force | 9,368 |
| Initial contacts retained by grid | 9,368 |
| Agent spheres outside cell | 0 |
| Recorded events | 87,670 |
| NO_EFFECT / MODIFY / BIND | 86,891 / 493 / 286 |
| Complex member-enclosure violations | 0 / 286 |

These verify software contracts on synthetic fixtures, not biological fidelity.
The full external omics snapshot and a live browser rendering were not revalidated
in this acceptance run; replay payload semantics and JavaScript syntax were checked.

Old v0.1 counts (58,558 events, 237 complexes) are historical and are not an
acceptance target after fixing missing contacts and changing initialization.
No old observed data or historical result files need to be overwritten.

Before biological prediction, establish a curated MG1655 condition with matched
quantitative omics, real feature/accession mappings, localization evidence,
structure-derived or explicitly estimated sizes, and calibrated reaction
parameters. Add held-out experimental validation and uncertainty reporting.
Increasing agent count or provisioning a GPU does not establish those facts.

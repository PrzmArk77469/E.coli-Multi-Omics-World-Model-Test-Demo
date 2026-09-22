# Synthetic Condition Priors

## Scope

v0.2 uses one selected sample context per simulation and separate molecular
and condition origins. See [migration and boundaries](SCIENTIFIC_INTEGRITY.md).

The observed condition registry is intentionally sparse. Synthetic priors exist
only to exercise the condition-aware Demo workflow and expose missing interface
contracts. They are not biological measurements and must not be reported as
observed metadata.

The implementation is
`src/ecoli_world/synthetic_conditions.py`.

## Hard separation

The synthetic layer never edits `unified_sample_map.tsv.gz`.

Observed and synthesized values are written to separate files:

```text
observed:
  unified_sample_map.tsv.gz

synthetic:
  synthetic_condition_fill.tsv.gz

explicitly joined for the Demo:
  demo_condition_contexts.tsv
```

Every synthetic record carries:

- `synthetic_reason=missing_source_attribute`;
- `generation_method=deterministic_condition_fixture_v2`;
- the fixed `generation_seed`;
- `confidence=0.25`;
- `synthetic_fields_json`;
- provenance identifying the observed source sample.

The effective condition ID uses the `ECOLI_DC_` prefix. It is a Demo
condition ID and is not interchangeable with an observed `ECOLI_C_` ID.

## Deterministic priors

The generator uses a SHA256-based deterministic choice for each sample and
field. Changing row order does not change an individual sample's values.

| Field | Candidate domain |
|---|---|
| Medium | LB, LB Lennox, M9 + glucose, M9 + glycerol, MOPS |
| Genotype | MG1655 wild-type, `delta-lacZ`, `delta-lacI`, `delta-crp`, `relA spoT`; BW25113 analogues when strain is known |
| Treatment | none, IPTG, glucose limitation, heat shock |
| Timepoint | 0, 5, 10, 20, 30, 60 min |
| Replicate | rep1, rep2, rep3 |

Biological constraints are deliberately simple and reviewable:

- `delta-lacZ` and `delta-lacI` increase the prior probability of IPTG.
- `delta-crp` increases the prior probability of glucose limitation.
- Minimal medium shifts timepoints toward later sampling.
- Heat shock uses short 5-30 minute timepoints.
- Existing observed fields are always preserved and never resampled.

These are workflow-testing priors, not calibrated causal parameters.

## Run the complete Demo

```bash
cd /mnt/d/CodexApp/Project13/Git
PYTHONPATH=src python3 -m ecoli_world.demo_pipeline \
  --observed-map /mnt/d/CodexApp/Project13/EcoliOmics/integrated/condition_completion/unified_sample_map.tsv.gz \
  --output-dir /mnt/d/CodexApp/Project13/EcoliOmics/integrated/condition_completion/demo_full \
  --agents 2000 \
  --steps 80 \
  --seed 42
```

The command:

1. reads observed samples;
2. writes missing-field priors to a sidecar;
3. selects a deterministic, source-stratified Demo cohort;
4. selects one source sample from that cohort and shares its context across all synthetic agents;
5. runs the event engine;
6. writes event, agent-context, summary, manifest, and synthetic-provenance
   files;
7. exports the replay viewer and its generated browser payload.

For the full 602,778-row sidecar, file writes through `/mnt/d` are I/O-bound.
The verified full build used native Windows Python. Ubuntu remains the required
environment for tests and small Demo runs; a future full WSL run should place
the temporary data tree on the Linux ext4 VHDX and publish only the final
artifacts back to the project data tree.

## Historical v0.1 verified run

The old local seed-42 run completed with the following values. These are not
v0.2 acceptance targets; contact detection, geometry, and context selection
have changed:

```text
source rows:                  602,778
synthetic sidecar rows:       602,778
demo contexts:                  2,000
agents with condition context:  2,000
unique effective conditions:      415
DATA_ORIGIN=MIXED:                119
DATA_ORIGIN=SYNTHETIC:          1,881
events:                         58,558
NO_EFFECT:                      57,928
MODIFY:                            393
BIND:                              237
complexes:                         237
```

Source-stratified contexts:

```text
ENA:                       1,804
MetaboLights:                176
Metabolomics Workbench:       20
```

## Replay visualization

The run above produced:

```text
D:\CodexApp\Project13\EcoliOmics\integrated\condition_completion\
  demo_full\visualization\demo_visualization.html
```

Serve the generated `visualization` directory over local HTTP and open
`demo_visualization.html`. The viewer uses the bundled Three.js and Lucide
files in `visualizations/vendor`; network access is not required after the
files have been generated.

The controls provide:

- play, pause, previous/next step, and reset;
- direct timeline navigation across the 80-step run;
- highlighting for `NO_EFFECT`, `MODIFY`, `BIND`, and generated complexes;
- coloring by agent type, data origin, or condition source;
- hover summaries and click-through detail for individual agents.

The page was browser-verified with WebGL at step 1: 1,606 active agents, 4,079
cumulative events, and 197 complexes were visible, with all four local icon
assets loaded. The generated viewer directory is a local reproducibility
artifact and is intentionally excluded from Git.

## Replacement rule

When a real source attribute is retrieved, it replaces the corresponding
synthetic field in the effective join without changing the synthetic sidecar
history. The next ENA BioSample expansion should therefore be judged by how
many Demo contexts move from `SYNTHETIC` toward `MIXED` or `OBSERVED`.

Before model training, synthetic rows require a separate ablation:

1. observed-only;
2. observed plus synthetic;
3. hold out synthetic-heavy conditions.

No claim of biological fidelity should be based on this fixture alone.

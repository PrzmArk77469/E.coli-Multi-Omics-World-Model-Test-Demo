# Minimal Simulation MVP

## Scope

The first simulation milestone is intentionally synthetic. It validates the
engineering loop rather than claiming calibrated biological predictions:

```text
agents
  -> spatial hash
  -> neighbor pairs
  -> event queue
  -> rule matching
  -> NO_EFFECT / MODIFY / BIND
  -> state changes, complex creation, event log
```

Every synthetic agent uses `source_ref` values beginning with
`synthetic://ecoli-mvp/`. Later data-derived agents must use source database
identifiers and versioned provenance instead.

## Five schemas

- `schemas/agent.schema.json`
- `schemas/behavior.schema.json`
- `schemas/rule.schema.json`
- `schemas/encounter.schema.json`
- `schemas/complex.schema.json`

## Run

From Ubuntu:

```bash
cd /mnt/d/CodexApp/Project13/Git
PYTHONPATH=src python3 -m ecoli_world.cli \
  --agents 2000 \
  --steps 80 \
  --seed 42 \
  --output artifacts/simulation_mvp
```

Outputs:

- `events.jsonl`: one encounter event per line
- `summary.json`: event totals, outcomes, active agents, and complexes
- `run_manifest.json`: configuration, rules, behaviors, and schema references

The command fails if any required outcome is absent unless
`--allow-missing-outcomes` is supplied.

## Tests

```bash
cd /mnt/d/CodexApp/Project13/Git
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The integration test creates 2,000 agents for 80 steps and requires all three
outcomes plus at least one complex.

## Current rules

- A synthetic active `Kinase` can modify an inactive `Target`.
- A synthetic free `ProteinA` and `ProteinB` can bind into `ComplexAB`.
- Other contacts produce a recorded `NO_EFFECT` event.

The rule probabilities and positions are fixtures, not scientific estimates.
Step 3 replaces incomplete metadata with a documented condition-mapping
architecture; Step 4 introduces clearly labeled biologically plausible
synthetic fixtures where source coverage is insufficient.

# Schemas

The minimal simulation uses five JSON Schema files:

- `agent.schema.json`
- `behavior.schema.json`
- `rule.schema.json`
- `encounter.schema.json`
- `complex.schema.json`

The Python dataclasses in `src/ecoli_world/models.py` provide the same core
contracts without adding a runtime schema-validation dependency. Schema files
are the interchange contract for later Parquet, API, and cloud workflows.

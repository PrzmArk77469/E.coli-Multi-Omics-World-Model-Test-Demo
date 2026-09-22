"""Command-line entry point for the minimal simulation."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .engine import SimulationConfig, SimulationEngine
from .io import JsonlEventWriter, write_json, write_spatial_records
from .provenance import build_provenance, prepare_output_dir, sha256_file
from .rules import default_behaviors, default_rules
from .synthetic_conditions import read_demo_contexts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the 2,000-agent E. coli world-model MVP.")
    parser.add_argument("--agents", type=int, default=2000)
    parser.add_argument("--steps", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("artifacts/simulation_mvp"))
    parser.add_argument("--condition-contexts", type=Path)
    parser.add_argument("--container-image", help="Immutable container image digest, when applicable")
    parser.add_argument(
        "--allow-missing-outcomes",
        action="store_true",
        help="Do not fail if NO_EFFECT, MODIFY, or BIND is absent.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output.resolve()
    prepare_output_dir(output_dir)

    config = SimulationConfig(agent_count=args.agents, steps=args.steps, seed=args.seed)
    rules = default_rules()
    behaviors = default_behaviors()
    condition_contexts = (
        read_demo_contexts(args.condition_contexts)
        if args.condition_contexts
        else None
    )
    provenance = build_provenance(asdict(config), [args.condition_contexts] if args.condition_contexts else [], args.container_image)
    events_path = output_dir / "events.jsonl"
    summary_path = output_dir / "summary.json"
    manifest_path = output_dir / "run_manifest.json"

    with JsonlEventWriter(events_path) as writer:
        engine = SimulationEngine(
            config=config,
            rules=rules,
            behaviors=behaviors,
            event_sink=writer.write,
            condition_contexts=condition_contexts,
        )
        result = engine.run()

    summary = result.to_summary_dict()
    summary["provenance"] = provenance
    spatial_files = write_spatial_records(output_dir, engine.agents, result.complexes)
    summary["spatial_files"] = spatial_files
    summary["events_file"] = str(events_path)
    summary["synthetic_notice"] = (
        "This run uses clearly labeled synthetic agents and rules for workflow validation, "
        "not calibrated biological predictions."
    )
    write_json(summary_path, summary)
    write_json(
        manifest_path,
        {
            "provenance": provenance,
            "artifacts": {
                name: {"path": path, "sha256": sha256_file(Path(path))}
                for name, path in {"events": str(events_path), **spatial_files}.items()
            },
            "config": result.to_summary_dict(),
            "rules": [rule.to_dict() for rule in rules],
            "behaviors": [behavior.to_dict() for behavior in behaviors],
            "condition_context_file": str(args.condition_contexts)
            if args.condition_contexts
            else "",
            "condition_context_count": len(condition_contexts or []),
            "schema_files": [
                "schemas/agent.schema.json",
                "schemas/behavior.schema.json",
                "schemas/rule.schema.json",
                "schemas/encounter.schema.json",
                "schemas/complex.schema.json",
            ],
        },
    )

    missing = [name for name, count in result.outcome_counts.items() if count == 0]
    if missing and not args.allow_missing_outcomes:
        raise SystemExit(f"Simulation did not produce required outcomes: {', '.join(missing)}")

    print(
        json.dumps(
            {
                "agents": config.agent_count,
                "steps": config.steps,
                "seed": config.seed,
                "events": result.event_count,
                "outcomes": result.outcome_counts,
                "complexes": result.complex_count,
                "active_agents": result.active_agents,
                "summary": str(summary_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

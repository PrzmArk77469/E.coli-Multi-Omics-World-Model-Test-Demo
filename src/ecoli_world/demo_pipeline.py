"""Run the condition-aware 2,000-agent Demo workflow end to end."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from .conditions import utc_now
from .engine import SimulationConfig, SimulationEngine
from .io import JsonlEventWriter, write_json, write_spatial_records
from .provenance import build_provenance, prepare_output_dir
from .rules import default_behaviors, default_rules
from .synthetic_conditions import (
    generate_synthetic_sidecar_and_contexts,
    read_demo_contexts,
    sha256_file,
)
from .visualization import export_visualization


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observed-map", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--agents", type=int, default=2000)
    parser.add_argument("--steps", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--log-dir", type=Path, default=Path("logs"))
    parser.add_argument("--sample-id", help="Choose a sample from the exported context cohort")
    parser.add_argument("--container-image", help="Immutable container image digest, when applicable")
    parser.add_argument("--allow-missing-outcomes", action="store_true")
    return parser


def write_agent_contexts(path: Path, engine: SimulationEngine) -> None:
    fields = (
        "agent_uid",
        "agent_type",
        "state_id",
        "unified_sample_id",
        "condition_id",
        "data_origin",
        "condition_data_origin",
        "source_ref",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for agent in engine.agents:
            writer.writerow(
                {
                    "agent_uid": agent.agent_uid,
                    "agent_type": agent.agent_type,
                    "state_id": agent.state_id,
                    "unified_sample_id": agent.unified_sample_id,
                    "condition_id": agent.condition_id,
                    "data_origin": agent.data_origin,
                    "condition_data_origin": agent.condition_data_origin,
                    "source_ref": agent.source_ref,
                }
            )


def select_simulation_context(contexts: list[dict[str, str]], sample_id: str | None = None) -> dict[str, str]:
    candidates = [context for context in contexts
                  if sample_id is None or context["unified_sample_id"] == sample_id]
    if not candidates:
        raise ValueError(f"sample not available in exported cohort: {sample_id}")
    # Choose one source sample. Metadata quality is a selection criterion, never
    # evidence that synthetic agents or their geometry were measured.
    return min(candidates, key=lambda row: (
        "mg1655" not in row.get("strain", "").casefold(),
        {"OBSERVED": 0, "MIXED": 1, "SYNTHETIC": 2}.get(row.get("data_origin", ""), 3),
        row["unified_sample_id"],
    ))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.resolve()
    prepare_output_dir(output_dir)

    synthetic_summary, contexts_path = generate_synthetic_sidecar_and_contexts(
        observed_map=args.observed_map,
        output_dir=output_dir,
        seed=args.seed,
        context_count=args.agents,
    )
    cohort = read_demo_contexts(contexts_path)
    selected_context = select_simulation_context(cohort, args.sample_id)
    contexts = [dict(selected_context) for _ in range(args.agents)]
    selected_context_path = output_dir / "simulation_context.json"
    write_json(selected_context_path, selected_context)
    config = SimulationConfig(
        agent_count=args.agents,
        steps=args.steps,
        seed=args.seed,
    )
    provenance = build_provenance({**asdict(config), "selected_sample_id": selected_context["unified_sample_id"]},
                                  [args.observed_map], args.container_image)
    rules = default_rules()
    behaviors = default_behaviors()
    simulation_dir = output_dir / "simulation"
    simulation_dir.mkdir(parents=True, exist_ok=True)
    events_path = simulation_dir / "events.jsonl"
    summary_path = simulation_dir / "summary.json"
    manifest_path = simulation_dir / "run_manifest.json"
    agent_contexts_path = simulation_dir / "agent_contexts.tsv"

    with JsonlEventWriter(events_path) as writer:
        engine = SimulationEngine(
            config=config,
            rules=rules,
            behaviors=behaviors,
            event_sink=writer.write,
            condition_contexts=contexts,
        )
        result = engine.run()
    write_agent_contexts(agent_contexts_path, engine)
    spatial_files = write_spatial_records(simulation_dir, engine.agents, result.complexes)
    visualization = export_visualization(
        output_dir=output_dir / "visualization",
        engine=engine,
        result=result,
        contexts=contexts,
        template_path=Path(__file__).resolve().parents[2]
        / "visualizations"
        / "demo_engine.html",
        provenance=provenance,
    )

    summary = result.to_summary_dict()
    summary.update(
        {
            "provenance": provenance,
            "selected_context_file": str(selected_context_path),
            "selected_sample_id": selected_context["unified_sample_id"],
            "context_reuse": "one source sample context shared by synthetic agents; not independent observations",
            "spatial_files": spatial_files,
            "events_file": str(events_path),
            "agent_contexts_file": str(agent_contexts_path),
            "contexts_file": str(contexts_path),
            "visualization_html": str(visualization["html"]),
            "visualization_data": str(visualization["data"]),
            "synthetic_fill": synthetic_summary,
            "synthetic_notice": (
                "Agents and molecular rules are synthetic workflow fixtures. "
                "Observed condition fields are preserved; missing fields use "
                "the separately labeled deterministic synthetic sidecar."
            ),
        }
    )
    write_json(summary_path, summary)
    write_json(
        manifest_path,
        {
            "provenance": provenance,
            "selected_context": selected_context,
            "artifacts": {
                name: {"path": str(path), "sha256": sha256_file(Path(path))}
                for name, path in {"events": events_path, "cohort": contexts_path,
                                   "agent_contexts": agent_contexts_path, **spatial_files}.items()
            },
            "config": result.to_summary_dict(),
            "rules": [rule.to_dict() for rule in rules],
            "behaviors": [behavior.to_dict() for behavior in behaviors],
            "condition_contexts": str(contexts_path),
            "agent_contexts": str(agent_contexts_path),
            "visualization_html": str(visualization["html"]),
            "visualization_data": str(visualization["data"]),
            "synthetic_fill_summary": synthetic_summary,
            "schema_files": [
                "schemas/agent.schema.json",
                "schemas/behavior.schema.json",
                "schemas/rule.schema.json",
                "schemas/encounter.schema.json",
                "schemas/complex.schema.json",
            ],
        },
    )
    verification = {
        "provenance": provenance,
        "generated_at": utc_now(),
        "seed": args.seed,
        "agents": args.agents,
        "conditioned_agents": result.conditioned_agents,
        "condition_count": result.condition_count,
        "events": result.event_count,
        "outcomes": result.outcome_counts,
        "complexes": result.complex_count,
        "events_sha256": sha256_file(events_path),
        "contexts_sha256": sha256_file(contexts_path),
        "sidecar_sha256": synthetic_summary["sidecar_sha256"],
        "visualization_data_sha256": str(visualization["data_sha256"]),
        "summary_file": str(summary_path),
        "manifest_file": str(manifest_path),
    }
    args.log_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        args.log_dir / f"condition-demo-{args.seed}-{provenance['run_id']}.json",
        verification,
    )

    missing = [
        name
        for name, count in result.outcome_counts.items()
        if count == 0
    ]
    if missing and not args.allow_missing_outcomes:
        raise SystemExit(
            f"Simulation did not produce required outcomes: {', '.join(missing)}"
        )
    print(
        json.dumps(
            {
                "agents": args.agents,
                "steps": args.steps,
                "seed": args.seed,
                "events": result.event_count,
                "outcomes": result.outcome_counts,
                "complexes": result.complex_count,
                "active_agents": result.active_agents,
                "conditioned_agents": result.conditioned_agents,
                "condition_count": result.condition_count,
                "data_origins": result.data_origin_counts,
                "contexts": str(contexts_path),
                "summary": str(summary_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Export a deterministic replay payload and browser viewer for the Demo."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .conditions import utc_now
from .engine import SimulationEngine, SimulationResult
from .synthetic_conditions import sha256_file


OUTCOME_CODES = {"NO_EFFECT": 0, "MODIFY": 1, "BIND": 2}
ORIGIN_CODES = {"OBSERVED": 0, "MIXED": 1, "SYNTHETIC": 2}


def build_visualization_payload(
    engine: SimulationEngine,
    result: SimulationResult,
    contexts: list[dict[str, str]],
) -> dict[str, Any]:
    condition_ids: dict[str, int] = {}
    conditions: list[dict[str, Any]] = []
    for context in contexts:
        condition_id = context.get("effective_condition_id", "")
        if not condition_id or condition_id in condition_ids:
            continue
        condition_ids[condition_id] = len(conditions)
        conditions.append(
            {
                "id": condition_id,
                "source": context.get("source", ""),
                "medium": context.get("medium", ""),
                "genotype": context.get("genotype", ""),
                "treatment": context.get("treatment", ""),
                "timepoint": context.get("timepoint", ""),
                "replicate": context.get("replicate", ""),
                "origin": context.get("data_origin", "SYNTHETIC"),
                "sample_id": context.get("unified_sample_id", ""),
            }
        )

    agents = []
    for agent in engine.agents:
        context = contexts[agent.agent_uid]
        agents.append(
            {
                "i": agent.agent_uid,
                "t": agent.agent_type,
                "x": round(agent.x, 5),
                "y": round(agent.y, 5),
                "z": round(agent.z, 5),
                "r": round(agent.r_eff, 5),
                "c": condition_ids.get(agent.condition_id, -1),
                "o": ORIGIN_CODES.get(agent.data_origin, 2),
                "a": int(agent.active),
                "w": agent.copy_weight,
            }
        )

    events = [
        {
            "s": event.step_index,
            "a": event.agent_a_uid,
            "b": event.agent_b_uid,
            "o": OUTCOME_CODES[event.outcome],
            "r": event.rule_id,
            "c": event.new_complex_uid or "",
        }
        for event in result.events
    ]
    complexes = [
        {
            "id": complex_model.complex_uid,
            "members": complex_model.member_agent_uids,
            "x": round(complex_model.representative_x, 5),
            "y": round(complex_model.representative_y, 5),
            "z": round(complex_model.representative_z, 5),
            "step": int(complex_model.created_at / engine.config.step_seconds),
        }
        for complex_model in result.complexes
    ]
    return {
        "schema": "ecoli-demo-visualization-v1",
        "generated_at": utc_now(),
        "notice": (
            "Synthetic molecular agents and rules for workflow validation; "
            "condition fields retain observed/synthetic provenance."
        ),
        "config": {
            "seed": engine.config.seed,
            "steps": engine.config.steps,
            "step_seconds": engine.config.step_seconds,
            "cell_length_um": engine.config.cell_length_um,
            "cell_radius_um": engine.config.cell_radius_um,
        },
        "summary": result.to_summary_dict(),
        "conditions": conditions,
        "agents": agents,
        "events": events,
        "complexes": complexes,
    }


def export_visualization(
    output_dir: Path,
    engine: SimulationEngine,
    result: SimulationResult,
    contexts: list[dict[str, str]],
    template_path: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = build_visualization_payload(engine, result, contexts)
    data_path = output_dir / "demo_visualization_data.js"
    html_path = output_dir / "demo_visualization.html"
    data_path.write_text(
        "window.ECOLI_DEMO = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    shutil.copyfile(template_path, html_path)
    vendor_source = template_path.parent / "vendor"
    if vendor_source.exists():
        shutil.copytree(
            vendor_source,
            output_dir / "vendor",
            dirs_exist_ok=True,
        )
    return {
        "html": html_path,
        "data": data_path,
        "data_sha256": sha256_file(data_path),
    }

"""Regression checks on exported scientific contracts, not just file existence."""

import csv
import io
import json
import math
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecoli_world.cli import main as cli_main
from ecoli_world.conditions import build_unified_condition_map
from ecoli_world.demo_pipeline import main as demo_main
from ecoli_world.provenance import sha256_file
from ecoli_world.synthetic_conditions import generate_synthetic_sidecar_and_contexts, synthetic_values

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None


def write_fixture(path: Path) -> None:
    fields = ["source", "study_accession", "sample_accession", "strain", "medium",
              "genotype", "treatment", "timepoint", "replicate", "temperature", "oxygen",
              "ph", "growth_phase"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields, delimiter="\t")
        writer.writeheader()
        # Test-only observations; these identifiers are not real database accessions.
        for i, source in enumerate(("ENA", "MetaboLights", "MetabolomicsWorkbench")):
            writer.writerow({"source": source, "study_accession": "TEST_ONLY",
                             "sample_accession": f"TEST_ONLY_{i}", "strain": "MG1655",
                             "medium": "LB", "genotype": "MG1655 wild-type", "treatment": "none",
                             "timepoint": "5 min", "replicate": str(i + 1), "temperature": "37 C",
                             "oxygen": "aerobic", "ph": "7", "growth_phase": "exponential"})


class ArtifactIntegrityTests(unittest.TestCase):
    def test_cli_exports_geometry_and_hashes_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "run"
            args = ["--agents", "100", "--steps", "10", "--output", str(output),
                    "--allow-missing-outcomes", "--container-image", "test-image@sha256:test-only"]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli_main(args), 0)
            manifest = json.loads((output / "run_manifest.json").read_text())
            self.assertEqual(manifest["provenance"]["random_seed"], 42)
            self.assertEqual(manifest["provenance"]["container_image"], "test-image@sha256:test-only")
            self.assertEqual(len(manifest["provenance"]["source_tree_sha256"]), 64)
            for artifact in manifest["artifacts"].values():
                self.assertEqual(artifact["sha256"], sha256_file(Path(artifact["path"])))
            agents = [json.loads(line) for line in (output / "agents.jsonl").read_text().splitlines()]
            self.assertEqual(len({a["agent_uid"] for a in agents}), 100)
            self.assertTrue(all(a["coordinate_unit"] == "um" and a["data_origin"] == "SYNTHETIC" for a in agents))
            self.assertTrue(all(math.isfinite(a[axis]) for a in agents for axis in ("x", "y", "z", "r_eff")))
            events_hash = sha256_file(output / "events.jsonl")
            with self.assertRaises(FileExistsError):
                cli_main(args)
            self.assertEqual(events_hash, sha256_file(output / "events.jsonl"))

    def test_mapping_to_demo_uses_one_context_and_preserves_input_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "fixture.tsv"
            write_fixture(source)
            build_unified_condition_map(source, root / "map")
            observed = root / "map" / "unified_sample_map.tsv.gz"
            before = sha256_file(observed)
            args = ["--observed-map", str(observed), "--agents", "50", "--steps", "5",
                    "--log-dir", str(root / "logs"), "--allow-missing-outcomes"]
            with redirect_stdout(io.StringIO()):
                demo_main([*args, "--output-dir", str(root / "demo1")])
                demo_main([*args, "--output-dir", str(root / "demo2")])
            self.assertEqual(before, sha256_file(observed))
            summaries = [json.loads((root / name / "simulation" / "summary.json").read_text())
                         for name in ("demo1", "demo2")]
            for summary in summaries:
                self.assertEqual(summary["condition_count"], 1)
                self.assertEqual(summary["data_origin_counts"], {"SYNTHETIC": 50})
                self.assertEqual(summary["condition_data_origin_counts"], {"OBSERVED": 50})
                self.assertEqual(summary["provenance"]["inputs"][0]["sha256"], before)
            self.assertEqual(len(list((root / "logs").glob("*.json"))), 2)
            for relative in ("synthetic_condition_fill.tsv.gz", "simulation/events.jsonl",
                             "simulation/agents.jsonl", "demo_condition_contexts.tsv"):
                self.assertEqual(sha256_file(root / "demo1" / relative), sha256_file(root / "demo2" / relative))

    def test_synthetic_dependencies_use_observed_values_and_do_not_invent_strain(self):
        row = {"unified_sample_id": "test", "strain": "W3110", "genotype": "known mutant",
               "medium": "M9 + glucose", "treatment": "heat shock"}
        values = synthetic_values(row, 42)
        self.assertEqual(values["genotype"], "known mutant")
        self.assertEqual(values["medium"], "M9 + glucose")
        self.assertEqual(values["treatment"], "heat shock")
        self.assertNotIn("MG1655", synthetic_values({"strain": "W3110"}, 42)["genotype"])

    def test_replay_uses_integer_event_steps_and_initial_states(self):
        from ecoli_world.engine import SimulationConfig, SimulationEngine
        from ecoli_world.visualization import build_visualization_payload
        engine = SimulationEngine(SimulationConfig(agent_count=200, steps=35))
        result = engine.run()
        payload = build_visualization_payload(engine, result, [{} for _ in engine.agents])
        by_complex = {event.new_complex_uid: event for event in result.events if event.new_complex_uid}
        for complex_record in payload["complexes"]:
            self.assertEqual(complex_record["step"], by_complex[complex_record["id"]].step_index)
            self.assertGreater(complex_record["r"], 0)
        for agent in payload["agents"]:
            if agent["t"] == "Target":
                self.assertEqual(agent["initial_state"], "inactive")

    @unittest.skipIf(Draft202012Validator is None, "install .[test] for JSON Schema validation")
    def test_exported_objects_conform_to_all_five_schemas(self):
        from ecoli_world.engine import SimulationConfig, SimulationEngine
        engine = SimulationEngine(SimulationConfig(agent_count=200, steps=10))
        result = engine.run()
        self.assertTrue(result.complexes)
        groups = {"agent": engine.agents, "complex": result.complexes, "encounter": result.events,
                  "behavior": engine.behaviors, "rule": engine.rules}
        for name, records in groups.items():
            schema = json.loads((ROOT / "schemas" / f"{name}.schema.json").read_text())
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema)
            for record in records:
                with self.subTest(schema=name):
                    validator.validate(record.to_dict())


if __name__ == "__main__":
    unittest.main()

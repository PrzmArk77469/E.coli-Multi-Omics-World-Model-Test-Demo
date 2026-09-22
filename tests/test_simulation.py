from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecoli_world.engine import SimulationConfig, SimulationEngine  # noqa: E402
from ecoli_world.events import EventQueue  # noqa: E402
from ecoli_world.models import Agent  # noqa: E402
from ecoli_world.spatial import UniformGrid  # noqa: E402


class SpatialHashTests(unittest.TestCase):
    def test_candidate_pairs_include_close_agents(self) -> None:
        grid = UniformGrid(cell_size=0.2)
        first = Agent(0, "species-a", "ProteinA", "free", "cytoplasm", 0.0, 0.0, 0.0, 0.05)
        second = Agent(1, "species-b", "ProteinB", "free", "cytoplasm", 0.1, 0.0, 0.0, 0.05)
        grid.insert(first)
        grid.insert(second)

        self.assertEqual(list(grid.candidate_pairs()), [(0, 1)])


class EventQueueTests(unittest.TestCase):
    def test_queue_deduplicates_and_orders_events(self) -> None:
        queue = EventQueue()
        self.assertTrue(queue.schedule(2, 3, 1, "rule_b"))
        self.assertFalse(queue.schedule(2, 1, 3, "rule_b"))
        self.assertTrue(queue.schedule(1, 4, 5, "rule_a"))

        first_batch = queue.pop_due(1)
        self.assertEqual(len(first_batch), 1)
        self.assertEqual(first_batch[0].rule_id, "rule_a")
        second_batch = queue.pop_due(2)
        self.assertEqual(len(second_batch), 1)
        self.assertEqual(second_batch[0].rule_id, "rule_b")


class SimulationTests(unittest.TestCase):
    def test_seed_is_reproducible(self) -> None:
        config = SimulationConfig(agent_count=500, steps=20, seed=7)
        first = SimulationEngine(config).run().to_summary_dict()
        second = SimulationEngine(config).run().to_summary_dict()
        self.assertEqual(first, second)

    def test_full_mvp_produces_all_required_outcomes(self) -> None:
        result = SimulationEngine(SimulationConfig(agent_count=2000, steps=80, seed=42)).run()
        self.assertGreater(result.outcome_counts["NO_EFFECT"], 0)
        self.assertGreater(result.outcome_counts["MODIFY"], 0)
        self.assertGreater(result.outcome_counts["BIND"], 0)
        self.assertGreater(result.complex_count, 0)
        self.assertLess(result.active_agents, 2000)

    def test_all_encounter_records_validate(self) -> None:
        result = SimulationEngine(SimulationConfig(agent_count=500, steps=20, seed=11)).run()
        for event in result.events:
            event.validate()
        for complex_model in result.complexes:
            complex_model.validate()

    def test_condition_contexts_are_attached_to_every_agent(self) -> None:
        contexts = [
            {
                "unified_sample_id": f"ECOLI_S_{index:04d}",
                "effective_condition_id": f"ECOLI_DC_{index % 3}",
                "data_origin": "MIXED" if index % 2 else "SYNTHETIC",
            }
            for index in range(100)
        ]
        result = SimulationEngine(
            SimulationConfig(agent_count=100, steps=10, seed=5),
            condition_contexts=contexts,
        ).run()
        self.assertEqual(result.conditioned_agents, 100)
        self.assertEqual(result.condition_count, 3)
        self.assertEqual(sum(result.data_origin_counts.values()), 100)


class SchemaTests(unittest.TestCase):
    def test_schema_files_are_valid_json(self) -> None:
        schema_dir = ROOT / "schemas"
        expected = {
            "agent.schema.json",
            "behavior.schema.json",
            "rule.schema.json",
            "encounter.schema.json",
            "complex.schema.json",
        }
        self.assertEqual({path.name for path in schema_dir.glob("*.schema.json")}, expected)
        for path in schema_dir.glob("*.schema.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertIn("properties", payload)


if __name__ == "__main__":
    unittest.main()

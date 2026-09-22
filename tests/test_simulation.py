from __future__ import annotations

import json
import math
import random
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecoli_world.engine import SimulationConfig, SimulationEngine  # noqa: E402
from ecoli_world.events import EventQueue  # noqa: E402
from ecoli_world.models import Agent  # noqa: E402
from ecoli_world.spatial import UniformGrid  # noqa: E402
from ecoli_world.geometry import contains_sphere, enclosing_sphere  # noqa: E402


class SpatialHashTests(unittest.TestCase):
    def test_cross_cell_pair_is_not_filtered_by_id_order(self) -> None:
        grid = UniformGrid(0.2)
        for uid, x in ((9, 0.19), (1, 0.21)):
            grid.insert(Agent(uid, str(uid), "ProteinA", "free", "cytoplasm", x, 0, 0, 0.045))
        self.assertEqual(list(grid.candidate_pairs()), [(1, 9)])

    def test_grid_matches_brute_force_after_relabeling_and_reordering(self) -> None:
        rng = random.Random(25)
        positions = [tuple(rng.uniform(-0.4, 0.4) for _ in range(3)) for _ in range(120)]
        expected = {(i, j) for i in range(120) for j in range(i + 1, 120)
                    if math.dist(positions[i], positions[j]) <= 0.15}
        for trial in range(3):
            labels = list(range(120))
            rng.shuffle(labels)
            by_id = {labels[i]: i for i in range(120)}
            grid = UniformGrid(0.15)
            order = list(range(120))
            rng.shuffle(order)
            for i in order:
                grid.insert(Agent(labels[i], str(i), "ProteinA", "free", "cytoplasm",
                                  *positions[i], 0.05))
            pairs = list(grid.candidate_pairs())
            self.assertEqual(len(pairs), len(set(pairs)))
            actual = {tuple(sorted((by_id[a], by_id[b]))) for a, b in pairs
                      if math.dist(positions[by_id[a]], positions[by_id[b]]) <= 0.15}
            self.assertEqual(actual, expected)

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
    def test_all_initial_spheres_fit_the_rendered_capsule(self) -> None:
        for seed in (0, 7, 42):
            config = SimulationConfig(seed=seed)
            engine = SimulationEngine(config)
            self.assertTrue(all(contains_sphere(a.position, a.r_eff, config.cell_length_um,
                                                config.cell_radius_um) for a in engine.agents))

    def test_invalid_geometry_and_insufficient_grid_are_rejected(self) -> None:
        for overrides in ({"cell_length_um": 0.8}, {"cell_radius_um": 0.04},
                          {"cell_size_um": 0.05}, {"step_seconds": float("nan")}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                SimulationEngine(SimulationConfig(**overrides))

    def test_seed_is_reproducible(self) -> None:
        config = SimulationConfig(agent_count=500, steps=20, seed=7)
        first = SimulationEngine(config).run().to_summary_dict()
        second = SimulationEngine(config).run().to_summary_dict()
        self.assertEqual(first, second)

    def test_full_mvp_produces_all_required_outcomes(self) -> None:
        engine = SimulationEngine(SimulationConfig(agent_count=2000, steps=80, seed=42))
        result = engine.run()
        self.assertGreater(result.outcome_counts["NO_EFFECT"], 0)
        self.assertGreater(result.outcome_counts["MODIFY"], 0)
        self.assertGreater(result.outcome_counts["BIND"], 0)
        self.assertGreater(result.complex_count, 0)
        self.assertLess(result.active_agents, 2000)
        for complex_model in result.complexes:
            center = (complex_model.representative_x, complex_model.representative_y,
                      complex_model.representative_z)
            for uid in complex_model.member_agent_uids:
                member = engine.agents_by_uid[uid]
                self.assertLessEqual(math.dist(center, member.position) + member.r_eff,
                                     complex_model.r_eff + 1e-12)

    def test_all_encounter_records_validate(self) -> None:
        result = SimulationEngine(SimulationConfig(agent_count=500, steps=20, seed=11)).run()
        for event in result.events:
            event.validate()
        for complex_model in result.complexes:
            complex_model.validate()

    def test_condition_contexts_are_attached_to_every_agent(self) -> None:
        contexts = [
            {
                "unified_sample_id": "ECOLI_S_sample",
                "effective_condition_id": "ECOLI_DC_condition",
                "data_origin": "OBSERVED",
            }
            for index in range(100)
        ]
        result = SimulationEngine(
            SimulationConfig(agent_count=100, steps=10, seed=5),
            condition_contexts=contexts,
        ).run()
        self.assertEqual(result.conditioned_agents, 100)
        self.assertEqual(result.condition_count, 1)
        self.assertEqual(result.data_origin_counts, {"SYNTHETIC": 100})
        self.assertEqual(result.condition_data_origin_counts, {"OBSERVED": 100})

    def test_different_sample_or_condition_cannot_share_one_simulation(self) -> None:
        for key in ("unified_sample_id", "effective_condition_id"):
            context = {"unified_sample_id": "s", "effective_condition_id": "c"}
            contexts = [context, {**context, key: "other"}]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "one simulation"):
                SimulationEngine(SimulationConfig(agent_count=2), condition_contexts=contexts)


class GeometryTests(unittest.TestCase):
    def test_minimum_envelope_for_separated_unequal_and_nested_members(self) -> None:
        for p1, r1, p2, r2 in (((0, 0, 0), 1, (4, 0, 0), 2),
                              ((0, 0, 0), 3, (1, 0, 0), 1),
                              ((0, 0, 0), 1, (0, 0, 0), 2)):
            center, radius = enclosing_sphere(p1, r1, p2, r2)
            self.assertLessEqual(math.dist(center, p1) + r1, radius + 1e-12)
            self.assertLessEqual(math.dist(center, p2) + r2, radius + 1e-12)
            self.assertAlmostEqual(radius, max(r1, r2, (math.dist(p1, p2) + r1 + r2) / 2))


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

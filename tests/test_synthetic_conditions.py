from __future__ import annotations

import csv
import gzip
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecoli_world.synthetic_conditions import (  # noqa: E402
    generate_synthetic_sidecar_and_contexts,
    synthetic_values,
)
from ecoli_world.demo_pipeline import main as demo_main  # noqa: E402


class SyntheticConditionTests(unittest.TestCase):
    def test_generation_is_deterministic_with_declared_domains(self) -> None:
        row = {
            "unified_sample_id": "ECOLI_S_test",
            "strain": "MG1655",
            "condition_text": "medium=M9 + glucose;genotype=MG1655 delta-lacZ",
        }
        first = synthetic_values(row, 42)
        second = synthetic_values(row, 42)
        self.assertEqual(first, second)
        self.assertIn(first["medium"], {"LB", "LB Lennox", "M9 + glucose", "M9 + glycerol", "MOPS"})
        self.assertIn(
            first["genotype"],
            {
                "MG1655 wild-type",
                "MG1655 delta-lacZ",
                "MG1655 delta-lacI",
                "MG1655 delta-crp",
                "MG1655 relA spoT",
            },
        )

    def test_sidecar_never_replaces_observed_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observed_map = root / "observed.tsv.gz"
            fields = [
                "unified_sample_id",
                "condition_id",
                "source",
                "source_record_id",
                "study_accession",
                "strain",
                "medium",
                "genotype",
                "treatment",
                "timepoint",
                "replicate",
                "condition_status",
                "condition_text",
            ]
            with gzip.open(observed_map, "wt", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
                writer.writeheader()
                writer.writerow(
                    {
                        "unified_sample_id": "ECOLI_S_test",
                        "condition_id": "ECOLI_C_test",
                        "source": "ENA",
                        "source_record_id": "S1",
                        "study_accession": "PRJ1",
                        "strain": "MG1655",
                        "medium": "LB",
                        "condition_status": "partial",
                        "condition_text": "medium=LB",
                    }
                )
            summary, contexts_path = generate_synthetic_sidecar_and_contexts(
                observed_map=observed_map,
                output_dir=root / "synthetic",
                seed=7,
                context_count=1,
            )
            self.assertEqual(summary["rows"], 1)
            self.assertEqual(summary["synthetic_field_counts"]["medium"], 0)
            with contexts_path.open("r", encoding="utf-8", newline="") as handle:
                context = next(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(context["medium"], "LB")
            self.assertEqual(context["medium_origin"], "OBSERVED")
            self.assertEqual(context["data_origin"], "MIXED")
            self.assertIn(
                "genotype",
                json.loads(context["synthetic_fields_json"]),
            )

    def test_conditioned_pipeline_runs_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observed_map = root / "observed.tsv.gz"
            fields = [
                "unified_sample_id",
                "condition_id",
                "source",
                "source_record_id",
                "study_accession",
                "strain",
                "medium",
                "genotype",
                "treatment",
                "timepoint",
                "replicate",
                "condition_status",
                "condition_text",
            ]
            with gzip.open(observed_map, "wt", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
                writer.writeheader()
                for index in range(2):
                    writer.writerow(
                        {
                            "unified_sample_id": f"ECOLI_S_test{index}",
                            "condition_id": f"ECOLI_C_test{index}",
                            "source": "ENA",
                            "source_record_id": f"S{index}",
                            "study_accession": "PRJ1",
                            "strain": "MG1655",
                            "medium": "LB" if index == 0 else "",
                            "condition_status": "partial",
                            "condition_text": "medium=LB" if index == 0 else "",
                        }
                    )
            with redirect_stdout(io.StringIO()):
                exit_code = demo_main(
                    [
                        "--observed-map",
                        str(observed_map),
                        "--output-dir",
                        str(root / "demo"),
                        "--log-dir",
                        str(root / "logs"),
                        "--agents",
                        "2",
                        "--steps",
                        "5",
                        "--seed",
                        "9",
                        "--allow-missing-outcomes",
                    ]
                )
            self.assertEqual(exit_code, 0)
            summary = json.loads(
                (root / "demo" / "simulation" / "summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(summary["conditioned_agents"], 2)
            self.assertTrue(
                (root / "demo" / "simulation" / "agent_contexts.tsv").exists()
            )
            self.assertTrue(
                (
                    root
                    / "demo"
                    / "visualization"
                    / "demo_visualization.html"
                ).exists()
            )
            self.assertTrue(
                (
                    root
                    / "demo"
                    / "visualization"
                    / "vendor"
                    / "three.min.js"
                ).exists()
            )


if __name__ == "__main__":
    unittest.main()

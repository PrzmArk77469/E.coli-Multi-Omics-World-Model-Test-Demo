from __future__ import annotations

import csv
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecoli_world.conditions import (  # noqa: E402
    build_unified_condition_map,
    canonical_timepoint,
    canonical_medium,
    canonical_treatment,
    make_condition_id,
    make_sample_id,
    map_sample_row,
    parse_biosample_xml,
)


BIOSAMPLE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<SAMPLE_SET>
  <SAMPLE accession="SAMD00019996">
    <TITLE>BHY189-1</TITLE>
    <SAMPLE_NAME>
      <TAXON_ID>511145</TAXON_ID>
      <SCIENTIFIC_NAME>Escherichia coli str. K-12 substr. MG1655</SCIENTIFIC_NAME>
    </SAMPLE_NAME>
    <DESCRIPTION>This strain was grown in Lennox LB to mid-exponential phase.</DESCRIPTION>
    <SAMPLE_ATTRIBUTES>
      <SAMPLE_ATTRIBUTE><TAG>strain</TAG><VALUE>BHY173</VALUE></SAMPLE_ATTRIBUTE>
      <SAMPLE_ATTRIBUTE><TAG>substrain</TAG><VALUE>MG1655</VALUE></SAMPLE_ATTRIBUTE>
      <SAMPLE_ATTRIBUTE><TAG>genotype</TAG><VALUE>MG1655 delta(mrr-hsdRMS-mcrB)</VALUE></SAMPLE_ATTRIBUTE>
      <SAMPLE_ATTRIBUTE><TAG>replicate</TAG><VALUE>2</VALUE></SAMPLE_ATTRIBUTE>
    </SAMPLE_ATTRIBUTES>
  </SAMPLE>
</SAMPLE_SET>
"""


class ConditionMappingTests(unittest.TestCase):
    def test_condition_ids_are_stable_and_ignore_replicate(self) -> None:
        first = make_condition_id(
            {
                "medium": "LB",
                "genotype": "MG1655",
                "treatment": "none",
                "timepoint": "30 min",
            }
        )
        second = make_condition_id(
            {
                "medium": "LB",
                "genotype": "MG1655",
                "treatment": "none",
                "timepoint": "30 min",
            }
        )
        self.assertEqual(first, second)
        self.assertNotEqual(first, make_condition_id({"medium": "M9 + glucose"}))
        self.assertNotEqual(
            make_sample_id("ENA", "SAMD00019996"),
            make_sample_id("ENA", "SAMD00019997"),
        )

    def test_timepoint_units_are_canonicalized(self) -> None:
        self.assertEqual(canonical_timepoint("2 h"), ("120 min", "120"))
        self.assertEqual(canonical_timepoint("30 minutes"), ("30 min", "30"))
        self.assertEqual(canonical_timepoint("unknown"), ("unknown", ""))

    def test_generic_source_name_does_not_collapse_distinct_samples(self) -> None:
        base = {
            "source": "MetaboLights",
            "study_accession": "MTBLS373",
            "sample_accession": "MTBLS373:cell lysate",
            "scientific_name": "Escherichia coli",
            "metadata_json": "{}",
        }
        first = map_sample_row({**base, "sample_name": "sample-1"})
        second = map_sample_row({**base, "sample_name": "sample-2"})
        self.assertNotEqual(
            first["unified_sample_id"],
            second["unified_sample_id"],
        )

    def test_biosample_xml_is_parsed_without_flattening(self) -> None:
        record = parse_biosample_xml(BIOSAMPLE_XML)
        self.assertEqual(record.accession, "SAMD00019996")
        self.assertEqual(record.taxon_id, "511145")
        self.assertEqual(record.attributes["replicate"], ["2"])

    def test_mapping_prefers_observed_biosample_fields(self) -> None:
        mapped = map_sample_row(
            {
                "source": "ENA",
                "study_accession": "PRJDB3140",
                "sample_accession": "SAMD00019996",
                "sample_name": "BHY189-1",
                "scientific_name": "Escherichia coli str. K-12 substr. MG1655",
                "strain": "MG1655",
                "omics_types": "transcriptomics",
                "metadata_json": "{}",
            },
            biosample_xml=BIOSAMPLE_XML,
        )
        self.assertEqual(mapped["medium"], "Lennox LB to mid-exponential phase")
        self.assertEqual(mapped["genotype"], "MG1655 delta(mrr-hsdRMS-mcrB)")
        self.assertEqual(mapped["replicate"], "rep2")
        self.assertEqual(mapped["condition_status"], "core")
        self.assertEqual(
            json.loads(mapped["field_origin_json"])["medium"][0]["origin"],
            "biosample.description:medium",
        )

    def test_condition_identity_preserves_each_experimental_dimension(self) -> None:
        base = {"source": "ENA", "sample_accession": "S1", "strain": "MG1655",
                "medium": "LB", "genotype": "wild type", "treatment": "0.1 mM IPTG",
                "timepoint": "10 min", "temperature": "37 C", "oxygen": "aerobic",
                "ph": "7", "growth_phase": "exponential"}
        original = map_sample_row(base)
        for key, value in {"strain": "BW25113", "treatment": "1 mM IPTG",
                           "medium": "LB + 0.2% glucose", "temperature": "42 C",
                           "oxygen": "anaerobic", "ph": "6", "growth_phase": "stationary"}.items():
            with self.subTest(key=key):
                self.assertNotEqual(original["condition_id"], map_sample_row({**base, key: value})["condition_id"])
        replicate = map_sample_row({**base, "sample_accession": "S2", "replicate": "2"})
        self.assertEqual(original["condition_id"], replicate["condition_id"])
        self.assertEqual(original["condition_identity_complete"], "true")

    def test_missing_conditions_are_scoped_to_source_sample(self) -> None:
        first = map_sample_row({"source": "ENA", "sample_accession": "S1", "medium": "LB"})
        second = map_sample_row({"source": "ENA", "sample_accession": "S2", "medium": "LB"})
        self.assertNotEqual(first["condition_id"], second["condition_id"])
        self.assertEqual(first["condition_identity_complete"], "false")
        missing = map_sample_row({"source": "ENA", "sample_accession": "S1", "treatment": "N/A"})
        self.assertEqual(missing["treatment"], "")

    def test_normalization_does_not_drop_units_doses_or_ranges(self) -> None:
        self.assertEqual(canonical_timepoint("5"), ("5", ""))
        self.assertEqual(canonical_timepoint("5-30 min"), ("5-30 min", ""))
        self.assertEqual(canonical_timepoint("-5 min"), ("-5 min", "-5"))
        self.assertNotEqual(canonical_medium("M9 + 0.2% glucose"), canonical_medium("M9 + 2% glucose"))
        self.assertNotEqual(canonical_treatment("0.1 mM IPTG"), canonical_treatment("1 mM IPTG"))

    def test_builder_writes_a_streamable_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sample_master = root / "sample_master.tsv.gz"
            fields = [
                "source",
                "study_accession",
                "sample_accession",
                "sample_name",
                "scientific_name",
                "strain",
                "omics_types",
                "condition",
                "treatment",
                "timepoint",
                "medium",
                "genotype",
                "replicate",
                "metadata_json",
            ]
            with gzip.open(sample_master, "wt", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
                writer.writeheader()
                writer.writerow(
                    {
                        "source": "ENA",
                        "study_accession": "PRJ1",
                        "sample_accession": "S1",
                        "scientific_name": "Escherichia coli",
                        "omics_types": "transcriptomics",
                        "condition": "medium=M9 + glucose;timepoint=20 min",
                    }
                )
            summary = build_unified_condition_map(
                sample_master=sample_master,
                output_dir=root / "mapped",
            )
            self.assertEqual(summary["rows"], 1)
            self.assertEqual(summary["unique_sample_ids"], 1)
            with gzip.open(
                root / "mapped" / "unified_sample_map.tsv.gz",
                "rt",
                encoding="utf-8",
                newline="",
            ) as handle:
                row = next(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(row["medium"], "M9 + glucose")
            self.assertEqual(row["timepoint"], "20 min")


if __name__ == "__main__":
    unittest.main()

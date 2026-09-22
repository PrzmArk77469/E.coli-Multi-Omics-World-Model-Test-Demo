"""Unified sample and condition mapping for E. coli omics metadata.

The mapper deliberately keeps observed metadata separate from any later
synthetic gap filling. Every normalized field carries its evidence, confidence,
and conflict state so a synthetic value can never be mistaken for a source
observation.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, TextIO
from .io import deterministic_gzip_text
from .provenance import build_provenance, prepare_output_dir, sha256_file


CONDITION_FIELDS = ("medium", "genotype", "treatment", "timepoint", "replicate")
CONTEXT_FIELDS = ("strain", "temperature", "oxygen", "ph", "growth_phase")
OBSERVED_FIELDS = CONDITION_FIELDS + CONTEXT_FIELDS
CONDITION_ID_FIELDS = ("medium", "genotype", "treatment", "timepoint") + CONTEXT_FIELDS
MAPPING_VERSION = "condition-map-v2"
DIRECT_FIELDS = (
    "condition",
    "treatment",
    "timepoint",
    "medium",
    "genotype",
    "replicate",
) + CONTEXT_FIELDS

BIOSAMPLE_TAG_ALIASES = {
    "strain": ("strain", "strain name"),
    "temperature": ("temperature", "growth temperature", "culture temperature"),
    "oxygen": ("oxygen", "oxygenation", "aeration", "oxygen availability"),
    "ph": ("ph", "culture ph", "growth ph"),
    "growth_phase": ("growth phase", "growth_phase", "phase"),
    "medium": (
        "growth medium",
        "growth_medium",
        "culture medium",
        "culture_medium",
        "medium",
        "media",
    ),
    "genotype": (
        "genotype",
        "strain genotype",
        "strain_genotype",
        "substrain",
        "sub_strain",
    ),
    "treatment": (
        "treatment",
        "experimental treatment",
        "experimental_treatment",
        "perturbation",
        "agent",
        "stress",
    ),
    "timepoint": (
        "timepoint",
        "time point",
        "time_point",
        "sampling time",
        "sampling_time",
        "time elapsed",
        "time_elapsed",
    ),
    "replicate": (
        "replicate",
        "biological replicate",
        "biological_replicate",
        "replicate number",
        "replicate_number",
    ),
}

FACTOR_ALIASES = {
    **BIOSAMPLE_TAG_ALIASES,
    "medium": BIOSAMPLE_TAG_ALIASES["medium"] + ("media", "culture condition"),
    "genotype": BIOSAMPLE_TAG_ALIASES["genotype"] + ("variant",),
    "treatment": BIOSAMPLE_TAG_ALIASES["treatment"] + ("condition",),
    "timepoint": BIOSAMPLE_TAG_ALIASES["timepoint"] + ("time",),
}

MUTATION_MARKERS = (
    "delta",
    "\u0394",
    "mutant",
    "mutation",
    "knockout",
    "deletion",
    "insertion",
    "::",
    "phage",
    "plasmid",
    "overexpress",
)


@dataclass(frozen=True, slots=True)
class BioSampleRecord:
    accession: str
    title: str
    description: str
    scientific_name: str
    taxon_id: str
    attributes: dict[str, list[str]]


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", text).strip()


def normalize_key(value: object) -> str:
    text = clean_text(value).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def stable_digest(*parts: object, length: int = 24) -> str:
    payload = "\x1f".join(clean_text(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


def make_sample_id(source: str, source_record_id: str) -> str:
    return f"ECOLI_S_{stable_digest(source, source_record_id)}"


def make_condition_id(values: dict[str, str], incomplete_scope: str = "") -> str:
    signature = {
        field: values.get(field) or "UNKNOWN" for field in CONDITION_ID_FIELDS
    }
    # Unknown attributes do not establish equivalence between source samples.
    if incomplete_scope and any(value == "UNKNOWN" for value in signature.values()):
        signature["incomplete_sample_scope"] = incomplete_scope
    payload = json.dumps(signature, sort_keys=True, ensure_ascii=True)
    return f"ECOLI_C_{stable_digest(MAPPING_VERSION, payload)}"


def canonical_timepoint(value: object) -> tuple[str, str]:
    text = clean_text(value)
    if not text:
        return "", ""
    numeric = re.fullmatch(
        r"(-?\d+(?:\.\d+)?)\s*(d|day|days|h|hr|hrs|hour|hours|m|min|mins|minute|minutes|s|sec|secs|second|seconds)",
        text,
        flags=re.IGNORECASE,
    )
    if numeric:
        amount = float(numeric.group(1))
        unit = numeric.group(2).casefold()
        if unit.startswith("d"):
            minutes = amount * 1440.0
        elif unit.startswith("h"):
            minutes = amount * 60.0
        elif unit.startswith("m"):
            minutes = amount
        else:
            minutes = amount / 60.0
        minutes = round(minutes, 6)
        minutes_text = f"{minutes:g}"
        return f"{minutes_text} min", minutes_text
    # Unitless values and intervals must not silently become minutes or points.
    return text, ""


def canonical_medium(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    # Exact aliases only: concentrations, supplements and qualifiers are evidence.
    aliases = {
        "lb": "LB", "luria bertani": "LB", "luria-bertani": "LB",
        "lennox lb": "LB Lennox", "lb lennox": "LB Lennox",
        "m9": "M9", "m9 + glucose": "M9 + glucose",
        "m9 + glycerol": "M9 + glycerol", "mops": "MOPS",
        "tb": "Terrific Broth", "terrific broth": "Terrific Broth",
    }
    return aliases.get(text.casefold(), text)


def canonical_treatment(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    lowered = text.casefold()
    if lowered in {"none", "control", "untreated", "no treatment"}:
        return "none"
    if lowered == "iptg":
        return "IPTG"
    if lowered in {"glucose limitation", "glucose starvation"}:
        return "glucose limitation"
    if lowered in {"heat shock", "heat stress"}:
        return "heat shock"
    return text


def canonical_genotype(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    lowered = text.casefold()
    if (
        ("escherichia coli" in lowered or lowered.startswith("e. coli"))
        and not any(marker in lowered for marker in MUTATION_MARKERS)
    ):
        return ""
    text = re.sub(r"\bdelta\b", "delta", text, flags=re.IGNORECASE)
    return text


def canonical_replicate(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    match = re.search(r"(?:rep(?:licate)?\s*)?(\d+)\b", text, re.IGNORECASE)
    if match:
        return f"rep{int(match.group(1))}"
    return text


def canonical_value(field: str, value: object) -> str:
    if field == "medium":
        return canonical_medium(value)
    if field == "genotype":
        return canonical_genotype(value)
    if field == "treatment":
        return canonical_treatment(value)
    if field == "timepoint":
        return canonical_timepoint(value)[0]
    if field == "replicate":
        return canonical_replicate(value)
    return clean_text(value)


def parse_biosample_xml(xml_text: str) -> BioSampleRecord:
    root = ET.fromstring(xml_text)
    sample = root.find(".//SAMPLE")
    if sample is None:
        raise ValueError("BioSample XML has no SAMPLE element")
    attributes: dict[str, list[str]] = defaultdict(list)
    for item in sample.findall("./SAMPLE_ATTRIBUTES/SAMPLE_ATTRIBUTE"):
        tag = clean_text(item.findtext("TAG"))
        value = clean_text(item.findtext("VALUE"))
        if tag and value:
            attributes[tag].append(value)
    return BioSampleRecord(
        accession=clean_text(sample.attrib.get("accession")),
        title=clean_text(sample.findtext("./TITLE")),
        description=clean_text(sample.findtext("./DESCRIPTION")),
        scientific_name=clean_text(sample.findtext("./SAMPLE_NAME/SCIENTIFIC_NAME")),
        taxon_id=clean_text(sample.findtext("./SAMPLE_NAME/TAXON_ID")),
        attributes=dict(attributes),
    )


def read_biosample_cache(cache_dir: Path | None, accession: str) -> str | None:
    if cache_dir is None or not accession:
        return None
    path = cache_dir / f"{accession}.xml"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def iter_tsv(path: Path) -> Iterator[dict[str, str]]:
    with _open_text(path) as handle:
        yield from csv.DictReader(handle, delimiter="\t")


class ObservationSet:
    def __init__(self) -> None:
        self._values: dict[str, dict[str, list[tuple[str, float]]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def add(
        self,
        field: str,
        value: object,
        origin: str,
        confidence: float,
    ) -> None:
        if clean_text(value).casefold() in {"unknown", "n/a", "na", "not available", "not provided", "missing"}:
            return
        canonical = canonical_value(field, value)
        if not canonical:
            return
        self._values[field][canonical].append((origin, confidence))

    def select(self, field: str) -> tuple[str, list[tuple[str, float]], list[str]]:
        candidates = self._values.get(field, {})
        if not candidates:
            return "", [], []
        ranked = sorted(
            candidates.items(),
            key=lambda item: (
                -max(confidence for _, confidence in item[1]),
                -len(item[1]),
                item[0],
            ),
        )
        selected_value, selected_evidence = ranked[0]
        conflicts = [value for value, _ in ranked[1:]]
        return selected_value, selected_evidence, conflicts


def parse_factor_values(value: object) -> dict[str, str]:
    text = clean_text(value)
    if not text:
        return {}
    output: dict[str, str] = {}
    for item in re.split(r"\||;", text):
        key, separator, raw_value = item.partition("=")
        if not separator:
            key, separator, raw_value = item.partition(":")
        if separator and clean_text(key) and clean_text(raw_value):
            output[clean_text(key)] = clean_text(raw_value)
    return output


def add_factor_observations(
    observations: ObservationSet,
    factors: dict[str, Any],
    origin_prefix: str,
) -> None:
    aliases = {
        normalize_key(alias): field
        for field, field_aliases in FACTOR_ALIASES.items()
        for alias in field_aliases
    }
    for key, value in factors.items():
        if isinstance(value, (dict, list)):
            continue
        field = aliases.get(normalize_key(key))
        if field:
            observations.add(field, value, f"{origin_prefix}:{key}", 0.70)


def add_metadata_observations(
    observations: ObservationSet,
    metadata_json: str,
) -> None:
    if not metadata_json:
        return
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError:
        return
    factors = metadata.get("factors")
    if isinstance(factors, dict):
        add_factor_observations(observations, factors, "metadata.factors")
    annotations = metadata.get("annotations")
    if isinstance(annotations, dict):
        add_factor_observations(observations, annotations, "metadata.annotations")


def derive_description_observations(
    observations: ObservationSet,
    description: str,
) -> None:
    text = clean_text(description)
    if not text:
        return
    genotype_match = re.search(
        r"genotype\s*[:\-]\s*([^.;]+)",
        text,
        flags=re.IGNORECASE,
    )
    if genotype_match:
        observations.add(
            "genotype",
            genotype_match.group(1),
            "biosample.description:genotype",
            0.55,
        )
    medium_match = re.search(
        r"(?:grown|growth|cultured|culture)\s+(?:in|on|with)\s+([^.;]+)",
        text,
        flags=re.IGNORECASE,
    )
    if medium_match:
        phrase = medium_match.group(1)
        if re.search(r"\bLB\b|Luria|Lennox|M9|MOPS|Terrific", phrase, re.IGNORECASE):
            observations.add(
                "medium",
                phrase,
                "biosample.description:medium",
                0.55,
            )
    timepoint_match = re.search(
        r"(?:at|after)\s+(\d+(?:\.\d+)?\s*(?:min|minutes?|h|hr|hrs|hours?))\b",
        text,
        flags=re.IGNORECASE,
    )
    if timepoint_match:
        observations.add(
            "timepoint",
            timepoint_match.group(1),
            "biosample.description:timepoint",
            0.55,
        )


def add_biosample_observations(
    observations: ObservationSet,
    xml_text: str,
) -> BioSampleRecord:
    record = parse_biosample_xml(xml_text)
    aliases = {
        normalize_key(alias): field
        for field, field_aliases in BIOSAMPLE_TAG_ALIASES.items()
        for alias in field_aliases
    }
    for tag, values in record.attributes.items():
        field = aliases.get(normalize_key(tag))
        if field:
            for value in values:
                normalized_tag = normalize_key(tag)
                confidence = 1.0
                if field == "genotype" and normalized_tag in {
                    "substrain",
                    "sub strain",
                }:
                    confidence = 0.75
                observations.add(
                    field,
                    value,
                    f"biosample:{tag}",
                    confidence,
                )
    derive_description_observations(observations, record.description)
    return record


def map_sample_row(
    row: dict[str, str],
    biosample_xml: str | None = None,
) -> dict[str, Any]:
    observations = ObservationSet()
    for field in DIRECT_FIELDS:
        if field == "condition":
            factors = parse_factor_values(row.get(field))
            add_factor_observations(observations, factors, "sample_master.condition")
        elif clean_text(row.get(field)):
            observations.add(
                field,
                row.get(field),
                f"sample_master:{field}",
                0.80,
            )

    add_metadata_observations(observations, row.get("metadata_json", ""))
    biosample = None
    if biosample_xml:
        biosample = add_biosample_observations(observations, biosample_xml)

    values: dict[str, str] = {}
    origin: dict[str, list[dict[str, object]]] = {}
    conflicts: dict[str, list[str]] = {}
    confidences: list[float] = []
    for field in OBSERVED_FIELDS:
        selected, evidence, field_conflicts = observations.select(field)
        values[field] = selected
        if evidence:
            origin[field] = [
                {"origin": item_origin, "confidence": item_confidence}
                for item_origin, item_confidence in evidence
            ]
            confidences.append(max(item_confidence for _, item_confidence in evidence))
        if field_conflicts:
            conflicts[field] = field_conflicts

    source = clean_text(row.get("source"))
    source_record_id = clean_text(row.get("sample_accession"))
    if not source_record_id:
        source_record_id = clean_text(row.get("sample_name"))
    sample_name = clean_text(row.get("sample_name"))
    source_record_key = source_record_id
    if sample_name and sample_name != source_record_id:
        source_record_key = f"{source_record_id}|{sample_name}"
    if not source_record_id:
        source_record_key = stable_digest(
            row.get("study_accession"), row.get("sample_name")
        )
        source_record_id = source_record_key
    unified_sample_id = make_sample_id(source, source_record_key)
    condition_id = make_condition_id(values, incomplete_scope=unified_sample_id)
    observed_field_count = sum(bool(values[field]) for field in CONDITION_FIELDS)
    if all(values[field] for field in ("medium", "genotype", "treatment", "timepoint")):
        condition_status = "complete"
    elif values["medium"] and values["genotype"]:
        condition_status = "core"
    elif observed_field_count:
        condition_status = "partial"
    else:
        condition_status = "missing"

    timepoint, timepoint_minutes = canonical_timepoint(values["timepoint"])
    values["timepoint"] = timepoint
    condition_text = ";".join(
        f"{field}={values[field] or 'UNKNOWN'}"
        for field in CONDITION_FIELDS
        if values[field] or field in CONDITION_ID_FIELDS
    )
    provenance = {
        "source": source,
        "source_record_id": source_record_id,
        "source_record_key": source_record_key,
        "study_accession": clean_text(row.get("study_accession")),
        "mapping_version": MAPPING_VERSION,
    }
    if biosample:
        provenance["biosample"] = {
            "accession": biosample.accession,
            "taxon_id": biosample.taxon_id,
            "scientific_name": biosample.scientific_name,
        }
    return {
        "unified_sample_id": unified_sample_id,
        "condition_id": condition_id,
        "source": source,
        "source_record_id": source_record_id,
        "study_accession": clean_text(row.get("study_accession")),
        "sample_name": clean_text(row.get("sample_name")),
        "scientific_name": clean_text(row.get("scientific_name")),
        **{field: values[field] for field in CONTEXT_FIELDS},
        "condition_identity_complete": str(all(values[field] for field in CONDITION_ID_FIELDS)).lower(),
        "condition_mapping_version": MAPPING_VERSION,
        "omics_types": clean_text(row.get("omics_types")),
        "medium": values["medium"],
        "genotype": values["genotype"],
        "treatment": values["treatment"],
        "timepoint": values["timepoint"],
        "timepoint_minutes": timepoint_minutes,
        "replicate": values["replicate"],
        "condition_status": condition_status,
        "observed_field_count": observed_field_count,
        "confidence": round(sum(confidences) / len(confidences), 4)
        if confidences
        else 0.0,
        "field_origin_json": json.dumps(origin, sort_keys=True, separators=(",", ":")),
        "conflicts_json": json.dumps(conflicts, sort_keys=True, separators=(",", ":")),
        "condition_text": condition_text,
        "provenance_json": json.dumps(
            provenance, sort_keys=True, separators=(",", ":")
        ),
    }


OUTPUT_FIELDS = (
    "unified_sample_id",
    "condition_id",
    "source",
    "source_record_id",
    "source_record_key",
    "study_accession",
    "sample_name",
    "scientific_name",
    "strain",
    "temperature",
    "oxygen",
    "ph",
    "growth_phase",
    "condition_identity_complete",
    "condition_mapping_version",
    "omics_types",
    "medium",
    "genotype",
    "treatment",
    "timepoint",
    "timepoint_minutes",
    "replicate",
    "condition_status",
    "observed_field_count",
    "confidence",
    "field_origin_json",
    "conflicts_json",
    "condition_text",
    "provenance_json",
)


def build_unified_condition_map(
    sample_master: Path,
    output_dir: Path,
    biosample_cache: Path | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    prepare_output_dir(output_dir)
    output_path = output_dir / "unified_sample_map.tsv.gz"
    summary_path = output_dir / "condition_mapping_summary.json"
    source_counts: Counter = Counter()
    status_counts: Counter = Counter()
    field_counts: Counter = Counter()
    sample_ids: set[str] = set()
    condition_ids: set[str] = set()
    biosample_matches = 0
    rows = 0
    biosample_inputs: set[Path] = set()
    with deterministic_gzip_text(output_path) as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, delimiter="\t")
        writer.writeheader()
        for row in iter_tsv(sample_master):
            accession = clean_text(row.get("sample_accession"))
            xml_text = read_biosample_cache(biosample_cache, accession)
            if xml_text is not None and biosample_cache:
                biosample_inputs.add(biosample_cache / f"{accession}.xml")
            mapped = map_sample_row(row, biosample_xml=xml_text)
            writer.writerow(mapped)
            rows += 1
            source_counts[mapped["source"]] += 1
            status_counts[mapped["condition_status"]] += 1
            for field in CONDITION_FIELDS:
                field_counts[field] += int(bool(mapped[field]))
            sample_ids.add(mapped["unified_sample_id"])
            condition_ids.add(mapped["condition_id"])
            biosample_matches += int(xml_text is not None)
            if limit is not None and rows >= limit:
                break

    summary = {
        "provenance": build_provenance({"mapping_version": MAPPING_VERSION, "limit": limit,
                                        "seed": None}, [sample_master, *sorted(biosample_inputs)]),
        "output_sha256": sha256_file(output_path),
        "generated_at": utc_now(),
        "input": str(sample_master),
        "output": str(output_path),
        "biosample_cache": str(biosample_cache) if biosample_cache else "",
        "mapping_version": MAPPING_VERSION,
        "rows": rows,
        "unique_sample_ids": len(sample_ids),
        "unique_condition_ids": len(condition_ids),
        "sources": dict(source_counts),
        "condition_status": dict(status_counts),
        "field_completeness": {
            field: round(field_counts[field] / rows, 4) if rows else 0.0
            for field in CONDITION_FIELDS
        },
        "biosample_cache_matches": biosample_matches,
        "separation_rule": (
            "Observed values only. Synthetic gap filling must be written to a "
            "separate sidecar and joined explicitly."
        ),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-master", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--biosample-cache", type=Path)
    parser.add_argument("--limit", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = build_unified_condition_map(
        sample_master=args.sample_master,
        output_dir=args.output_dir,
        biosample_cache=args.biosample_cache,
        limit=args.limit,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

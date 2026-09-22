"""Clearly labeled synthetic condition priors for workflow validation.

These values are not observations and must never overwrite the observed
condition registry. The generator uses deterministic, biologically plausible
priors so every Demo run can be reproduced from its seed.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import heapq
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Iterator, TextIO

from .conditions import (
    CONDITION_FIELDS,
    clean_text,
    iter_tsv,
    make_condition_id,
)


GENERATION_METHOD = "deterministic_biological_condition_prior_v1"
SYNTHETIC_CONFIDENCE = 0.25
SOURCE_QUOTAS = {
    "ENA": 1800,
    "MetaboLights": 180,
    "MetabolomicsWorkbench": 20,
}

MEDIA = (
    ("LB", 0.40),
    ("LB Lennox", 0.15),
    ("M9 + glucose", 0.25),
    ("M9 + glycerol", 0.12),
    ("MOPS", 0.08),
)
WILDTYPE_GENOTYPES = (
    ("MG1655 wild-type", 0.62),
    ("MG1655 delta-lacZ", 0.14),
    ("MG1655 delta-lacI", 0.12),
    ("MG1655 delta-crp", 0.08),
    ("MG1655 relA spoT", 0.04),
)
BW25113_GENOTYPES = (
    ("BW25113 wild-type", 0.65),
    ("BW25113 delta-lacZ", 0.15),
    ("BW25113 delta-lacI", 0.10),
    ("BW25113 delta-crp", 0.10),
)
TIMEPOINTS = (
    ("0 min", 0.06),
    ("5 min", 0.22),
    ("10 min", 0.23),
    ("20 min", 0.20),
    ("30 min", 0.19),
    ("60 min", 0.10),
)
TREATMENTS = (
    ("none", 0.70),
    ("IPTG", 0.15),
    ("glucose limitation", 0.10),
    ("heat shock", 0.05),
)
REPLICATES = (("rep1", 0.34), ("rep2", 0.33), ("rep3", 0.33))

SIDECAR_FIELDS = (
    "unified_sample_id",
    "observed_condition_id",
    "source",
    "source_record_id",
    "synthetic_medium",
    "synthetic_genotype",
    "synthetic_treatment",
    "synthetic_timepoint",
    "synthetic_replicate",
    "synthetic_fields_json",
    "synthetic_reason",
    "generation_method",
    "generation_seed",
    "confidence",
    "provenance_json",
)

CONTEXT_FIELDS = (
    "context_rank",
    "unified_sample_id",
    "observed_condition_id",
    "effective_condition_id",
    "source",
    "source_record_id",
    "study_accession",
    "strain",
    "medium",
    "genotype",
    "treatment",
    "timepoint",
    "replicate",
    "data_origin",
    "medium_origin",
    "genotype_origin",
    "treatment_origin",
    "timepoint_origin",
    "replicate_origin",
    "observed_condition_status",
    "synthetic_fields_json",
    "generation_method",
    "generation_seed",
    "confidence",
    "provenance_json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def _weighted_choice(
    options: Iterable[tuple[str, float]],
    unit: float,
) -> str:
    materialized = tuple(options)
    cursor = 0.0
    last_value = ""
    for value, weight in materialized:
        cursor += weight
        last_value = value
        if unit <= cursor:
            return value
    if not last_value:
        raise ValueError("weighted choice requires at least one option")
    return last_value


def _unit(seed: int, sample_id: str, field: str) -> float:
    payload = f"{seed}\x1f{sample_id}\x1f{field}".encode("utf-8")
    value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return value / float(2**64)


def _priority(seed: int, sample_id: str) -> int:
    payload = f"demo-context\x1f{seed}\x1f{sample_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _synthetic_genotype(row: dict[str, str], seed: int) -> str:
    strain = clean_text(row.get("strain")).casefold()
    sample_id = clean_text(row.get("unified_sample_id"))
    if "bw25113" in strain:
        return _weighted_choice(
            BW25113_GENOTYPES,
            _unit(seed, sample_id, "genotype"),
        )
    return _weighted_choice(
        WILDTYPE_GENOTYPES,
        _unit(seed, sample_id, "genotype"),
    )


def _synthetic_medium(row: dict[str, str], seed: int) -> str:
    sample_id = clean_text(row.get("unified_sample_id"))
    condition_text = clean_text(row.get("condition_text")).casefold()
    for medium in ("LB Lennox", "M9 + glycerol", "M9 + glucose", "M9", "LB"):
        if medium.casefold() in condition_text:
            if _unit(seed, sample_id, "medium-evidence") < 0.70:
                return medium
    return _weighted_choice(MEDIA, _unit(seed, sample_id, "medium"))


def _synthetic_treatment(
    genotype: str,
    seed: int,
    sample_id: str,
) -> str:
    lowered = genotype.casefold()
    unit = _unit(seed, sample_id, "treatment")
    if "delta-lacz" in lowered or "delta-laci" in lowered:
        options = (
            ("none", 0.30),
            ("IPTG", 0.55),
            ("glucose limitation", 0.05),
            ("heat shock", 0.10),
        )
    elif "delta-crp" in lowered:
        options = (
            ("none", 0.25),
            ("glucose limitation", 0.65),
            ("heat shock", 0.10),
        )
    else:
        options = TREATMENTS
    return _weighted_choice(options, unit)


def _synthetic_timepoint(
    treatment: str,
    medium: str,
    seed: int,
    sample_id: str,
) -> str:
    unit = _unit(seed, sample_id, "timepoint")
    lowered_treatment = treatment.casefold()
    if lowered_treatment == "heat shock":
        return _weighted_choice(
            (("0 min", 0.05), ("5 min", 0.25), ("10 min", 0.35), ("20 min", 0.25), ("30 min", 0.10)),
            unit,
        )
    if lowered_treatment == "iptg":
        return _weighted_choice(
            (("0 min", 0.08), ("5 min", 0.20), ("10 min", 0.17), ("20 min", 0.20), ("30 min", 0.20), ("60 min", 0.15)),
            unit,
        )
    if lowered_treatment == "glucose limitation" or medium.startswith("M9"):
        return _weighted_choice(
            (("0 min", 0.04), ("5 min", 0.12), ("10 min", 0.17), ("20 min", 0.23), ("30 min", 0.24), ("60 min", 0.20)),
            unit,
        )
    return _weighted_choice(TIMEPOINTS, unit)


def synthetic_values(
    row: dict[str, str],
    seed: int,
) -> dict[str, str]:
    sample_id = clean_text(row.get("unified_sample_id"))
    genotype = _synthetic_genotype(row, seed)
    medium = _synthetic_medium(row, seed)
    treatment = _synthetic_treatment(genotype, seed, sample_id)
    return {
        "medium": medium,
        "genotype": genotype,
        "treatment": treatment,
        "timepoint": _synthetic_timepoint(
            treatment,
            medium,
            seed,
            sample_id,
        ),
        "replicate": _weighted_choice(
            REPLICATES,
            _unit(seed, sample_id, "replicate"),
        ),
    }


def sidecar_row(
    observed: dict[str, str],
    synthetic: dict[str, str],
    seed: int,
) -> dict[str, Any]:
    missing = [
        field for field in CONDITION_FIELDS if not clean_text(observed.get(field))
    ]
    output = {
        "unified_sample_id": clean_text(observed.get("unified_sample_id")),
        "observed_condition_id": clean_text(observed.get("condition_id")),
        "source": clean_text(observed.get("source")),
        "source_record_id": clean_text(observed.get("source_record_id")),
        "synthetic_fields_json": json.dumps(
            missing,
            separators=(",", ":"),
        ),
        "synthetic_reason": "missing_source_attribute" if missing else "",
        "generation_method": GENERATION_METHOD if missing else "",
        "generation_seed": seed,
        "confidence": SYNTHETIC_CONFIDENCE if missing else 0.0,
        "provenance_json": json.dumps(
            {
                "kind": "synthetic_prior",
                "purpose": "demo_workflow_validation",
                "source_sample_id": clean_text(observed.get("unified_sample_id")),
                "observed_fields_preserved": [
                    field
                    for field in CONDITION_FIELDS
                    if clean_text(observed.get(field))
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    }
    for field in CONDITION_FIELDS:
        output[f"synthetic_{field}"] = (
            synthetic[field] if field in missing else ""
        )
    return output


def _context_from_rows(
    observed: dict[str, str],
    sidecar: dict[str, str],
) -> dict[str, Any]:
    synthetic_fields = set(json.loads(sidecar["synthetic_fields_json"] or "[]"))
    effective: dict[str, str] = {}
    for field in CONDITION_FIELDS:
        effective[field] = clean_text(observed.get(field)) or clean_text(
            sidecar.get(f"synthetic_{field}")
        )
    if not synthetic_fields:
        data_origin = "OBSERVED"
    elif len(synthetic_fields) == len(CONDITION_FIELDS):
        data_origin = "SYNTHETIC"
    else:
        data_origin = "MIXED"
    condition_id = make_condition_id(effective)
    effective_condition_id = condition_id.replace("ECOLI_C_", "ECOLI_DC_", 1)
    output: dict[str, Any] = {
        "unified_sample_id": clean_text(observed.get("unified_sample_id")),
        "observed_condition_id": clean_text(observed.get("condition_id")),
        "effective_condition_id": effective_condition_id,
        "source": clean_text(observed.get("source")),
        "source_record_id": clean_text(observed.get("source_record_id")),
        "study_accession": clean_text(observed.get("study_accession")),
        "strain": clean_text(observed.get("strain")),
        "data_origin": data_origin,
        "observed_condition_status": clean_text(
            observed.get("condition_status")
        ),
        "synthetic_fields_json": sidecar["synthetic_fields_json"],
        "generation_method": sidecar["generation_method"],
        "generation_seed": sidecar["generation_seed"],
        "confidence": sidecar["confidence"],
        "provenance_json": json.dumps(
            {
                "observed_map": "unified_sample_map.tsv.gz",
                "synthetic_sidecar": "synthetic_condition_fill.tsv.gz",
                "generation_method": GENERATION_METHOD,
                "generation_seed": sidecar["generation_seed"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    }
    for field in CONDITION_FIELDS:
        output[field] = effective[field]
        output[f"{field}_origin"] = (
            "SYNTHETIC_PRIOR_V1" if field in synthetic_fields else "OBSERVED"
        )
    return output


def _keep_priority(
    heap: list[tuple[int, str, int, dict[str, str], dict[str, str]]],
    limit: int,
    item: tuple[int, str, int, dict[str, str], dict[str, str]],
) -> None:
    if limit <= 0:
        return
    if len(heap) < limit:
        heapq.heappush(heap, item)
    elif item[0] > heap[0][0]:
        heapq.heapreplace(heap, item)


def generate_synthetic_sidecar_and_contexts(
    observed_map: Path,
    output_dir: Path,
    seed: int = 42,
    context_count: int = 2000,
) -> tuple[dict[str, Any], Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    sidecar_path = output_dir / "synthetic_condition_fill.tsv.gz"
    contexts_path = output_dir / "demo_condition_contexts.tsv"
    summary_path = output_dir / "synthetic_fill_summary.json"

    field_counts: Counter = Counter()
    origin_counts: Counter = Counter()
    rows = 0
    rows_with_synthetic = 0
    source_heaps: dict[str, list[Any]] = {
        source: [] for source in SOURCE_QUOTAS
    }
    global_heap: list[Any] = []

    with gzip.open(sidecar_path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=SIDECAR_FIELDS,
            delimiter="\t",
        )
        writer.writeheader()
        for index, observed in enumerate(iter_tsv(observed_map)):
            sample_id = clean_text(observed.get("unified_sample_id"))
            if not sample_id:
                continue
            synthetic = synthetic_values(observed, seed)
            mapped = sidecar_row(observed, synthetic, seed)
            writer.writerow(mapped)
            rows += 1
            missing = json.loads(mapped["synthetic_fields_json"] or "[]")
            rows_with_synthetic += int(bool(missing))
            field_counts.update(missing)
            origin_counts[
                "SYNTHETIC"
                if len(missing) == len(CONDITION_FIELDS)
                else "MIXED"
                if missing
                else "OBSERVED"
            ] += 1
            priority = _priority(seed, sample_id)
            item = (priority, sample_id, index, observed, mapped)
            _keep_priority(global_heap, context_count, item)
            source = clean_text(observed.get("source"))
            if source in source_heaps:
                _keep_priority(source_heaps[source], SOURCE_QUOTAS[source], item)

    selected: dict[str, tuple[Any, ...]] = {}
    for source, quota in SOURCE_QUOTAS.items():
        for item in sorted(source_heaps[source], key=lambda value: -value[0])[:quota]:
            selected[item[1]] = item
    for item in sorted(global_heap, key=lambda value: -value[0]):
        if len(selected) >= context_count:
            break
        selected.setdefault(item[1], item)
    if len(selected) < context_count:
        raise RuntimeError(
            f"only {len(selected)} demo contexts available, need {context_count}"
        )
    ranked = sorted(
        selected.values(),
        key=lambda item: (
            clean_text(item[3].get("source")),
            -item[0],
            item[1],
        ),
    )[:context_count]

    contexts: list[dict[str, Any]] = []
    for rank, item in enumerate(ranked, start=1):
        context = _context_from_rows(item[3], item[4])
        context["context_rank"] = rank
        contexts.append(context)
    with contexts_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=CONTEXT_FIELDS,
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(contexts)

    summary = {
        "observed_map": str(observed_map),
        "sidecar": str(sidecar_path),
        "sidecar_sha256": sha256_file(sidecar_path),
        "contexts": str(contexts_path),
        "rows": rows,
        "rows_with_synthetic_fields": rows_with_synthetic,
        "synthetic_field_counts": {
            field: field_counts[field] for field in CONDITION_FIELDS
        },
        "record_origin_counts": dict(origin_counts),
        "context_count": len(contexts),
        "context_source_counts": dict(Counter(item["source"] for item in contexts)),
        "context_data_origin_counts": dict(
            Counter(item["data_origin"] for item in contexts)
        ),
        "generation_seed": seed,
        "generation_method": GENERATION_METHOD,
        "synthetic_confidence": SYNTHETIC_CONFIDENCE,
        "guardrail": (
            "Synthetic values are isolated in a sidecar and never replace "
            "observed fields in unified_sample_map.tsv.gz."
        ),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary, contexts_path


def read_demo_contexts(path: Path) -> list[dict[str, str]]:
    with _open_text(path) as handle:
        return list(csv.DictReader(handle, delimiter="\t"))

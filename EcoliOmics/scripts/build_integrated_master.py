#!/usr/bin/env python3
"""Build sample, experiment and feature crosswalk tables from local sources."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "manifests" / "ecoli_catalog.sqlite"
INTEGRITY_MANIFEST = (
    ROOT / "reports" / "integrity" / "local_sha256_manifest.tsv.gz"
)
METABOLIGHTS_JSON = ROOT / "manifests" / "metabolights_ecoli_studies.jsonl.gz"
WORKBENCH_MANIFEST = (
    ROOT
    / "manifests"
    / "download_queue"
    / "metabolomics_workbench_ecoli_studies.tsv"
)
GFF = (
    ROOT
    / "reference"
    / "MG1655"
    / "NCBI"
    / "GCF_000005845.2"
    / "GCF_000005845.2_ASM584v2_genomic.gff.gz"
)
UNIPROT = (
    ROOT
    / "reference"
    / "MG1655"
    / "UniProt"
    / "uniprot_mg1655_UP000000625.tsv.gz"
)
INTEGRATED_DIR = ROOT / "integrated"
REPORT_DIR = ROOT / "reports" / "coverage"
SAMPLE_MASTER = INTEGRATED_DIR / "sample_master.tsv.gz"
EXPERIMENT_MASTER = INTEGRATED_DIR / "experiment_master.tsv.gz"
FEATURE_CROSSWALK = INTEGRATED_DIR / "feature_crosswalk.tsv.gz"
BUILD_REPORT = REPORT_DIR / "integration_build.json"
GAP_REPORT = REPORT_DIR / "integration_gaps.md"

SUMMARY_FIELDS = [
    "record_level",
    "source",
    "study_accession",
    "sample_accession",
    "sample_name",
    "project_accession",
    "strain",
    "scientific_name",
    "omics_types",
    "assay_types",
    "platform",
    "instrument_model",
    "condition",
    "treatment",
    "timepoint",
    "medium",
    "genotype",
    "replicate",
    "run_count",
    "run_accessions",
    "local_file_count",
    "local_bytes",
    "metadata_json",
    "license_status",
    "redistribution_status",
    "needs_manual_review",
]

EXPERIMENT_FIELDS = [
    "record_level",
    "source",
    "experiment_accession",
    "study_accession",
    "sample_accession",
    "project_accession",
    "run_accession",
    "title",
    "scientific_name",
    "strain",
    "omics_type",
    "assay_type",
    "platform",
    "instrument_model",
    "condition",
    "treatment",
    "timepoint",
    "medium",
    "genotype",
    "replicate",
    "local_file_count",
    "local_bytes",
    "download_status",
    "license_status",
    "redistribution_status",
    "needs_manual_review",
    "metadata_json",
]

FEATURE_FIELDS = [
    "locus_tag",
    "gene_name",
    "gene_synonyms",
    "chromosome",
    "start",
    "end",
    "strand",
    "protein_id",
    "uniprot_entry",
    "uniprot_entry_name",
    "uniprot_reviewed",
    "protein_name",
    "ec_number",
    "kegg_ids",
    "refseq_proteins",
    "ncbi_gene_ids",
    "go_terms",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def split_unique(value: str, separators: str = ";|") -> list[str]:
    if not value:
        return []
    pattern = f"[{re.escape(separators)}]"
    return list(dict.fromkeys(part.strip() for part in re.split(pattern, value) if part.strip()))


def compact_json(value: dict) -> str:
    cleaned = {key: item for key, item in value.items() if item not in ("", None, [], {})}
    return json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))


def read_workbench_manifest() -> dict[str, dict]:
    with WORKBENCH_MANIFEST.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            row["study_id"]: row
            for row in csv.DictReader(handle, delimiter="\t")
            if row.get("study_id")
        }


def read_metabolights_metadata() -> dict[str, dict]:
    records: dict[str, dict] = {}
    with gzip.open(METABOLIGHTS_JSON, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                records[item["accession"]] = item
    return records


def read_integrity_manifest() -> tuple[dict[str, dict], Counter]:
    by_accession: dict[str, dict] = {}
    license_counts: Counter = Counter()
    with gzip.open(
        INTEGRITY_MANIFEST, "rt", encoding="utf-8", newline=""
    ) as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            license_counts[row.get("license_status", "unknown")] += 1
            accession = row.get("accession") or ""
            if not accession:
                continue
            bucket = by_accession.setdefault(
                accession, {"files": 0, "bytes": 0}
            )
            bucket["files"] += 1
            bucket["bytes"] += int(row.get("size_bytes") or 0)
    return by_accession, license_counts


def add_nonempty(stats: Counter, row: dict, fields: list[str]) -> None:
    for field in fields:
        if clean(row.get(field)):
            stats[field] += 1


def build_ena_samples(
    con: sqlite3.Connection,
    writer: csv.DictWriter,
    local_index: dict[str, dict],
    stats: Counter,
) -> int:
    query = """
    SELECT
      sample_accession,
      group_concat(DISTINCT study_accession),
      min(tax_id),
      min(scientific_name),
      CASE
        WHEN sum(CASE WHEN strain_guess = 'MG1655' THEN 1 ELSE 0 END) > 0
          THEN 'MG1655'
        ELSE min(strain_guess)
      END AS strain,
      group_concat(DISTINCT omics_type),
      group_concat(DISTINCT library_strategy),
      count(*) AS run_count,
      group_concat(run_accession),
      sum(fastq_bytes),
      sum(read_count),
      sum(base_count),
      max(needs_manual_review)
    FROM runs
    WHERE sample_accession IS NOT NULL AND sample_accession != ''
    GROUP BY sample_accession
    """
    count = 0
    for row in con.execute(query):
        (
            sample_accession,
            studies,
            tax_id,
            scientific_name,
            strain,
            omics_types,
            assay_types,
            run_count,
            run_accessions,
            fastq_bytes,
            read_count,
            base_count,
            needs_review,
        ) = row
        runs = run_accessions.split(",") if run_accessions else []
        local_files = 0
        local_bytes = 0
        for run in runs:
            evidence = local_index.get(run)
            if evidence:
                local_files += evidence["files"]
                local_bytes += evidence["bytes"]
        output = {
            "record_level": "sample",
            "source": "ENA",
            "study_accession": studies or "",
            "sample_accession": sample_accession or "",
            "sample_name": "",
            "project_accession": "",
            "strain": clean(strain),
            "scientific_name": clean(scientific_name),
            "omics_types": (omics_types or "").replace(",", ";"),
            "assay_types": (assay_types or "").replace(",", ";"),
            "platform": "",
            "instrument_model": "",
            "condition": "",
            "treatment": "",
            "timepoint": "",
            "medium": "",
            "genotype": "",
            "replicate": "",
            "run_count": int(run_count or 0),
            "run_accessions": run_accessions or "",
            "local_file_count": local_files,
            "local_bytes": local_bytes,
            "metadata_json": compact_json(
                {
                    "tax_id": tax_id,
                    "fastq_bytes": fastq_bytes,
                    "read_count": read_count,
                    "base_count": base_count,
                    "catalog": CATALOG.name,
                }
            ),
            "license_status": "license_unverified",
            "redistribution_status": "blocked_until_reviewed",
            "needs_manual_review": int(needs_review or 0),
        }
        writer.writerow(output)
        stats["ENA"] += 1
        add_nonempty(
            stats,
            output,
            [
                "study_accession",
                "sample_accession",
                "strain",
                "scientific_name",
                "omics_types",
                "assay_types",
            ],
        )
        count += 1
    return count


def deduplicated_header(header: list[str]) -> list[str]:
    counts: Counter = Counter()
    output: list[str] = []
    for index, value in enumerate(header, start=1):
        name = clean(value) or f"column_{index}"
        counts[name] += 1
        output.append(name if counts[name] == 1 else f"{name}#{counts[name]}")
    return output


def read_delimited_rows(path: Path) -> tuple[list[str], list[dict]]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.reader(handle, delimiter="\t")
                header = deduplicated_header(next(reader))
                rows = [
                    dict(zip(header, values))
                    for values in reader
                    if any(clean(value) for value in values)
                ]
            return header, rows
        except UnicodeDecodeError:
            continue
    return [], []


def first_nonempty(row: dict, keys: list[str]) -> str:
    lowered = {key.lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if clean(value):
            return clean(value)
    return ""


def metabolights_license(metadata: dict) -> tuple[str, str]:
    value = clean(metadata.get("dataset_license"))
    if "cc by 4" in value.lower():
        return "open_attribution_cc_by_4_0", "allowed_with_attribution"
    if value:
        return "license_unverified", "blocked_until_reviewed"
    return "unknown", "blocked_until_reviewed"


def build_metabolights_samples(
    writer: csv.DictWriter,
    metadata: dict[str, dict],
    stats: Counter,
) -> int:
    count = 0
    root = ROOT / "raw" / "metabolomics" / "MetaboLights"
    for sample_path in sorted(root.glob("MTBLS*/s_MTBLS*.txt")):
        study_id = sample_path.parent.name
        study = metadata.get(study_id, {})
        license_status, redistribution = metabolights_license(study)
        _, rows = read_delimited_rows(sample_path)
        for source_row in rows:
            sample_id = first_nonempty(
                source_row, ["Source Name", "Sample Name"]
            )
            sample_name = first_nonempty(source_row, ["Sample Name", "Source Name"])
            scientific_name = first_nonempty(
                source_row,
                [
                    "Characteristics[Organism]",
                    "Characteristics[Organism Part]",
                ],
            )
            genotype = first_nonempty(
                source_row,
                [
                    "Characteristics[Genotype]",
                    "Characteristics[Variant]",
                ],
            )
            sample_source = first_nonempty(
                source_row,
                [
                    "Characteristics[Sample type]",
                    "Characteristics[Organism part]",
                ],
            )
            factor_values = {
                key: value
                for key, value in source_row.items()
                if key.startswith("Factor Value[") and clean(value)
            }
            output = {
                "record_level": "sample",
                "source": "MetaboLights",
                "study_accession": study_id,
                "sample_accession": f"{study_id}:{sample_id}" if sample_id else "",
                "sample_name": sample_name,
                "project_accession": "",
                "strain": "MG1655" if "mg1655" in study_id.lower() else "",
                "scientific_name": scientific_name,
                "omics_types": "metabolomics",
                "assay_types": "|".join(
                    clean(item.get("measurement"))
                    for item in study.get("assays", [])
                    if clean(item.get("measurement"))
                ),
                "platform": "|".join(
                    clean(item.get("platform"))
                    for item in study.get("assays", [])
                    if clean(item.get("platform"))
                ),
                "instrument_model": "",
                "condition": "|".join(
                    f"{key[13:-1]}={value}"
                    for key, value in factor_values.items()
                ),
                "treatment": "",
                "timepoint": factor_values.get("Factor Value[time elapsed]", ""),
                "medium": "",
                "genotype": genotype,
                "replicate": "",
                "run_count": 0,
                "run_accessions": "",
                "local_file_count": 0,
                "local_bytes": 0,
                "metadata_json": compact_json(
                    {
                        "sample_source": sample_source,
                        "factors": factor_values,
                        "annotations": source_row,
                        "sample_file": sample_path.relative_to(ROOT).as_posix(),
                    }
                ),
                "license_status": license_status,
                "redistribution_status": redistribution,
                "needs_manual_review": int(license_status == "license_unverified"),
            }
            writer.writerow(output)
            stats["MetaboLights"] += 1
            add_nonempty(
                stats,
                output,
                [
                    "study_accession",
                    "sample_accession",
                    "sample_name",
                    "scientific_name",
                    "condition",
                    "genotype",
                ],
            )
            count += 1
    return count


def build_workbench_samples(
    writer: csv.DictWriter,
    studies: dict[str, dict],
    stats: Counter,
) -> int:
    count = 0
    root = ROOT / "processed" / "metabolomics" / "MetabolomicsWorkbench"
    for path in sorted(root.glob("ST*_samples.tsv")):
        study_id = path.name.split("_", 1)[0]
        study = studies.get(study_id, {})
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for source_row in csv.DictReader(handle, delimiter="\t"):
                sample_id = (
                    source_row.get("mb_sample_id")
                    or source_row.get("local_sample_id")
                    or ""
                )
                factors = source_row.get("factors") or ""
                factor_values = {}
                for item in factors.split("|"):
                    name, separator, value = item.partition(":")
                    if separator:
                        factor_values[name.strip()] = value.strip()
                output = {
                    "record_level": "sample",
                    "source": "MetabolomicsWorkbench",
                    "study_accession": study_id,
                    "sample_accession": sample_id,
                    "sample_name": source_row.get("local_sample_id") or "",
                    "project_accession": "",
                    "strain": "",
                    "scientific_name": study.get("species") or "Escherichia coli",
                    "omics_types": "metabolomics",
                    "assay_types": study.get("analysis_type") or "",
                    "platform": study.get("analysis_type") or "",
                    "instrument_model": "",
                    "condition": factors,
                    "treatment": "",
                    "timepoint": factor_values.get("Time", ""),
                    "medium": "",
                    "genotype": factor_values.get("Genotype", ""),
                    "replicate": "",
                    "run_count": 0,
                    "run_accessions": "",
                    "local_file_count": 0,
                    "local_bytes": 0,
                    "metadata_json": compact_json(
                        {
                            "sample_source": source_row.get("sample_source"),
                            "factors": factor_values,
                            "raw_data": source_row.get("raw_data"),
                            "sample_file": path.relative_to(ROOT).as_posix(),
                        }
                    ),
                    "license_status": study.get("license_status") or "unknown",
                    "redistribution_status": study.get(
                        "redistribution_status"
                    )
                    or "review_required",
                    "needs_manual_review": 0,
                }
                writer.writerow(output)
                stats["MetabolomicsWorkbench"] += 1
                add_nonempty(
                    stats,
                    output,
                    [
                        "study_accession",
                        "sample_accession",
                        "sample_name",
                        "scientific_name",
                        "condition",
                        "genotype",
                        "timepoint",
                    ],
                )
                count += 1
    return count


def build_ena_experiments(
    con: sqlite3.Connection,
    writer: csv.DictWriter,
    local_index: dict[str, dict],
    stats: Counter,
) -> int:
    query = """
    SELECT
      run_accession, study_accession, sample_accession, tax_id,
      scientific_name, strain_guess, library_strategy, library_source,
      omics_type, omics_confidence, classification_reason,
      needs_manual_review, data_tier, license_status,
      fastq_bytes, read_count, base_count
    FROM runs
    """
    count = 0
    for row in con.execute(query):
        (
            run_accession,
            study_accession,
            sample_accession,
            tax_id,
            scientific_name,
            strain,
            library_strategy,
            library_source,
            omics_type,
            omics_confidence,
            classification_reason,
            needs_review,
            data_tier,
            license_status,
            fastq_bytes,
            read_count,
            base_count,
        ) = row
        evidence = local_index.get(run_accession, {"files": 0, "bytes": 0})
        output = {
            "record_level": "run",
            "source": "ENA",
            "experiment_accession": run_accession or "",
            "study_accession": study_accession or "",
            "sample_accession": sample_accession or "",
            "project_accession": "",
            "run_accession": run_accession or "",
            "title": "",
            "scientific_name": scientific_name or "",
            "strain": strain or "",
            "omics_type": omics_type or "",
            "assay_type": library_strategy or "",
            "platform": "",
            "instrument_model": "",
            "condition": "",
            "treatment": "",
            "timepoint": "",
            "medium": "",
            "genotype": "",
            "replicate": "",
            "local_file_count": evidence["files"],
            "local_bytes": evidence["bytes"],
            "download_status": "local" if evidence["files"] else "metadata_only",
            "license_status": license_status or "license_unverified",
            "redistribution_status": "blocked_until_reviewed",
            "needs_manual_review": int(needs_review or 0),
            "metadata_json": compact_json(
                {
                    "tax_id": tax_id,
                    "library_source": library_source,
                    "omics_confidence": omics_confidence,
                    "classification_reason": classification_reason,
                    "data_tier": data_tier,
                    "fastq_bytes": fastq_bytes,
                    "read_count": read_count,
                    "base_count": base_count,
                }
            ),
        }
        writer.writerow(output)
        stats["ENA"] += 1
        count += 1
    return count


def build_project_experiments(
    con: sqlite3.Connection,
    writer: csv.DictWriter,
    local_index: dict[str, dict],
    metabolights: dict[str, dict],
    workbench: dict[str, dict],
    stats: Counter,
) -> tuple[int, int, int]:
    pride_count = 0
    pride_query = """
    SELECT accession, title, organisms, publication_date, submission_date,
           submission_type, instruments, experiment_types, keywords, doi
    FROM pride_projects
    """
    for row in con.execute(pride_query):
        (
            accession,
            title,
            organisms,
            publication_date,
            submission_date,
            submission_type,
            instruments,
            experiment_types,
            keywords,
            doi,
        ) = row
        evidence = local_index.get(accession, {"files": 0, "bytes": 0})
        output = {
            "record_level": "project",
            "source": "PRIDE",
            "experiment_accession": accession or "",
            "study_accession": accession or "",
            "sample_accession": "",
            "project_accession": accession or "",
            "run_accession": "",
            "title": title or "",
            "scientific_name": organisms or "",
            "strain": "",
            "omics_type": "proteomics",
            "assay_type": experiment_types or "",
            "platform": instruments or "",
            "instrument_model": instruments or "",
            "condition": "",
            "treatment": "",
            "timepoint": "",
            "medium": "",
            "genotype": "",
            "replicate": "",
            "local_file_count": evidence["files"],
            "local_bytes": evidence["bytes"],
            "download_status": "local" if evidence["files"] else "metadata_only",
            "license_status": "license_unverified",
            "redistribution_status": "blocked_until_reviewed",
            "needs_manual_review": 1,
            "metadata_json": compact_json(
                {
                    "publication_date": publication_date,
                    "submission_date": submission_date,
                    "submission_type": submission_type,
                    "keywords": keywords,
                    "doi": doi,
                }
            ),
        }
        writer.writerow(output)
        stats["PRIDE"] += 1
        pride_count += 1

    metabolights_count = 0
    for study_id, study in sorted(metabolights.items()):
        license_status, redistribution = metabolights_license(study)
        evidence = local_index.get(study_id, {"files": 0, "bytes": 0})
        output = {
            "record_level": "study",
            "source": "MetaboLights",
            "experiment_accession": study_id,
            "study_accession": study_id,
            "sample_accession": "",
            "project_accession": "",
            "run_accession": "",
            "title": study.get("title") or "",
            "scientific_name": "Escherichia coli",
            "strain": "",
            "omics_type": "metabolomics",
            "assay_type": "|".join(
                clean(item.get("measurement"))
                for item in study.get("assays", [])
                if clean(item.get("measurement"))
            ),
            "platform": "|".join(
                clean(item.get("platform"))
                for item in study.get("assays", [])
                if clean(item.get("platform"))
            ),
            "instrument_model": "",
            "condition": "|".join(study.get("factors") or []),
            "treatment": "",
            "timepoint": "",
            "medium": "",
            "genotype": "",
            "replicate": "",
            "local_file_count": evidence["files"],
            "local_bytes": evidence["bytes"],
            "download_status": "local" if evidence["files"] else "metadata_only",
            "license_status": license_status,
            "redistribution_status": redistribution,
            "needs_manual_review": int(license_status == "license_unverified"),
            "metadata_json": compact_json(
                {
                    "study_status": study.get("study_status"),
                    "study_category": study.get("study_category"),
                    "dataset_license": study.get("dataset_license"),
                    "publication_date": study.get("publication_date"),
                    "submission_date": study.get("submission_date"),
                }
            ),
        }
        writer.writerow(output)
        stats["MetaboLights"] += 1
        metabolights_count += 1

    workbench_count = 0
    for study_id, study in sorted(workbench.items()):
        evidence = local_index.get(study_id, {"files": 0, "bytes": 0})
        output = {
            "record_level": "study",
            "source": "MetabolomicsWorkbench",
            "experiment_accession": study_id,
            "study_accession": study_id,
            "sample_accession": "",
            "project_accession": "",
            "run_accession": "",
            "title": study.get("study_title") or "",
            "scientific_name": study.get("species") or "Escherichia coli",
            "strain": "",
            "omics_type": "metabolomics",
            "assay_type": study.get("analysis_type") or "",
            "platform": study.get("analysis_type") or "",
            "instrument_model": "",
            "condition": "",
            "treatment": "",
            "timepoint": "",
            "medium": "",
            "genotype": "",
            "replicate": "",
            "local_file_count": evidence["files"],
            "local_bytes": evidence["bytes"],
            "download_status": "local" if evidence["files"] else "metadata_only",
            "license_status": study.get("license_status") or "unknown",
            "redistribution_status": study.get("redistribution_status")
            or "review_required",
            "needs_manual_review": 0,
            "metadata_json": compact_json(
                {
                    "number_of_samples": study.get("number_of_samples"),
                    "release_date": study.get("release_date"),
                    "license": study.get("license"),
                    "license_url": study.get("license_url"),
                    "study_url": study.get("study_url"),
                }
            ),
        }
        writer.writerow(output)
        stats["MetabolomicsWorkbench"] += 1
        workbench_count += 1
    return pride_count, metabolights_count, workbench_count


def parse_attributes(value: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for item in value.split(";"):
        key, separator, attr_value = item.partition("=")
        if separator:
            attributes[key.strip()] = attr_value.strip()
    return attributes


def append_unique(target: dict[str, set[str]], key: str, value: str) -> None:
    if key and value:
        target[key].add(value)


def build_feature_crosswalk(writer: csv.DictWriter) -> tuple[int, Counter]:
    genes: dict[str, dict] = {}
    uniprot_by_locus: dict[str, list[dict]] = defaultdict(list)
    uniprot_by_gene: dict[str, list[dict]] = defaultdict(list)
    stats: Counter = Counter()

    with gzip.open(GFF, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9 or fields[2] not in {"gene", "CDS"}:
                continue
            chromosome, _, feature, start, end, _, strand, _, raw_attributes = fields
            attributes = parse_attributes(raw_attributes)
            locus_tag = attributes.get("locus_tag") or ""
            if not locus_tag:
                continue
            gene = genes.setdefault(
                locus_tag,
                {
                    "locus_tag": locus_tag,
                    "gene_name": "",
                    "gene_synonyms": set(),
                    "chromosome": chromosome,
                    "start": start,
                    "end": end,
                    "strand": strand,
                    "protein_id": set(),
                    "uniprot_entry": set(),
                    "protein_name": set(),
                    "ncbi_gene_ids": set(),
                },
            )
            if feature == "gene":
                gene["gene_name"] = attributes.get("gene") or gene["gene_name"]
                for synonym in split_unique(
                    attributes.get("gene_synonym", ""), separators=","
                ):
                    gene["gene_synonyms"].add(synonym)
                for dbxref in attributes.get("Dbxref", "").split(","):
                    if dbxref.startswith("GeneID:"):
                        gene["ncbi_gene_ids"].add(dbxref.split(":", 1)[1])
            else:
                gene["protein_id"].add(attributes.get("protein_id", ""))
                gene["protein_name"].add(attributes.get("product", ""))
                for dbxref in attributes.get("Dbxref", "").split(","):
                    if dbxref.startswith("UniProtKB/Swiss-Prot:"):
                        gene["uniprot_entry"].add(dbxref.split(":", 1)[1])

    with gzip.open(UNIPROT, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            item = {
                "entry": row.get("Entry") or "",
                "entry_name": row.get("Entry Name") or "",
                "reviewed": row.get("Reviewed") or "",
                "protein_name": row.get("Protein names") or "",
                "gene_name": row.get("Gene Names (primary)") or "",
                "ec_number": row.get("EC number") or "",
                "kegg_ids": row.get("KEGG") or "",
                "refseq": row.get("RefSeq") or "",
                "go_terms": row.get("Gene Ontology (GO)") or "",
            }
            loci = split_unique(
                row.get("Gene Names (ordered locus)") or "",
                separators=";",
            )
            for locus in loci:
                for token in locus.split():
                    uniprot_by_locus[token].append(item)
            if item["gene_name"]:
                uniprot_by_gene[item["gene_name"]].append(item)

    count = 0
    seen_loci: set[str] = set()
    for locus_tag, gene in sorted(genes.items()):
        entries = uniprot_by_locus.get(locus_tag, [])
        if not entries and gene["gene_name"]:
            entries = uniprot_by_gene.get(gene["gene_name"], [])
        uniprot_entry = set(gene["uniprot_entry"])
        uniprot_entry_name = set()
        uniprot_reviewed = set()
        protein_name = set(gene["protein_name"])
        ec_number = set()
        kegg_ids = set()
        refseq_proteins = set()
        ncbi_gene_ids = set(gene["ncbi_gene_ids"])
        go_terms = set()
        for item in entries:
            uniprot_entry.add(item["entry"])
            uniprot_entry_name.add(item["entry_name"])
            uniprot_reviewed.add(item["reviewed"])
            protein_name.add(item["protein_name"])
            ec_number.update(split_unique(item["ec_number"], separators=";"))
            kegg_ids.update(split_unique(item["kegg_ids"], separators=";"))
            refseq_proteins.update(split_unique(item["refseq"], separators=";"))
            go_terms.update(split_unique(item["go_terms"], separators=";"))
        output = {
            "locus_tag": locus_tag,
            "gene_name": gene["gene_name"],
            "gene_synonyms": ";".join(sorted(gene["gene_synonyms"])),
            "chromosome": gene["chromosome"],
            "start": gene["start"],
            "end": gene["end"],
            "strand": gene["strand"],
            "protein_id": ";".join(sorted(gene["protein_id"])),
            "uniprot_entry": ";".join(sorted(uniprot_entry)),
            "uniprot_entry_name": ";".join(sorted(uniprot_entry_name)),
            "uniprot_reviewed": ";".join(sorted(uniprot_reviewed)),
            "protein_name": ";".join(sorted(protein_name)),
            "ec_number": ";".join(sorted(ec_number)),
            "kegg_ids": ";".join(sorted(kegg_ids)),
            "refseq_proteins": ";".join(sorted(refseq_proteins)),
            "ncbi_gene_ids": ";".join(sorted(ncbi_gene_ids)),
            "go_terms": ";".join(sorted(go_terms)),
        }
        writer.writerow(output)
        seen_loci.add(locus_tag)
        stats["uniprot_loci"] += int(bool(uniprot_entry))
        stats["protein_id_loci"] += int(bool(gene["protein_id"]))
        count += 1

    for entries in uniprot_by_locus.values():
        for item in entries:
            if item["entry"]:
                stats["uniprot_entries"] += 1
                break
    stats["uniprot_entries"] = len(
        {
            item["entry"]
            for entries in uniprot_by_locus.values()
            for item in entries
            if item["entry"]
        }
        | {
            item["entry"]
            for entries in uniprot_by_gene.values()
            for item in entries
            if item["entry"]
        }
    )
    stats["gff_loci"] = len(seen_loci)
    return count, stats


def completeness(stats: Counter, total: int) -> dict[str, float]:
    excluded = {"total", "ENA", "MetaboLights", "MetabolomicsWorkbench"}
    return {
        field: round(count / total, 4) if total else 0.0
        for field, count in sorted(stats.items())
        if field not in excluded
    }


def render_gap_report(
    sample_count: int,
    experiment_count: int,
    feature_count: int,
    sample_stats: Counter,
    experiment_stats: Counter,
    source_counts: Counter,
    feature_stats: Counter,
) -> None:
    missing_fields = [
        field
        for field in (
            "condition",
            "treatment",
            "timepoint",
            "medium",
            "genotype",
            "replicate",
        )
        if sample_stats.get(field, 0) / sample_count < 0.5
    ]
    lines = [
        "# Integration Gap Report",
        "",
        f"Generated: `{utc_now()}`",
        "",
        "## Outputs",
        "",
        f"- `sample_master.tsv.gz`: {sample_count:,} rows",
        f"- `experiment_master.tsv.gz`: {experiment_count:,} rows",
        f"- `feature_crosswalk.tsv.gz`: {feature_count:,} MG1655 loci",
        f"- Feature crosswalk UniProt entries represented: "
        f"{feature_stats.get('uniprot_entries', 0):,}",
        "",
        "## Record Sources",
        "",
        "| Source | Rows |",
        "|---|---:|",
    ]
    for source, count in source_counts.most_common():
        lines.append(f"| `{source}` | {count:,} |")
    lines.extend(
        [
            "",
            "## Highest-Priority Gaps",
            "",
            "The sample master is structurally complete, but most ENA records "
            "still lack experimental condition fields. The following fields are "
            "populated in fewer than half of all sample rows:",
            "",
        ]
    )
    for field in missing_fields:
        lines.append(
            f"- `{field}`: {sample_stats.get(field, 0):,}/{sample_count:,} "
            f"({sample_stats.get(field, 0) / sample_count:.1%})"
        )
    lines.extend(
        [
            "",
            "Recommended order:",
            "",
            "1. Resolve MG1655 and K-12 strain records before species-wide matching.",
            "2. Extract ENA BioSample attributes for medium, genotype, treatment, "
            "timepoint and replicate.",
            "3. Map processed proteomics and metabolomics sample names to the same "
            "sample or condition identifiers.",
            "4. Assign integration level `A`, `B` or `C` only after condition "
            "matching is explicit.",
            "",
            "No record in this report is promoted to an integrated cross-omics "
            "pair merely because accessions share the same study.",
        ]
    )
    GAP_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.workers != 1:
        print("workers=1 is used because SQLite exports are streamed", flush=True)

    for path in (
        CATALOG,
        INTEGRITY_MANIFEST,
        METABOLIGHTS_JSON,
        WORKBENCH_MANIFEST,
        GFF,
        UNIPROT,
    ):
        if not path.exists():
            raise SystemExit(f"missing required input: {path}")

    INTEGRATED_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    local_index, integrity_license_counts = read_integrity_manifest()
    metabolights = read_metabolights_metadata()
    workbench = read_workbench_manifest()
    con = sqlite3.connect(CATALOG)

    sample_stats: Counter = Counter()
    experiment_stats: Counter = Counter()
    source_counts: Counter = Counter()
    sample_count = 0
    experiment_count = 0

    with gzip.open(SAMPLE_MASTER, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=SUMMARY_FIELDS, delimiter="\t"
        )
        writer.writeheader()
        sample_count += build_ena_samples(con, writer, local_index, sample_stats)
        sample_count += build_metabolights_samples(
            writer, metabolights, sample_stats
        )
        sample_count += build_workbench_samples(
            writer, workbench, sample_stats
        )

    with gzip.open(
        EXPERIMENT_MASTER, "wt", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=EXPERIMENT_FIELDS, delimiter="\t"
        )
        writer.writeheader()
        experiment_count += build_ena_experiments(
            con, writer, local_index, experiment_stats
        )
        pride_count, metabolights_count, workbench_count = (
            build_project_experiments(
                con,
                writer,
                local_index,
                metabolights,
                workbench,
                experiment_stats,
            )
        )
        experiment_count += (
            pride_count + metabolights_count + workbench_count
        )

    feature_stats: Counter = Counter()
    with gzip.open(
        FEATURE_CROSSWALK, "wt", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=FEATURE_FIELDS, delimiter="\t"
        )
        writer.writeheader()
        feature_count, feature_stats = build_feature_crosswalk(writer)

    for source, count in sample_stats.items():
        if source in {
            "ENA",
            "MetaboLights",
            "MetabolomicsWorkbench",
        }:
            source_counts[source] += count

    report = {
        "generated_at": utc_now(),
        "inputs": {
            "catalog": CATALOG.relative_to(ROOT).as_posix(),
            "integrity_manifest": INTEGRITY_MANIFEST.relative_to(ROOT).as_posix(),
            "metabolights_metadata": METABOLIGHTS_JSON.relative_to(ROOT).as_posix(),
            "workbench_manifest": WORKBENCH_MANIFEST.relative_to(ROOT).as_posix(),
            "gff": GFF.relative_to(ROOT).as_posix(),
            "uniprot": UNIPROT.relative_to(ROOT).as_posix(),
        },
        "outputs": {
            "sample_master": SAMPLE_MASTER.relative_to(ROOT).as_posix(),
            "experiment_master": EXPERIMENT_MASTER.relative_to(ROOT).as_posix(),
            "feature_crosswalk": FEATURE_CROSSWALK.relative_to(ROOT).as_posix(),
            "gap_report": GAP_REPORT.relative_to(ROOT).as_posix(),
        },
        "rows": {
            "sample_master": sample_count,
            "experiment_master": experiment_count,
            "feature_crosswalk": feature_count,
        },
        "sample_sources": {
            key: sample_stats.get(key, 0)
            for key in ("ENA", "MetaboLights", "MetabolomicsWorkbench")
        },
        "experiment_sources": {
            key: experiment_stats.get(key, 0)
            for key in ("ENA", "PRIDE", "MetaboLights", "MetabolomicsWorkbench")
        },
        "sample_field_completeness": completeness(sample_stats, sample_count),
        "feature_crosswalk": dict(feature_stats),
        "integrity_license_counts": dict(sorted(integrity_license_counts.items())),
    }
    BUILD_REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    render_gap_report(
        sample_count,
        experiment_count,
        feature_count,
        sample_stats,
        experiment_stats,
        source_counts,
        feature_stats,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

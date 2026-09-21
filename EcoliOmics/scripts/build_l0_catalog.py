#!/usr/bin/env python3
"""Build the local L0 catalog from downloaded metadata manifests."""

from __future__ import annotations

import csv
import gzip
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


csv.field_size_limit(1024 * 1024 * 1024)

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "manifests" / "ecoli_catalog.sqlite"
ENA_MANIFEST = ROOT / "manifests" / "ena_all_runs.tsv.gz"
ENA_FILES_MANIFEST = ROOT / "manifests" / "ena_all_files.tsv.gz"
ENA_CONTEXT_MANIFEST = ROOT / "manifests" / "ena_all_context.tsv.gz"
ENA_MG1655_CONTEXT_MANIFEST = ROOT / "manifests" / "ena_mg1655_context.tsv.gz"
NCBI_COUNTS = ROOT / "reports" / "coverage" / "ncbi_counts.json"
PRIDE_MANIFEST = ROOT / "manifests" / "pride_ecoli_projects.tsv.gz"
COVERAGE = ROOT / "reports" / "coverage"
CLASSIFIER_VERSION = "rule_v2_strategy_taxonomy_2026_09"

OMICS_MAP = {
    "WGS": "genomics",
    "WGA": "genomics",
    "WCS": "genomics",
    "RAD-Seq": "genomics",
    "Synthetic-Long-Read": "genomics",
    "RNA-Seq": "transcriptomics",
    "ssRNA-seq": "transcriptomics",
    "ncRNA-Seq": "transcriptomics",
    "miRNA-Seq": "transcriptomics",
    "EST": "transcriptomics",
    "ChIP-Seq": "regulomics",
    "RIP-Seq": "regulomics",
    "SELEX": "regulomics",
    "MNase-Seq": "regulomics",
    "Tn-Seq": "functional_genomics",
    "Bisulfite-Seq": "methylomics",
    "MeDIP-Seq": "methylomics",
    "Hi-C": "structural_genomics",
    "ATAC-seq": "chromatin_accessibility",
    "AMPLICON": "amplicon",
    "Targeted-Capture": "targeted_sequencing",
    "WXS": "targeted_sequencing",
    "POOLCLONE": "clone_validation",
    "CLONE": "clone_validation",
    "CLONEEND": "clone_validation",
    "FINISHING": "genome_finishing",
    "VALIDATION": "validation",
    "FAIRE-seq": "chromatin_accessibility",
    "OTHER": "other_or_unclassified",
}

OMICS_PRIORITY = {
    "transcriptomics": 100,
    "regulomics": 95,
    "functional_genomics": 94,
    "methylomics": 85,
    "chromatin_accessibility": 70,
    "genomics": 50,
    "structural_genomics": 45,
    "amplicon": 30,
    "targeted_sequencing": 25,
    "genome_finishing": 20,
    "clone_validation": 10,
    "validation": 10,
    "unknown_sequencing": 5,
    "other_or_unclassified": 0,
}

STRAIN_PATTERNS = [
    ("MG1655", ("MG1655",)),
    ("BW25113", ("BW25113",)),
    ("W3110", ("W3110",)),
    ("BL21", ("BL21",)),
    ("REL606", ("REL606",)),
    ("O157:H7", ("O157:H7",)),
    ("CFT073", ("CFT073",)),
    ("K-12", ("K-12", "K12")),
]

CONTEXT_CLASSIFIERS = [
    (
        "functional_genomics",
        ("TN-SEQ", "TNSEQ", "TRADIS", "TRANSPOSON", "RB-TNSEQ", "HIMAR1"),
    ),
    (
        "methylomics",
        ("BISULFITE", "METHYLOME", "METHYLATION", "MEDIP", "METHYL-SEQ"),
    ),
    (
        "structural_genomics",
        ("HI-C", "HIC ", "3C-SEQ", "4C-SEQ", "CONTACT MAP"),
    ),
    (
        "chromatin_accessibility",
        ("ATAC-SEQ", "ATAC SEQ", "FAIRE-SEQ", "MNASE-SEQ"),
    ),
    (
        "regulomics",
        (
            "CHIP-SEQ",
            "CHIP SEQ",
            "CHAP",
            "BINDING PROFILE",
            "RNAP BINDING",
            "TRANSCRIPTION FACTOR",
            "PROMOTER",
            "SELEX",
        ),
    ),
    (
        "translatomics",
        ("RIBO-SEQ", "RIBOSEQ", "TRANSLATOME", "FOOTPRINTING"),
    ),
    (
        "transcriptomics",
        (
            "RNA-SEQ",
            "RNA SEQ",
            "TRANSCRIPTOME",
            "GENE EXPRESSION",
            "TRANSCRIPTION START",
            "5' END",
            "NCRNA",
            "SRNA",
        ),
    ),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_semicolon_ints(value: str | None) -> list[int]:
    if not value:
        return []
    result = []
    for item in value.split(";"):
        try:
            result.append(int(item))
        except ValueError:
            continue
    return result


def strain_guess(scientific_name: str) -> str:
    upper = scientific_name.upper()
    for strain, patterns in STRAIN_PATTERNS:
        if any(pattern.upper() in upper for pattern in patterns):
            return strain
    return "unresolved"


def data_tier(strain: str) -> str:
    if strain == "MG1655":
        return "L1_core_candidate"
    if strain in {"BW25113", "W3110", "BL21", "REL606", "O157:H7", "CFT073", "K-12"}:
        return "L1_extended_candidate"
    return "L3_on_demand"


def classify_run(strategy: str, source: str, context_text: str) -> tuple[str, float, str, int]:
    strategy_type = OMICS_MAP.get(strategy, "other_or_unclassified")
    upper = context_text.upper()
    context_type = None
    context_term = ""
    for candidate_type, terms in CONTEXT_CLASSIFIERS:
        matched = next((term for term in terms if term in upper), None)
        if matched:
            context_type = candidate_type
            context_term = matched
            break

    if context_type and strategy_type in {"other_or_unclassified", "genomics"}:
        return (
            context_type,
            0.80,
            f"context_override:{context_term};strategy={strategy};source={source}",
            0,
        )
    if context_type and context_type != strategy_type:
        return (
            context_type,
            0.68,
            f"context_conflict:strategy={strategy_type};context={context_type};term={context_term}",
            1,
        )
    if strategy_type != "other_or_unclassified":
        confidence = 0.88 if strategy in {"RNA-Seq", "ChIP-Seq", "Tn-Seq"} else 0.82
        return (
            strategy_type,
            confidence,
            f"strategy:{strategy};source={source}",
            0 if confidence >= 0.8 else 1,
        )
    if context_type:
        return context_type, 0.75, f"context_only:{context_term};strategy={strategy}", 1
    return "other_or_unclassified", 0.25, f"unresolved_strategy:{strategy};source={source}", 1


def init_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;

        DROP TABLE IF EXISTS runs;
        DROP TABLE IF EXISTS files;
        DROP TABLE IF EXISTS studies;
        DROP TABLE IF EXISTS omics_summary;
        DROP TABLE IF EXISTS strain_summary;
        DROP TABLE IF EXISTS ncbi_counts;
        DROP TABLE IF EXISTS pride_projects;
        DROP TABLE IF EXISTS download_candidates;
        DROP TABLE IF EXISTS source_snapshot;

        CREATE TABLE source_snapshot (
            source TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            snapshot_file TEXT NOT NULL
        );

        CREATE TABLE runs (
            run_accession TEXT PRIMARY KEY,
            study_accession TEXT,
            sample_accession TEXT,
            tax_id TEXT,
            scientific_name TEXT,
            strain_guess TEXT,
            library_strategy TEXT,
            library_source TEXT,
            omics_type TEXT,
            omics_priority INTEGER,
            omics_confidence REAL NOT NULL DEFAULT 0,
            classification_reason TEXT,
            classifier_version TEXT,
            needs_manual_review INTEGER NOT NULL DEFAULT 1,
            data_tier TEXT,
            license_status TEXT NOT NULL DEFAULT 'license_unverified',
            license_evidence TEXT,
            fastq_bytes INTEGER NOT NULL DEFAULT 0,
            read_count INTEGER NOT NULL DEFAULT 0,
            base_count INTEGER NOT NULL DEFAULT 0,
            has_fastq_bytes INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX idx_runs_study ON runs(study_accession);
        CREATE INDEX idx_runs_taxid ON runs(tax_id);
        CREATE INDEX idx_runs_strain ON runs(strain_guess);
        CREATE INDEX idx_runs_omics ON runs(omics_type);
        CREATE INDEX idx_runs_strategy ON runs(library_strategy);
        CREATE INDEX idx_runs_tier ON runs(data_tier);
        CREATE INDEX idx_runs_review ON runs(needs_manual_review);

        CREATE TABLE files (
            file_id TEXT PRIMARY KEY,
            run_accession TEXT NOT NULL,
            study_accession TEXT,
            sample_accession TEXT,
            strain_guess TEXT,
            omics_type TEXT,
            data_tier TEXT,
            file_index INTEGER NOT NULL,
            file_format TEXT,
            source_url TEXT,
            fastq_md5 TEXT,
            file_bytes INTEGER NOT NULL DEFAULT 0,
            local_relative_path TEXT,
            download_eligible INTEGER NOT NULL DEFAULT 0,
            license_status TEXT NOT NULL DEFAULT 'license_unverified',
            download_status TEXT NOT NULL DEFAULT 'not_queued',
            FOREIGN KEY(run_accession) REFERENCES runs(run_accession)
        );

        CREATE INDEX idx_files_run ON files(run_accession);
        CREATE INDEX idx_files_study ON files(study_accession);
        CREATE INDEX idx_files_omics ON files(omics_type);
        CREATE INDEX idx_files_tier ON files(data_tier);
        CREATE INDEX idx_files_eligible ON files(download_eligible);
        CREATE INDEX idx_files_md5 ON files(fastq_md5);

        CREATE TABLE ncbi_counts (
            name TEXT PRIMARY KEY,
            database_name TEXT,
            term TEXT,
            count INTEGER,
            status TEXT,
            error TEXT
        );

        CREATE TABLE pride_projects (
            accession TEXT PRIMARY KEY,
            title TEXT,
            organisms TEXT,
            publication_date TEXT,
            submission_date TEXT,
            updated_date TEXT,
            submission_type TEXT,
            instruments TEXT,
            experiment_types TEXT,
            keywords TEXT,
            project_description TEXT,
            project_file_names TEXT,
            doi TEXT
        );
        """
    )


def select_run_manifest() -> Path:
    for path in (ENA_CONTEXT_MANIFEST, ENA_FILES_MANIFEST, ENA_MANIFEST):
        if path.exists():
            return path
    raise FileNotFoundError("no ENA manifest is available")


def load_runs(connection: sqlite3.Connection) -> int:
    inserted = 0
    context_rows: dict[str, dict] = {}
    if ENA_MG1655_CONTEXT_MANIFEST.exists():
        with gzip.open(
            ENA_MG1655_CONTEXT_MANIFEST, "rt", encoding="utf-8-sig", newline=""
        ) as context_handle:
            for context_row in csv.DictReader(context_handle, delimiter="\t"):
                context_rows[context_row.get("run_accession") or ""] = context_row

    with gzip.open(select_run_manifest(), "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        batch = []
        for row in reader:
            row = context_rows.get(row.get("run_accession") or "", row)
            strategy = row.get("library_strategy") or "OTHER"
            source = row.get("library_source") or "MISSING"
            context_text = " ".join(
                row.get(field) or ""
                for field in ("study_title", "experiment_title", "sample_title")
            )
            omics_type, confidence, reason, needs_review = classify_run(
                strategy, source, context_text
            )
            fastq_bytes = sum(parse_semicolon_ints(row.get("fastq_bytes")))
            read_count = int((row.get("read_count") or "0").split(";")[0] or 0)
            base_count = int((row.get("base_count") or "0").split(";")[0] or 0)
            scientific_name = row.get("scientific_name") or ""
            strain = strain_guess(scientific_name)
            batch.append(
                (
                    row.get("run_accession"),
                    row.get("study_accession"),
                    row.get("sample_accession"),
                    row.get("tax_id"),
                    scientific_name,
                    strain,
                    strategy,
                    source,
                    omics_type,
                    OMICS_PRIORITY.get(omics_type, 0),
                    confidence,
                    reason,
                    CLASSIFIER_VERSION,
                    needs_review,
                    data_tier(strain),
                    "license_unverified",
                    "ENA_per_study_terms_require_review",
                    fastq_bytes,
                    read_count,
                    base_count,
                    int(fastq_bytes > 0),
                )
            )
            if len(batch) >= 5000:
                connection.executemany(
                    "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    batch,
                )
                inserted += len(batch)
                batch.clear()
        if batch:
            connection.executemany(
                "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                batch,
            )
            inserted += len(batch)
    return inserted


def build_aggregates(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE studies AS
        SELECT
            study_accession,
            COUNT(*) AS runs,
            COUNT(DISTINCT sample_accession) AS samples,
            MIN(tax_id) AS tax_id_min,
            GROUP_CONCAT(DISTINCT strain_guess) AS strains,
            GROUP_CONCAT(DISTINCT omics_type) AS omics_types,
            MIN(omics_confidence) AS min_omics_confidence,
            MAX(needs_manual_review) AS needs_manual_review,
            GROUP_CONCAT(DISTINCT data_tier) AS data_tiers,
            SUM(fastq_bytes) AS fastq_bytes,
            SUM(base_count) AS base_count
        FROM runs
        GROUP BY study_accession;

        CREATE INDEX idx_studies_bytes ON studies(fastq_bytes);

        CREATE TABLE omics_summary AS
        SELECT
            omics_type,
            COUNT(*) AS runs,
            COUNT(DISTINCT study_accession) AS studies,
            SUM(fastq_bytes) AS fastq_bytes,
            SUM(base_count) AS base_count
        FROM runs
        GROUP BY omics_type;

        CREATE TABLE strain_summary AS
        SELECT
            strain_guess,
            COUNT(*) AS runs,
            COUNT(DISTINCT study_accession) AS studies,
            GROUP_CONCAT(DISTINCT omics_type) AS omics_types,
            SUM(fastq_bytes) AS fastq_bytes,
            SUM(base_count) AS base_count
        FROM runs
        GROUP BY strain_guess;

        CREATE TABLE download_candidates AS
        SELECT
            run_accession,
            study_accession,
            sample_accession,
            tax_id,
            scientific_name,
            strain_guess,
            library_strategy,
            omics_type,
            omics_confidence,
            needs_manual_review,
            data_tier,
            license_status,
            fastq_bytes,
            base_count,
            omics_priority
                + CASE strain_guess
                    WHEN 'MG1655' THEN 50
                    WHEN 'BW25113' THEN 40
                    WHEN 'W3110' THEN 35
                    WHEN 'BL21' THEN 30
                    WHEN 'REL606' THEN 25
                    WHEN 'O157:H7' THEN 25
                    WHEN 'CFT073' THEN 25
                    WHEN 'K-12' THEN 10
                    ELSE 0
                  END AS selection_score,
            CASE
                WHEN omics_confidence < 0.6 OR needs_manual_review = 1
                    THEN 'needs_manual_review'
                ELSE 'unreviewed'
            END AS candidate_status,
            CASE
                WHEN omics_confidence < 0.6 THEN 'classification_low_confidence'
                WHEN needs_manual_review = 1 THEN 'classification_needs_review'
                ELSE 'license_status_unverified'
            END AS review_reason
        FROM runs
        WHERE strain_guess IN (
            'MG1655','BW25113','W3110','BL21','REL606','O157:H7','CFT073','K-12'
        );

        CREATE INDEX idx_candidates_score ON download_candidates(selection_score DESC);
        CREATE INDEX idx_candidates_status ON download_candidates(candidate_status);
        CREATE INDEX idx_candidates_tier ON download_candidates(data_tier);
        """
    )


def normalize_url(value: str) -> str:
    if "://" in value:
        return value
    return "https://" + value


def load_files(connection: sqlite3.Connection) -> tuple[int, int]:
    if not ENA_FILES_MANIFEST.exists():
        return 0, 0
    inserted = 0
    ineligible = 0
    run_meta = {
        row[0]: row
        for row in connection.execute(
            "SELECT run_accession, study_accession, sample_accession, strain_guess, "
            "omics_type, data_tier FROM runs"
        )
    }
    batch = []
    with gzip.open(ENA_FILES_MANIFEST, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            run_accession = row.get("run_accession") or ""
            meta = run_meta.get(run_accession)
            if not meta:
                continue
            urls = (row.get("fastq_ftp") or "").split(";")
            md5s = (row.get("fastq_md5") or "").split(";")
            sizes = parse_semicolon_ints(row.get("fastq_bytes"))
            if len(sizes) != len(urls):
                sizes = [0] * len(urls)
            if len(md5s) != len(urls):
                md5s = [""] * len(urls)
            seen_names: dict[str, int] = {}
            for index, url in enumerate(urls, start=1):
                if not url:
                    continue
                source_url = normalize_url(url)
                filename = Path(source_url.split("?", 1)[0]).name
                if not filename:
                    filename = f"{run_accession}_{index}.fastq.gz"
                name_count = seen_names.get(filename, 0)
                seen_names[filename] = name_count + 1
                if name_count:
                    filename = f"{Path(filename).stem}_{index}{Path(filename).suffix}"
                md5 = (md5s[index - 1] if index <= len(md5s) else "").strip().lower()
                file_bytes = sizes[index - 1] if index <= len(sizes) else 0
                eligible = bool(md5 and file_bytes > 0)
                if not eligible:
                    ineligible += 1
                local_relative = (
                    Path("raw")
                    / "sequencing"
                    / meta[3]
                    / run_accession
                    / filename
                ).as_posix()
                batch.append(
                    (
                        f"{run_accession}:{index}",
                        run_accession,
                        meta[1],
                        meta[2],
                        meta[3],
                        meta[4],
                        meta[5],
                        index,
                        "FASTQ.GZ" if filename.lower().endswith(".gz") else "UNKNOWN",
                        source_url,
                        md5,
                        file_bytes,
                        local_relative,
                        int(eligible),
                        "license_unverified",
                        "not_queued",
                    )
                )
                if len(batch) >= 10000:
                    connection.executemany(
                        "INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        batch,
                    )
                    inserted += len(batch)
                    batch.clear()
    if batch:
        connection.executemany(
            "INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            batch,
        )
        inserted += len(batch)
    return inserted, ineligible


def load_ncbi(connection: sqlite3.Connection) -> None:
    if not NCBI_COUNTS.exists():
        return
    payload = json.loads(NCBI_COUNTS.read_text(encoding="utf-8"))
    rows = []
    for name, item in payload.get("counts", {}).items():
        rows.append(
            (
                name,
                item.get("database"),
                item.get("term"),
                item.get("count"),
                item.get("status"),
                item.get("error"),
            )
        )
    connection.executemany("INSERT OR REPLACE INTO ncbi_counts VALUES (?,?,?,?,?,?)", rows)
    connection.execute(
        "INSERT INTO source_snapshot VALUES (?,?,?)",
        ("NCBI E-utilities", payload.get("retrieved_at", ""), str(NCBI_COUNTS.relative_to(ROOT))),
    )


def load_pride(connection: sqlite3.Connection) -> None:
    if not PRIDE_MANIFEST.exists():
        return
    with gzip.open(PRIDE_MANIFEST, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = [
            (
                row.get("accession"),
                row.get("title"),
                row.get("organisms"),
                row.get("publicationDate"),
                row.get("submissionDate"),
                row.get("updatedDate"),
                row.get("submissionType"),
                row.get("instruments"),
                row.get("experimentTypes"),
                row.get("keywords"),
                row.get("projectDescription"),
                row.get("projectFileNames"),
                row.get("doi"),
            )
            for row in reader
        ]
    connection.executemany(
        "INSERT OR REPLACE INTO pride_projects VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    snapshot = ROOT / "reports" / "coverage" / "pride_ecoli_summary.json"
    retrieved_at = utc_now()
    if snapshot.exists():
        retrieved_at = json.loads(snapshot.read_text(encoding="utf-8")).get("retrieved_at", retrieved_at)
    connection.execute(
        "INSERT INTO source_snapshot VALUES (?,?,?)",
        ("PRIDE", retrieved_at, str(snapshot.relative_to(ROOT))),
    )


def export_tsv(connection: sqlite3.Connection, query: str, output: Path, header: list[str]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(header)
        writer.writerows(connection.execute(query))


def main() -> int:
    if not ENA_MANIFEST.exists():
        raise SystemExit(f"missing ENA manifest: {ENA_MANIFEST}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    connection = sqlite3.connect(DB_PATH)
    init_schema(connection)
    inserted = load_runs(connection)
    build_aggregates(connection)
    files_inserted, files_ineligible = load_files(connection)
    load_ncbi(connection)
    load_pride(connection)
    connection.commit()

    export_tsv(
        connection,
        """
        SELECT omics_type, runs, studies, fastq_bytes, base_count
        FROM omics_summary
        ORDER BY fastq_bytes DESC
        """,
        COVERAGE / "ena_omics_summary.tsv.gz",
        ["omics_type", "runs", "studies", "fastq_bytes", "base_count"],
    )
    export_tsv(
        connection,
        """
        SELECT strain_guess, runs, studies, omics_types, fastq_bytes, base_count
        FROM strain_summary
        ORDER BY fastq_bytes DESC
        """,
        COVERAGE / "ena_strain_summary.tsv.gz",
        ["strain_guess", "runs", "studies", "omics_types", "fastq_bytes", "base_count"],
    )
    export_tsv(
        connection,
        """
        SELECT strain_guess, omics_type, COUNT(*) AS runs, SUM(fastq_bytes) AS fastq_bytes,
               MIN(selection_score) AS min_score, MAX(selection_score) AS max_score
        FROM download_candidates
        GROUP BY strain_guess, omics_type
        ORDER BY strain_guess, max_score DESC
        """,
        COVERAGE / "candidate_summary.tsv.gz",
        ["strain_guess", "omics_type", "runs", "fastq_bytes", "min_score", "max_score"],
    )
    export_tsv(
        connection,
        """
        SELECT omics_type, data_tier, needs_manual_review, COUNT(*) AS runs,
               ROUND(AVG(omics_confidence), 3) AS avg_confidence,
               SUM(fastq_bytes) AS fastq_bytes
        FROM runs
        GROUP BY omics_type, data_tier, needs_manual_review
        ORDER BY data_tier, omics_type, needs_manual_review
        """,
        COVERAGE / "ena_classification_summary.tsv.gz",
        [
            "omics_type",
            "data_tier",
            "needs_manual_review",
            "runs",
            "avg_confidence",
            "fastq_bytes",
        ],
    )
    export_tsv(
        connection,
        """
        SELECT data_tier, omics_type, COUNT(*) AS files, SUM(file_bytes) AS file_bytes,
               SUM(download_eligible) AS eligible_files
        FROM files
        GROUP BY data_tier, omics_type
        ORDER BY data_tier, file_bytes DESC
        """,
        COVERAGE / "ena_file_summary.tsv.gz",
        ["data_tier", "omics_type", "files", "file_bytes", "eligible_files"],
    )
    connection.close()

    summary = {
        "built_at": utc_now(),
        "database": str(DB_PATH.relative_to(ROOT)),
        "database_bytes": DB_PATH.stat().st_size,
        "run_manifests": [
            str(path.relative_to(ROOT))
            for path in (select_run_manifest(), ENA_MG1655_CONTEXT_MANIFEST)
            if path.exists()
        ],
        "runs_loaded": inserted,
        "files_manifest": str(ENA_FILES_MANIFEST.relative_to(ROOT))
        if ENA_FILES_MANIFEST.exists()
        else None,
        "files_loaded": files_inserted,
        "files_ineligible": files_ineligible,
        "classifier_version": CLASSIFIER_VERSION,
        "candidates": "see candidate_summary.tsv.gz",
    }
    output = COVERAGE / "catalog_build.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

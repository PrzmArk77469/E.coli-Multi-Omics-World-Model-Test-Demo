#!/usr/bin/env python3
"""Inventory and export public RegulonDB high-throughput collections.

The website exposes GFF3 links, but several of those endpoints return HTTP 200
with a zero-byte body. This collector uses the GraphQL API, which returns the
actual normalized records, and falls back to direct download only for bedGraph
and shared GFF3 files that have a real payload.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reference" / "RegulonDB"
REGISTRY = REFERENCE / "registry"
RAW = REFERENCE / "current" / "raw"
NORMALIZED = REFERENCE / "current" / "normalized"
REPORTS = ROOT / "reports" / "downloads"
BASE_URL = "https://regulondb.ccg.unam.mx"

SOURCE_MAP = {
    "TFBINDING": [
        "MULTIPLE_AUTHORS",
        "BAUMGART",
        "PALSSON",
        "ISHIHAMA",
        "GALAGAN",
    ],
    "RNAP_BINDING_SITES": ["RNAP_BINDING_SITES"],
    "TSS": ["REGULONDB"],
    "TTS": ["REGULONDB"],
    "TUS": ["REGULONDB"],
    "GENE_EXPRESSION": ["REGULONDB"],
}

SEARCH_QUERY = """
query GetDatasetsFromSearch($advancedSearch: String) {
  getDatasetsFromSearch(advancedSearch: $advancedSearch) {
    _id
    collectionData {
      source
      type
    }
    experimentCondition
    growthConditions {
      organism
      geneticBackground
      medium
      aeration
      temperature
      ph
      opticalDensity
      growthPhase
      experimentTitle
      experimentId
    }
    objectsTested {
      _id
      name
      abbreviatedName
      genes {
        _id
        name
      }
    }
    publications {
      authors
      title
    }
    sample {
      title
    }
    sourceSerie {
      title
      strategy
      platform {
        title
      }
    }
  }
}
""".strip()

DATA_QUERIES = {
    "TFBINDING": """
query GetNormalizedData($datasetId: String) {
  getAllPeaksOfDataset(datasetId: $datasetId) {
    _id
    chromosome
    closestGenes { _id name distanceTo productName }
    name
    peakLeftPosition
    peakRightPosition
    score
    datasetIds
  }
  getAllTFBindingOfDataset(datasetId: $datasetId) {
    _id
    chrLeftPosition
    chrRightPosition
    chromosome
    closestGenes { _id name distanceTo }
    datasetIds
    foundRIs {
      _id
      origin
      relativeGeneDistance
      relativeTSSDistance
      sequence
      strand
      tfbsLeftPosition
      tfbsRightPosition
    }
    nameCollection
    peakId
    score
    sequence
    strand
  }
}
""".strip(),
    "RNAP_BINDING_SITES": """
query GetNormalizedData($datasetId: String) {
  getAllPeaksOfDataset(datasetId: $datasetId) {
    _id
    chromosome
    closestGenes { _id name distanceTo productName }
    name
    peakLeftPosition
    peakRightPosition
    score
    datasetIds
  }
  getAllTFBindingOfDataset(datasetId: $datasetId) {
    _id
    chrLeftPosition
    chrRightPosition
    chromosome
    closestGenes { _id name distanceTo }
    datasetIds
    foundRIs { _id sequence strand tfbsLeftPosition tfbsRightPosition }
    nameCollection
    peakId
    score
    sequence
    strand
  }
}
""".strip(),
    "TSS": """
query GetNormalizedData($datasetId: String) {
  getAllTSSOfDataset(datasetId: $datasetId) {
    _id
    chromosome
    closestGenes { _id distanceTo name }
    datasetIds
    leftEndPosition
    pos_1
    promoter { _id confidenceLevel name pos1 sigma strand }
    rightEndPosition
    strand
  }
}
""".strip(),
    "TTS": """
query GetNormalizedData($datasetId: String) {
  getAllTTSOfDataset(datasetId: $datasetId) {
    _id
    chromosome
    closestGenes { _id name distanceTo }
    datasetIds
    leftEndPosition
    name
    rightEndPosition
    strand
    temporalId
    terminator {
      _id
      transcriptionUnits {
        _id
        name
        promoter { _id leftEndPosition name rightEndPosition sequence strand }
      }
    }
  }
}
""".strip(),
    "TUS": """
query GetNormalizedData($datasetId: String) {
  getAllTransUnitsOfDataset(datasetId: $datasetId) {
    _id
    chromosome
    datasetIds
    genes { _id name }
    leftEndPosition
    length
    name
    phantom
    pseudo
    rightEndPosition
    strand
    termType
  }
}
""".strip(),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def curl_base() -> list[str]:
    return [
        "curl.exe",
        "-sS",
        "-L",
        "--fail",
        "-4",
        "--http1.1",
        "--connect-timeout",
        "20",
        "--speed-time",
        "180",
        "--speed-limit",
        "1024",
        "--retry",
        "3",
        "--retry-all-errors",
        "--ssl-no-revoke",
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def graphql(query: str, variables: dict, timeout: int = 180) -> dict:
    payload = json.dumps({"query": query, "variables": variables})
    command = curl_base() + [
        "-X",
        "POST",
        BASE_URL + "/graphql",
        "-H",
        "Content-Type: application/json",
        "--data-binary",
        "@-",
    ]
    completed = subprocess.run(
        command,
        input=payload,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    response = json.loads(completed.stdout)
    if response.get("errors"):
        raise RuntimeError(json.dumps(response["errors"], ensure_ascii=False))
    return response["data"]


def fetch_search_inventory() -> list[dict]:
    REGISTRY.mkdir(parents=True, exist_ok=True)
    records: dict[tuple[str, str], dict] = {}
    query_status = []
    for dataset_type, sources in SOURCE_MAP.items():
        for source in sources:
            expression = f"{dataset_type}[collectionData.type]"
            if source != dataset_type:
                expression += f" AND {source}[collectionData.source]"
            try:
                data = graphql(SEARCH_QUERY, {"advancedSearch": expression}, timeout=300)
                payload = data.get("getDatasetsFromSearch") or []
                query_status.append(
                    {
                        "dataset_type": dataset_type,
                        "source": source,
                        "status": "ok",
                        "records": len(payload),
                    }
                )
                for record in payload:
                    collection = record.get("collectionData") or {}
                    key = (collection.get("type") or dataset_type, record["_id"])
                    record["_inventory_source_query"] = source
                    records[key] = record
                print(f"{dataset_type}/{source}: {len(payload)} datasets")
            except Exception as exc:  # noqa: BLE001
                query_status.append(
                    {
                        "dataset_type": dataset_type,
                        "source": source,
                        "status": "error",
                        "error": str(exc),
                    }
                )
                print(f"{dataset_type}/{source}: ERROR: {exc}")
            time.sleep(0.1)

    inventory = [records[key] for key in sorted(records)]
    snapshot = {
        "retrieved_at": utc_now(),
        "source": "RegulonDB GraphQL",
        "endpoint": BASE_URL + "/graphql",
        "license_status": "license_unverified",
        "redistribution_status": "blocked_until_reviewed",
        "query_status": query_status,
        "dataset_count": len(inventory),
        "records": inventory,
    }
    (REGISTRY / "dataset_inventory.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (REGISTRY / "dataset_inventory.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        fields = [
            "dataset_id",
            "dataset_type",
            "source",
            "strategy",
            "platform",
            "sample_title",
            "source_title",
            "objects_tested",
            "genes",
            "publication_titles",
            "experiment_condition",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for record in inventory:
            collection = record.get("collectionData") or {}
            source_serie = record.get("sourceSerie") or {}
            platform = source_serie.get("platform") or {}
            objects = record.get("objectsTested") or []
            genes = [
                gene.get("name", "")
                for item in objects
                for gene in (item.get("genes") or [])
            ]
            writer.writerow(
                {
                    "dataset_id": record.get("_id", ""),
                    "dataset_type": collection.get("type", ""),
                    "source": collection.get("source", ""),
                    "strategy": source_serie.get("strategy", ""),
                    "platform": platform.get("title", ""),
                    "sample_title": (record.get("sample") or {}).get("title", ""),
                    "source_title": source_serie.get("title", ""),
                    "objects_tested": ";".join(
                        item.get("abbreviatedName") or item.get("name") or ""
                        for item in objects
                    ),
                    "genes": ";".join(sorted(set(genes))),
                    "publication_titles": ";".join(
                        item.get("title", "") for item in (record.get("publications") or [])
                    ),
                    "experiment_condition": record.get("experimentCondition") or "",
                }
            )
    return inventory


def build_plan(
    inventory: list[dict],
    include_gene_expression: bool,
    gene_expression_limit: int,
) -> list[dict]:
    plan = [
        {
            "mode": "direct",
            "dataset_type": "TSS",
            "source": "REGULONDB",
            "dataset_id": "shared",
            "kind": "promoter_set",
            "url": BASE_URL + "/media/raw/gff3/PromoterSet.gff3",
            "extension": "gff3",
        },
        {
            "mode": "direct",
            "dataset_type": "TTS",
            "source": "REGULONDB",
            "dataset_id": "shared",
            "kind": "terminator_set",
            "url": BASE_URL + "/media/raw/gff3/TerminatorSet.gff3",
            "extension": "gff3",
        },
        {
            "mode": "direct",
            "dataset_type": "TUS",
            "source": "REGULONDB",
            "dataset_id": "shared",
            "kind": "tu_set",
            "url": BASE_URL + "/media/raw/gff3/TUSet.gff3",
            "extension": "gff3",
        },
    ]
    gene_expression: list[dict] = []
    for record in inventory:
        collection = record.get("collectionData") or {}
        dataset_type = collection.get("type") or ""
        source = collection.get("source") or ""
        dataset_id = record.get("_id") or ""
        if dataset_type in DATA_QUERIES:
            plan.append(
                {
                    "mode": "graphql",
                    "dataset_type": dataset_type,
                    "source": source,
                    "dataset_id": dataset_id,
                    "kind": "normalized",
                }
            )
        elif dataset_type == "GENE_EXPRESSION" and include_gene_expression:
            gene_expression.append(
                {
                    "mode": "direct",
                    "dataset_type": dataset_type,
                    "source": source,
                    "dataset_id": dataset_id,
                    "kind": "gene_expression",
                    "url": BASE_URL + f"/wdps/{dataset_id}/ge/bedgraph",
                    "extension": "bedgraph",
                }
            )
    if gene_expression_limit > 0:
        gene_expression = gene_expression[:gene_expression_limit]
    plan.extend(gene_expression)
    return plan


def destination_for(item: dict) -> Path:
    if item["mode"] == "graphql":
        return (
            NORMALIZED
            / item["dataset_type"]
            / item["source"]
            / f"{item['dataset_id']}.json.gz"
        )
    return (
        RAW
        / item["dataset_type"]
        / item["source"]
        / item["dataset_id"]
        / f"{item['dataset_id']}_{item['kind']}.{item.get('extension', 'gff3')}"
    )


def write_graphql_result(item: dict) -> dict:
    destination = destination_for(item)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return {
            **item,
            "status": "skipped_existing",
            "local_relative_path": str(destination.relative_to(ROOT)),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "finished_at": utc_now(),
        }
    try:
        data = graphql(
            DATA_QUERIES[item["dataset_type"]],
            {"datasetId": item["dataset_id"]},
            timeout=1800,
        )
        rows = sum(len(value) for value in data.values() if isinstance(value, list))
        part = destination.with_suffix(destination.suffix + ".part")
        with gzip.open(part, "wt", encoding="utf-8", newline="") as handle:
            json.dump(
                {
                    "dataset_type": item["dataset_type"],
                    "source": item["source"],
                    "dataset_id": item["dataset_id"],
                    "retrieved_at": utc_now(),
                    "row_count": rows,
                    "data": data,
                },
                handle,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            handle.write("\n")
        part.replace(destination)
        return {
            **item,
            "status": "downloaded" if rows else "downloaded_empty_dataset",
            "row_count": rows,
            "local_relative_path": str(destination.relative_to(ROOT)),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "finished_at": utc_now(),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            **item,
            "status": "failed",
            "error": str(exc),
            "bytes": 0,
            "finished_at": utc_now(),
        }


def download_direct(item: dict, retries: int) -> dict:
    destination = destination_for(item)
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")
    if destination.exists() and destination.stat().st_size > 0:
        return {
            **item,
            "status": "skipped_existing",
            "local_relative_path": str(destination.relative_to(ROOT)),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "finished_at": utc_now(),
        }
    last_error = ""
    for attempt in range(1, retries + 1):
        command = curl_base() + ["--continue-at", "-", "--output", str(part), item["url"]]
        try:
            subprocess.run(command, check=True, timeout=1800)
        except subprocess.CalledProcessError as exc:
            last_error = f"curl exit {exc.returncode}; partial file retained"
            if attempt < retries:
                time.sleep(min(20, 2 * attempt))
            continue
        if not part.exists() or part.stat().st_size == 0:
            last_error = "empty response"
            if attempt < retries:
                time.sleep(min(20, 2 * attempt))
            continue
        part.replace(destination)
        return {
            **item,
            "status": "downloaded",
            "local_relative_path": str(destination.relative_to(ROOT)),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "attempts": attempt,
            "finished_at": utc_now(),
        }
    return {
        **item,
        "status": "failed",
        "error": last_error,
        "bytes": 0,
        "finished_at": utc_now(),
    }


def run_plan(plan: list[dict], workers: int, retries: int) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    status_path = REPORTS / "regulondb_download_status.jsonl"
    summary_path = REPORTS / "regulondb_download_summary.json"
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {}
        for item in plan:
            if item["mode"] == "graphql":
                futures[executor.submit(write_graphql_result, item)] = item
            else:
                futures[executor.submit(download_direct, item, retries)] = item
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"{result['status']}: {result['dataset_type']}/"
                f"{result['dataset_id']} rows={result.get('row_count', '')}",
                flush=True,
            )
            with status_path.open("w", encoding="utf-8", newline="") as handle:
                for item in results:
                    handle.write(
                        json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
                    )

    counts: dict[str, int] = {}
    bytes_by_status: dict[str, int] = {}
    rows = 0
    for item in results:
        status = item["status"]
        counts[status] = counts.get(status, 0) + 1
        bytes_by_status[status] = bytes_by_status.get(status, 0) + int(item.get("bytes", 0))
        rows += int(item.get("row_count", 0))
    summary = {
        "finished_at": utc_now(),
        "files": len(results),
        "record_rows": rows,
        "counts": counts,
        "bytes_by_status": bytes_by_status,
        "total_bytes": sum(bytes_by_status.values()),
        "license_status": "license_unverified",
        "redistribution_status": "blocked_until_reviewed",
        "note": "GFF3 links with empty payloads were replaced by GraphQL exports.",
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if counts.get("failed"):
        raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--include-gene-expression", action="store_true")
    parser.add_argument(
        "--gene-expression-limit",
        type=int,
        default=100,
        help="0 downloads all discovered gene-expression bedGraph files",
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    inventory = fetch_search_inventory()
    plan = build_plan(
        inventory,
        args.include_gene_expression,
        args.gene_expression_limit,
    )
    (REGISTRY / "download_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"download plan: {len(plan)} files")
    if args.download:
        run_plan(plan, args.workers, args.retries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

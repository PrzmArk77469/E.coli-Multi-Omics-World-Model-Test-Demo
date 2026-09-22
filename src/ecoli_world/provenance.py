"""Versioned provenance for local, container, and CI runs (no network calls)."""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_provenance(config: dict[str, Any], inputs: list[Path] | None = None,
                     container_image: str | None = None) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    def git(*args: str) -> str:
        try:
            return subprocess.check_output(["git", *args], cwd=root, text=True,
                                           stderr=subprocess.DEVNULL, timeout=5).strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    # Includes uncommitted source bytes: a commit alone cannot identify a dirty run.
    code_files = sorted({path for pattern in ("pyproject.toml", "src/**/*", "schemas/*", "visualizations/**/*")
                         for path in root.glob(pattern)
                         if path.is_file() and "__pycache__" not in path.parts})
    code_hash = hashlib.sha256()
    for path in code_files:
        code_hash.update(path.relative_to(root).as_posix().encode() + b"\0")
        code_hash.update(bytes.fromhex(sha256_file(path)))
    image = container_image or os.environ.get("ECOLI_CONTAINER_IMAGE")
    return {
        "schema_version": "ecoli-run-v2",
        "run_id": uuid4().hex,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "code_commit": git("rev-parse", "HEAD") or "unavailable",
        "code_dirty": bool(git("status", "--porcelain", "--untracked-files=normal")),
        "source_tree_sha256": code_hash.hexdigest(),
        "source_data_version": "sha256-addressed-inputs" if inputs else "synthetic-fixture-v2",
        "inputs": [{"path": str(path.resolve()), "sha256": sha256_file(path),
                    "bytes": path.stat().st_size} for path in inputs or []],
        "configuration": config,
        "random_seed": config.get("seed"),
        "container_image": image or "not_provided",
        "container_image_note": "Pass an immutable image digest for container runs; no image is inferred.",
        "python": platform.python_version(),
        "platform": platform.platform(),
    }


def prepare_output_dir(path: Path) -> None:
    """Protect previous evidence from accidental replacement."""
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"output directory is not empty; choose a new run directory: {path}")
    path.mkdir(parents=True, exist_ok=True)

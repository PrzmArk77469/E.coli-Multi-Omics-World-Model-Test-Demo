"""Output helpers for deterministic simulation runs."""

from __future__ import annotations

import json
import gzip
import io
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from .models import EncounterEvent


@contextmanager
def deterministic_gzip_text(path: Path):
    """Gzip output independent of wall-clock time and destination filename."""
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                yield text


class JsonlEventWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._stream: Optional[object] = None

    def __enter__(self) -> "JsonlEventWriter":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.path.open("w", encoding="utf-8", newline="\n")
        return self

    def write(self, event: EncounterEvent) -> None:
        if self._stream is None:
            raise RuntimeError("writer is not open")
        self._stream.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_spatial_records(output_dir: Path, agents: list, complexes: list) -> dict[str, str]:
    """Export final agent/member and complex envelopes, in micrometres.

    Bound members remain present with active=false; consumers must not count
    them again when rendering or counting their enclosing complex.
    """
    paths = {}
    for name, records in (("agents", agents), ("complexes", complexes)):
        path = output_dir / f"{name}.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record.to_dict(), sort_keys=True, allow_nan=False) + "\n")
        paths[name] = str(path)
    return paths

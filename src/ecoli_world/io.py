"""Output helpers for deterministic simulation runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import EncounterEvent


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

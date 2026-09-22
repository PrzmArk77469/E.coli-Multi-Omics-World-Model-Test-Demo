"""Uniform-grid spatial hash for local neighborhood discovery."""

from __future__ import annotations

from collections.abc import Iterable
from math import floor

from .models import Agent


class UniformGrid:
    """A deterministic 3D uniform grid.

    This avoids all-pairs comparisons. The cell size should be at least the
    largest interaction radius so checking adjacent cells is sufficient.
    """

    _FORWARD_NEIGHBORS = (
        (1, 0, 0),
        (1, 1, 0),
        (1, -1, 0),
        (1, 0, 1),
        (1, 0, -1),
        (1, 1, 1),
        (1, 1, -1),
        (1, -1, 1),
        (1, -1, -1),
        (0, 1, 0),
        (0, 1, 1),
        (0, 1, -1),
        (0, 0, 1),
    )

    def __init__(self, cell_size: float) -> None:
        if cell_size <= 0:
            raise ValueError("cell_size must be positive")
        self.cell_size = cell_size
        self._cells: dict[tuple[int, int, int], list[int]] = {}
        self._agent_ids: dict[int, tuple[int, int, int]] = {}

    def insert(self, agent: Agent) -> None:
        cell = self._cell(agent.position)
        self._cells.setdefault(cell, []).append(agent.agent_uid)
        self._agent_ids[agent.agent_uid] = cell

    def cell_for(self, agent_uid: int) -> tuple[int, int, int]:
        return self._agent_ids[agent_uid]

    def candidate_pairs(self) -> Iterable[tuple[int, int]]:
        """Yield each pair once without comparing non-neighboring cells."""

        for cell in sorted(self._cells):
            cell_agents = sorted(self._cells[cell])
            for index, first in enumerate(cell_agents):
                for second in cell_agents[index + 1 :]:
                    yield (first, second)
            for offset in self._FORWARD_NEIGHBORS:
                other_cell = (cell[0] + offset[0], cell[1] + offset[1], cell[2] + offset[2])
                other_agents = self._cells.get(other_cell)
                if not other_agents:
                    continue
                for first in cell_agents:
                    for second in sorted(other_agents):
                        # Forward cell offsets already visit each cell pair once.
                        # IDs are unrelated to spatial ordering; filtering by ID
                        # here would silently discard half the cross-cell pairs.
                        yield (min(first, second), max(first, second))

    def _cell(self, position: tuple[float, float, float]) -> tuple[int, int, int]:
        return tuple(floor(value / self.cell_size) for value in position)

"""Micrometre geometry for an x-axis spherocylinder and enclosing spheres."""

from __future__ import annotations

import math
import random

Position = tuple[float, float, float]


def contains_sphere(position: Position, radius: float, length: float, cell_radius: float) -> bool:
    """Test full sphere containment; length includes both hemispherical caps."""
    half_segment = length / 2.0 - cell_radius
    x, y, z = position
    distance_to_segment = math.sqrt(max(abs(x) - half_segment, 0.0) ** 2 + y*y + z*z)
    return distance_to_segment + radius <= cell_radius + 1e-12


def sample_position(rng: random.Random, radius: float, length: float, cell_radius: float) -> Position:
    """Uniformly sample a center in the capsule eroded by the agent radius."""
    if not (0 < radius < cell_radius and length >= 2 * cell_radius):
        raise ValueError("agent sphere must fit in a valid spherocylinder")
    usable_radius = cell_radius - radius
    half_segment = length / 2.0 - cell_radius
    while True:
        position = (
            rng.uniform(-half_segment - usable_radius, half_segment + usable_radius),
            rng.uniform(-usable_radius, usable_radius),
            rng.uniform(-usable_radius, usable_radius),
        )
        if contains_sphere(position, radius, length, cell_radius):
            return position


def enclosing_sphere(first: Position, first_radius: float, second: Position,
                     second_radius: float) -> tuple[Position, float]:
    """Smallest sphere enclosing two member spheres, without moving members."""
    distance = math.dist(first, second)
    if first_radius >= distance + second_radius:
        return first, first_radius
    if second_radius >= distance + first_radius:
        return second, second_radius
    radius = (distance + first_radius + second_radius) / 2.0
    fraction = (radius - first_radius) / distance
    center = tuple(a + fraction * (b - a) for a, b in zip(first, second))
    return center, radius

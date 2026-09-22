"""Core data models for the simulation MVP."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Optional


OUTCOMES = {"NO_EFFECT", "MODIFY", "BIND"}
ACTIONS = {"NO_EFFECT", "MODIFY_SELF", "MODIFY_PEER", "MODIFY_BOTH", "BIND", "TRANSFORM", "DISSOCIATE"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


@dataclass(slots=True)
class Agent:
    agent_uid: int
    species_id: str
    agent_type: str
    state_id: str
    compartment: str
    x: float
    y: float
    z: float
    r_eff: float
    copy_weight: int = 1
    active: bool = True
    complex_uid: Optional[str] = None
    state_version: int = 0
    source_ref: str = "synthetic://mvp"
    confidence: float = 0.5
    unified_sample_id: str = ""
    condition_id: str = ""
    data_origin: str = "SYNTHETIC"
    condition_data_origin: str = "UNSPECIFIED"
    radius_definition: str = "synthetic_agent_sphere"
    coordinate_unit: str = "um"

    @property
    def position(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def validate(self) -> None:
        require(all(math.isfinite(v) for v in (*self.position, self.r_eff)), "geometry must be finite")
        require(self.agent_uid >= 0, "agent_uid must be non-negative")
        require(bool(self.species_id), "species_id is required")
        require(bool(self.agent_type), "agent_type is required")
        require(bool(self.state_id), "state_id is required")
        require(bool(self.compartment), "compartment is required")
        require(self.r_eff > 0, "r_eff must be positive")
        require(self.copy_weight >= 1, "copy_weight must be at least 1")
        require(0.0 <= self.confidence <= 1.0, "confidence must be between 0 and 1")
        require(
            self.data_origin in {"OBSERVED", "MIXED", "SYNTHETIC"},
            "unsupported data_origin",
        )
        require(self.condition_data_origin in {"OBSERVED", "MIXED", "SYNTHETIC", "UNSPECIFIED"},
                "unsupported condition_data_origin")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Behavior:
    behavior_id: str
    source_text: str
    structured_rule_id: str
    trigger: dict[str, Any]
    preconditions: list[str] = field(default_factory=list)
    action_distribution: dict[str, float] = field(default_factory=dict)
    delay_model: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5

    def validate(self) -> None:
        require(bool(self.behavior_id), "behavior_id is required")
        require(bool(self.structured_rule_id), "structured_rule_id is required")
        require(0.0 <= self.confidence <= 1.0, "confidence must be between 0 and 1")
        total = sum(self.action_distribution.values())
        require(all(math.isfinite(p) and 0 <= p <= 1 for p in self.action_distribution.values()),
                "action probabilities must be finite and between 0 and 1")
        require(total <= 1.000001, "action_distribution probabilities must sum to at most 1")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Rule:
    rule_id: str
    type_a: str
    state_a: str
    type_b: str
    state_b: str
    compartment: Optional[str]
    trigger_offset: float
    action: str
    probability: float
    rate: float
    output_type: Optional[str]
    cooldown: int
    priority: int

    def validate(self) -> None:
        require(bool(self.rule_id), "rule_id is required")
        require(all(math.isfinite(v) for v in (self.probability, self.rate, self.trigger_offset)),
                "rule parameters must be finite")
        require(self.action in ACTIONS, f"unsupported action: {self.action}")
        require(0.0 <= self.probability <= 1.0, "probability must be between 0 and 1")
        require(self.rate >= 0.0, "rate must be non-negative")
        require(self.trigger_offset >= 0.0, "trigger_offset must be non-negative")
        require(self.cooldown >= 0, "cooldown must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EncounterEvent:
    event_id: int
    simulation_time: float
    step_index: int
    agent_a_uid: int
    agent_b_uid: int
    distance: float
    rule_id: str
    outcome: str
    a_state_before: str
    a_state_after: str
    b_state_before: str
    b_state_after: str
    new_complex_uid: Optional[str] = None

    def validate(self) -> None:
        require(self.outcome in OUTCOMES, f"unsupported outcome: {self.outcome}")
        require(self.agent_a_uid != self.agent_b_uid, "an encounter requires two distinct agents")
        require(self.distance >= 0.0, "distance must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Complex:
    complex_uid: str
    representative_x: float
    representative_y: float
    representative_z: float
    r_eff: float
    behavior_profile_id: str
    component_count: int
    created_event_id: int
    created_at: float
    member_agent_uids: list[int] = field(default_factory=list)
    radius_definition: str = "minimum_enclosing_member_spheres"
    coordinate_unit: str = "um"

    def validate(self) -> None:
        require(bool(self.complex_uid), "complex_uid is required")
        require(all(math.isfinite(v) for v in (self.representative_x, self.representative_y,
                                               self.representative_z, self.r_eff)),
                "complex geometry must be finite")
        require(self.r_eff > 0, "r_eff must be positive")
        require(self.component_count >= 2, "a complex requires at least two components")
        require(len(self.member_agent_uids) == self.component_count, "component_count must match members")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

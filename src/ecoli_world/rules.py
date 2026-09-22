"""Default behavior and rule set for the synthetic MVP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import Agent, Behavior, Rule


@dataclass(slots=True, frozen=True)
class TriggeredRule:
    rule: Rule
    target_agent_uid: Optional[int]


def default_rules() -> list[Rule]:
    return [
        Rule(
            rule_id="rule_modify_kinase_target",
            type_a="Kinase",
            state_a="active",
            type_b="Target",
            state_b="inactive",
            compartment="cytoplasm",
            trigger_offset=0.030,
            action="MODIFY_PEER",
            probability=0.75,
            rate=10.0,
            output_type="active",
            cooldown=4,
            priority=100,
        ),
        Rule(
            rule_id="rule_bind_protein_ab",
            type_a="ProteinA",
            state_a="free",
            type_b="ProteinB",
            state_b="free",
            compartment="cytoplasm",
            trigger_offset=0.035,
            action="BIND",
            probability=0.60,
            rate=8.0,
            output_type="ComplexAB",
            cooldown=8,
            priority=90,
        ),
        Rule(
            rule_id="rule_no_effect_default",
            type_a="*",
            state_a="*",
            type_b="*",
            state_b="*",
            compartment=None,
            trigger_offset=0.020,
            action="NO_EFFECT",
            probability=1.0,
            rate=0.0,
            output_type=None,
            cooldown=3,
            priority=1,
        ),
    ]


def default_behaviors() -> list[Behavior]:
    return [
        Behavior(
            behavior_id="behavior_modify_kinase_target",
            source_text="A synthetic active kinase can activate an inactive target.",
            structured_rule_id="rule_modify_kinase_target",
            trigger={"types": ["Kinase", "Target"], "distance": "contact"},
            preconditions=["same compartment", "target state is inactive"],
            action_distribution={"MODIFY": 0.75, "NO_EFFECT": 0.25},
            delay_model={"scheduled_steps": 1},
            constraints=["target_state_transition_once"],
            provenance={"kind": "synthetic_fixture", "purpose": "workflow_validation"},
            confidence=0.5,
        ),
        Behavior(
            behavior_id="behavior_bind_protein_ab",
            source_text="Synthetic free A and B proteins can form an abstract complex.",
            structured_rule_id="rule_bind_protein_ab",
            trigger={"types": ["ProteinA", "ProteinB"], "distance": "contact"},
            preconditions=["both proteins are free", "same compartment"],
            action_distribution={"BIND": 0.60, "NO_EFFECT": 0.40},
            delay_model={"scheduled_steps": 1},
            constraints=["both_agents_deactivate", "complex_membership_is_recorded"],
            provenance={"kind": "synthetic_fixture", "purpose": "workflow_validation"},
            confidence=0.5,
        ),
        Behavior(
            behavior_id="behavior_no_effect_contact",
            source_text="A contact may be recorded without changing either agent.",
            structured_rule_id="rule_no_effect_default",
            trigger={"types": ["*", "*"], "distance": "contact"},
            preconditions=["no higher-priority rule matched"],
            action_distribution={"NO_EFFECT": 1.0},
            delay_model={"scheduled_steps": 1},
            constraints=["history_is_preserved"],
            provenance={"kind": "synthetic_fixture", "purpose": "workflow_validation"},
            confidence=0.5,
        ),
    ]


def match_triggered_rule(
    agent_a: Agent,
    agent_b: Agent,
    distance: float,
    rules: list[Rule],
) -> Optional[TriggeredRule]:
    for rule in rules:
        for first, second in ((agent_a, agent_b), (agent_b, agent_a)):
            if rule.compartment and first.compartment != rule.compartment:
                continue
            if rule.compartment and second.compartment != rule.compartment:
                continue
            if not _field_matches(rule.type_a, first.agent_type):
                continue
            if not _field_matches(rule.state_a, first.state_id):
                continue
            if not _field_matches(rule.type_b, second.agent_type):
                continue
            if not _field_matches(rule.state_b, second.state_id):
                continue
            if distance > first.r_eff + second.r_eff + rule.trigger_offset:
                continue

            target_agent_uid = second.agent_uid if rule.action == "MODIFY_PEER" else None
            return TriggeredRule(rule=rule, target_agent_uid=target_agent_uid)
    return None


def _field_matches(pattern: str, value: str) -> bool:
    return pattern == "*" or pattern == value

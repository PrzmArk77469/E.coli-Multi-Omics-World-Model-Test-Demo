"""Deterministic event-driven simulation for the 2,000-agent MVP."""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Optional

from .events import EventQueue, PendingEvent
from .models import Agent, Behavior, Complex, EncounterEvent, Rule
from .rules import TriggeredRule, default_behaviors, default_rules, match_triggered_rule
from .spatial import UniformGrid


@dataclass(slots=True)
class SimulationConfig:
    agent_count: int = 2000
    steps: int = 80
    seed: int = 42
    step_seconds: float = 0.01
    cell_size_um: float = 0.15
    cell_length_um: float = 2.0
    cell_radius_um: float = 0.5
    event_delay_steps: int = 1
    max_scheduled_events_per_step: int = 50000

    def validate(self) -> None:
        if self.agent_count < 2:
            raise ValueError("agent_count must be at least 2")
        if self.steps < 1:
            raise ValueError("steps must be at least 1")
        if self.step_seconds <= 0:
            raise ValueError("step_seconds must be positive")
        if self.cell_size_um <= 0:
            raise ValueError("cell_size_um must be positive")
        if self.cell_length_um <= 0 or self.cell_radius_um <= 0:
            raise ValueError("cell geometry must be positive")
        if self.event_delay_steps < 1:
            raise ValueError("event_delay_steps must be at least 1")
        if self.max_scheduled_events_per_step < 1:
            raise ValueError("max_scheduled_events_per_step must be positive")


@dataclass(slots=True)
class SimulationResult:
    config: SimulationConfig
    outcome_counts: dict[str, int]
    complex_count: int
    active_agents: int
    event_count: int
    invalidated_events: int
    queued_events_remaining: int
    events: list[EncounterEvent]
    complexes: list[Complex]

    def to_summary_dict(self) -> dict[str, object]:
        summary = asdict(self.config)
        summary.update(
            {
                "outcome_counts": dict(self.outcome_counts),
                "complex_count": self.complex_count,
                "active_agents": self.active_agents,
                "event_count": self.event_count,
                "invalidated_events": self.invalidated_events,
                "queued_events_remaining": self.queued_events_remaining,
                "simulation_seconds": self.config.steps * self.config.step_seconds,
            }
        )
        return summary


class SimulationEngine:
    def __init__(
        self,
        config: SimulationConfig,
        rules: Optional[list[Rule]] = None,
        behaviors: Optional[list[Behavior]] = None,
        event_sink: Optional[Callable[[EncounterEvent], None]] = None,
    ) -> None:
        config.validate()
        self.config = config
        self.rules = sorted(rules or default_rules(), key=lambda rule: (-rule.priority, rule.rule_id))
        self.behaviors = behaviors or default_behaviors()
        self.event_sink = event_sink
        self.rng = random.Random(config.seed)
        self.agents: list[Agent] = []
        self.agents_by_uid: dict[int, Agent] = {}
        self.queue = EventQueue()
        self.events: list[EncounterEvent] = []
        self.complexes: list[Complex] = []
        self.cooldowns: dict[tuple[int, int, str], int] = {}
        self.invalidated_events = 0
        self._complex_counter = 1
        self._initialize_agents()

    def run(self) -> SimulationResult:
        for step_index in range(self.config.steps):
            self._schedule_contacts(step_index)
            self._process_due_events(step_index)

        outcome_counts = Counter(event.outcome for event in self.events)
        return SimulationResult(
            config=self.config,
            outcome_counts={
                "NO_EFFECT": outcome_counts.get("NO_EFFECT", 0),
                "MODIFY": outcome_counts.get("MODIFY", 0),
                "BIND": outcome_counts.get("BIND", 0),
            },
            complex_count=len(self.complexes),
            active_agents=sum(1 for agent in self.agents if agent.active),
            event_count=len(self.events),
            invalidated_events=self.invalidated_events,
            queued_events_remaining=self.queue.queued_count,
            events=self.events,
            complexes=self.complexes,
        )

    def _initialize_agents(self) -> None:
        type_counts = self._distribute_agent_types()
        agent_types: list[str] = []
        for agent_type, count in type_counts.items():
            agent_types.extend([agent_type] * count)
        self.rng.shuffle(agent_types)

        for agent_uid, agent_type in enumerate(agent_types):
            x, y, z = self._random_rod_position()
            state_id, r_eff, copy_weight = self._type_defaults(agent_type)
            agent = Agent(
                agent_uid=agent_uid,
                species_id=f"ECOLI:{agent_type}",
                agent_type=agent_type,
                state_id=state_id,
                compartment="cytoplasm",
                x=x,
                y=y,
                z=z,
                r_eff=r_eff,
                copy_weight=copy_weight,
                source_ref=f"synthetic://ecoli-mvp/{agent_type}",
                confidence=0.5,
            )
            agent.validate()
            self.agents.append(agent)
            self.agents_by_uid[agent.agent_uid] = agent

    def _distribute_agent_types(self) -> dict[str, int]:
        weights = {
            "ProteinA": 0.20,
            "ProteinB": 0.20,
            "Kinase": 0.15,
            "Target": 0.30,
            "Metabolite": 0.15,
        }
        exact = {name: int(self.config.agent_count * weight) for name, weight in weights.items()}
        remaining = self.config.agent_count - sum(exact.values())
        names = list(weights)
        for index in range(remaining):
            exact[names[index % len(names)]] += 1
        return exact

    def _type_defaults(self, agent_type: str) -> tuple[str, float, int]:
        defaults = {
            "ProteinA": ("free", 0.045, self.rng.randint(2, 20)),
            "ProteinB": ("free", 0.045, self.rng.randint(2, 20)),
            "Kinase": ("active", 0.040, self.rng.randint(1, 8)),
            "Target": ("inactive", 0.050, self.rng.randint(1, 30)),
            "Metabolite": ("pool", 0.025, self.rng.randint(20, 200)),
        }
        return defaults[agent_type]

    def _random_rod_position(self) -> tuple[float, float, float]:
        usable_radius = self.config.cell_radius_um * 0.90
        usable_half_length = (self.config.cell_length_um * 0.5) - 0.05
        radius = usable_radius * math.sqrt(self.rng.random())
        theta = self.rng.uniform(0.0, 2.0 * math.pi)
        x = self.rng.uniform(-usable_half_length, usable_half_length)
        return (x, radius * math.cos(theta), radius * math.sin(theta))

    def _schedule_contacts(self, step_index: int) -> None:
        grid = UniformGrid(self.config.cell_size_um)
        for agent in self.agents:
            if agent.active:
                grid.insert(agent)

        scheduled = 0
        for first_uid, second_uid in grid.candidate_pairs():
            if scheduled >= self.config.max_scheduled_events_per_step:
                break
            first = self.agents_by_uid[first_uid]
            second = self.agents_by_uid[second_uid]
            distance = _distance(first, second)
            triggered = self._find_triggered_rule(first, second, distance)
            if triggered is None:
                continue

            key = (first_uid, second_uid, triggered.rule.rule_id)
            if step_index < self.cooldowns.get(key, -1):
                continue
            if self.queue.schedule(
                scheduled_step=step_index + self.config.event_delay_steps,
                agent_a_uid=first_uid,
                agent_b_uid=second_uid,
                rule_id=triggered.rule.rule_id,
            ):
                scheduled += 1

    def _process_due_events(self, step_index: int) -> None:
        for pending in self.queue.pop_due(step_index):
            event = self._resolve_pending_event(pending)
            if event is None:
                self.invalidated_events += 1
                continue
            self.events.append(event)
            if self.event_sink is not None:
                self.event_sink(event)

    def _resolve_pending_event(self, pending: PendingEvent) -> Optional[EncounterEvent]:
        agent_a = self.agents_by_uid[pending.agent_a_uid]
        agent_b = self.agents_by_uid[pending.agent_b_uid]
        if not agent_a.active or not agent_b.active:
            return None

        distance = _distance(agent_a, agent_b)
        rule = self._rule_by_id(pending.rule_id)
        triggered = match_triggered_rule(agent_a, agent_b, distance, [rule])
        if triggered is None:
            return None

        a_state_before = agent_a.state_id
        b_state_before = agent_b.state_id
        outcome = "NO_EFFECT"
        new_complex_uid: Optional[str] = None

        if triggered.rule.action != "NO_EFFECT" and self.rng.random() <= triggered.rule.probability:
            if triggered.rule.action == "MODIFY_PEER" and triggered.target_agent_uid is not None:
                target = self.agents_by_uid[triggered.target_agent_uid]
                if target.state_id != triggered.rule.output_type:
                    target.state_id = str(triggered.rule.output_type)
                    target.state_version += 1
                    outcome = "MODIFY"
            elif triggered.rule.action == "BIND":
                new_complex_uid = self._create_complex(agent_a, agent_b, pending, triggered.rule)
                outcome = "BIND"

        key = (pending.agent_a_uid, pending.agent_b_uid, triggered.rule.rule_id)
        self.cooldowns[key] = pending.scheduled_step + triggered.rule.cooldown

        event = EncounterEvent(
            event_id=pending.event_id,
            simulation_time=pending.scheduled_step * self.config.step_seconds,
            step_index=pending.scheduled_step,
            agent_a_uid=agent_a.agent_uid,
            agent_b_uid=agent_b.agent_uid,
            distance=round(distance, 6),
            rule_id=triggered.rule.rule_id,
            outcome=outcome,
            a_state_before=a_state_before,
            a_state_after=agent_a.state_id,
            b_state_before=b_state_before,
            b_state_after=agent_b.state_id,
            new_complex_uid=new_complex_uid,
        )
        event.validate()
        return event

    def _create_complex(
        self,
        agent_a: Agent,
        agent_b: Agent,
        pending: PendingEvent,
        rule: Rule,
    ) -> str:
        complex_uid = f"complex_{self._complex_counter:06d}"
        self._complex_counter += 1
        agent_a.active = False
        agent_b.active = False
        agent_a.complex_uid = complex_uid
        agent_b.complex_uid = complex_uid
        agent_a.state_version += 1
        agent_b.state_version += 1
        complex_model = Complex(
            complex_uid=complex_uid,
            representative_x=(agent_a.x + agent_b.x) / 2.0,
            representative_y=(agent_a.y + agent_b.y) / 2.0,
            representative_z=(agent_a.z + agent_b.z) / 2.0,
            r_eff=math.sqrt((agent_a.r_eff ** 2) + (agent_b.r_eff ** 2)),
            behavior_profile_id=str(rule.output_type),
            component_count=2,
            created_event_id=pending.event_id,
            created_at=pending.scheduled_step * self.config.step_seconds,
            member_agent_uids=[agent_a.agent_uid, agent_b.agent_uid],
        )
        complex_model.validate()
        self.complexes.append(complex_model)
        return complex_uid

    def _find_triggered_rule(
        self,
        agent_a: Agent,
        agent_b: Agent,
        distance: float,
    ) -> Optional[TriggeredRule]:
        return match_triggered_rule(agent_a, agent_b, distance, self.rules)

    def _rule_by_id(self, rule_id: str) -> Rule:
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        raise KeyError(f"unknown rule: {rule_id}")


def _distance(agent_a: Agent, agent_b: Agent) -> float:
    return math.dist(agent_a.position, agent_b.position)

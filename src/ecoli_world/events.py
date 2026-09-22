"""Priority event queue used by the simulation MVP."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field


@dataclass(order=True, slots=True)
class PendingEvent:
    scheduled_step: int
    sequence: int
    event_id: int = field(compare=False)
    agent_a_uid: int = field(compare=False)
    agent_b_uid: int = field(compare=False)
    rule_id: str = field(compare=False)
    pair_rule_key: tuple[int, int, str] = field(compare=False)


class EventQueue:
    def __init__(self) -> None:
        self._heap: list[PendingEvent] = []
        self._queued_keys: set[tuple[int, int, str]] = set()
        self._sequence = 0
        self.next_event_id = 1

    @property
    def queued_count(self) -> int:
        return len(self._heap)

    def schedule(
        self,
        scheduled_step: int,
        agent_a_uid: int,
        agent_b_uid: int,
        rule_id: str,
    ) -> bool:
        first, second = sorted((agent_a_uid, agent_b_uid))
        pair_rule_key = (first, second, rule_id)
        if pair_rule_key in self._queued_keys:
            return False

        event = PendingEvent(
            scheduled_step=scheduled_step,
            sequence=self._sequence,
            event_id=self.next_event_id,
            agent_a_uid=first,
            agent_b_uid=second,
            rule_id=rule_id,
            pair_rule_key=pair_rule_key,
        )
        self._sequence += 1
        self.next_event_id += 1
        self._queued_keys.add(pair_rule_key)
        heapq.heappush(self._heap, event)
        return True

    def pop_due(self, step_index: int) -> list[PendingEvent]:
        due: list[PendingEvent] = []
        while self._heap and self._heap[0].scheduled_step <= step_index:
            event = heapq.heappop(self._heap)
            self._queued_keys.discard(event.pair_rule_key)
            due.append(event)
        return due

    def is_queued(self, agent_a_uid: int, agent_b_uid: int, rule_id: str) -> bool:
        first, second = sorted((agent_a_uid, agent_b_uid))
        return (first, second, rule_id) in self._queued_keys

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrafficLightRuntimeState:
    status: str = "GREEN"
    lamport_clock: int = 0
    active_green_group: str | None = None
    green_elapsed: int = 0
    waiting_seconds_by_edge: dict[tuple[int, int], int] = field(default_factory=dict)
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VehicleRuntimeState:
    path: list[int] = field(default_factory=list)
    destination: Optional[int] = None
    status: str = "QUEUED"
    travel_timer: int = 0
    edge_total_timer: int = 0
    lamport_clock: int = 0
    next_node_buffer: Optional[int] = None
    sensor_registered: bool = False
    sensor_target_intersection: Optional[int] = None


@dataclass(frozen=True)
class StepContext:
    current_node: int
    next_node: int
    current_intersection: int
    next_intersection: int
    external_entry: bool

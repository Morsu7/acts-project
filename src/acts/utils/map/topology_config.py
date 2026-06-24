from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt


@dataclass(frozen=True)
class TopologyConfig:
    num_nodes: int = 10
    road_probability: float = 0.90
    diagonal_road_probability: float = 0.45
    bidirectional_probability: float = 0.45
    extra_turn_probability: float = 0.45
    # Distance of lane ports from the intersection center (normalized [0, 1] coordinates).
    port_offset: float = 0.09
    # How many random topology generations to try before accepting the last one.
    max_connectivity_attempts: int = 50
    # Extra rounds used when reconnecting weakly connected areas.
    reconnect_round_multiplier: int = 2

    @property
    def cols(self) -> int:
        return ceil(sqrt(self.num_nodes))

    @property
    def rows(self) -> int:
        return ceil(self.num_nodes / self.cols)

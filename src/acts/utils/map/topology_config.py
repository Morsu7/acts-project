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
    # How many random topology generations to try before accepting the last one.
    max_connectivity_attempts: int = 50
    # Extra rounds used when reconnecting weakly connected areas.
    reconnect_round_multiplier: int = 2

    # The size of each block in meters (used for calculating the length of edges).
    block_size_meters: float = 100.0
    # Distance of lane ports from the intersection center in meters
    port_offset: float = 20

    @property
    def cols(self) -> int:
        return ceil(sqrt(self.num_nodes))

    @property
    def rows(self) -> int:
        return ceil(self.num_nodes / self.cols)

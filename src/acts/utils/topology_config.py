from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt


@dataclass(frozen=True)
class TopologyConfig:
    num_nodes: int = 10
    road_probability: float = 0.75
    diagonal_road_probability: float = 0.45
    bidirectional_probability: float = 0.45
    extra_turn_probability: float = 0.45
    port_offset: float = 0.09
    max_connectivity_attempts: int = 50
    reconnect_round_multiplier: int = 2

    def normalized(self) -> "TopologyConfig":
        num_nodes = max(1, int(self.num_nodes))
        return TopologyConfig(
            num_nodes=num_nodes,
            road_probability=_clamp_probability(self.road_probability),
            diagonal_road_probability=_clamp_probability(self.diagonal_road_probability),
            bidirectional_probability=_clamp_probability(self.bidirectional_probability),
            extra_turn_probability=_clamp_probability(self.extra_turn_probability),
            port_offset=max(0.0, min(float(self.port_offset), 0.5)),
            max_connectivity_attempts=max(1, int(self.max_connectivity_attempts)),
            reconnect_round_multiplier=max(1, int(self.reconnect_round_multiplier)),
        )

    @property
    def cols(self) -> int:
        return ceil(sqrt(self.num_nodes))

    @property
    def rows(self) -> int:
        return ceil(self.num_nodes / self.cols)


def _clamp_probability(value: float) -> float:
    return max(0.0, min(float(value), 1.0))

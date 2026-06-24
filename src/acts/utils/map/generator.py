from __future__ import annotations

from typing import Optional

import networkx as nx

from acts.utils.map.topology_builder import TopologyBuilder
from acts.utils.map.topology_config import TopologyConfig


def generate_topology(
    num_nodes: int = 10,
    max_degree: int = 5,
    grid_size: int = 15,
    cell_size: int = 5,
    seed: Optional[int] = None,
) -> nx.DiGraph:
    _ = (max_degree, grid_size, cell_size)

    config = TopologyConfig(num_nodes=num_nodes)
    return TopologyBuilder(config=config, seed=seed).build()
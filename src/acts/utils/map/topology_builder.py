from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional

import networkx as nx

from acts.utils.map.topology_config import TopologyConfig


@dataclass(frozen=True)
class _IntersectionInfo:
    node_id: int
    row: int
    col: int


class TopologyBuilder:
    def __init__(self, config: TopologyConfig, seed: Optional[int] = None):
        self.config = config
        self.random_generator = random.Random(seed)

    def build(self) -> nx.DiGraph:
        base_pos = self._build_base_positions()
        base_edges = self._build_connected_base_edges()
        graph, neighbors_map, port_of = self._expand_intersections(base_pos, base_edges)
        self._connect_roads(graph, base_edges, port_of)
        self._connect_internal_turns(graph, neighbors_map, port_of)
        self._enforce_strong_connectivity(graph)
        self._set_graph_metadata(graph, base_pos, base_edges, neighbors_map)
        return graph

    def _build_base_positions(self) -> dict[int, tuple[float, float]]:
        positions: dict[int, tuple[float, float]] = {}
        cols = self.config.cols
        rows = self.config.rows

        for node_id in range(self.config.num_nodes):
            row = node_id // cols
            col = node_id % cols
            x = col / max(cols - 1, 1)
            y = row / max(rows - 1, 1)
            positions[node_id] = (x, y)

        return positions

    def _build_connected_base_edges(self) -> list[tuple[int, int]]:
        candidate_edges: list[tuple[int, int]] = []
        for _ in range(self.config.max_connectivity_attempts):
            candidate_edges = self._build_base_edges()
            if self._is_base_connected(candidate_edges):
                return candidate_edges

        return candidate_edges

    def _build_base_edges(self) -> list[tuple[int, int]]:
        edges: list[tuple[int, int]] = []
        cols = self.config.cols
        rows = self.config.rows

        for node_id in range(self.config.num_nodes):
            intersection = _IntersectionInfo(node_id=node_id, row=node_id // cols, col=node_id % cols)

            right = node_id + 1
            down = node_id + cols
            down_right = node_id + cols + 1
            down_left = node_id + cols - 1

            if (
                intersection.col < cols - 1
                and right < self.config.num_nodes
                and self.random_generator.random() < self.config.road_probability
            ):
                edges.append((node_id, right))

            if (
                intersection.row < rows - 1
                and down < self.config.num_nodes
                and self.random_generator.random() < self.config.road_probability
            ):
                edges.append((node_id, down))

            if (
                intersection.row < rows - 1
                and intersection.col < cols - 1
                and down_right < self.config.num_nodes
                and self.random_generator.random() < self.config.diagonal_road_probability
            ):
                edges.append((node_id, down_right))

            if (
                intersection.row < rows - 1
                and intersection.col > 0
                and down_left < self.config.num_nodes
                and self.random_generator.random() < self.config.diagonal_road_probability
            ):
                edges.append((node_id, down_left))

        return edges

    def _is_base_connected(self, edges: list[tuple[int, int]]) -> bool:
        if self.config.num_nodes <= 1:
            return True

        graph = nx.Graph()
        graph.add_nodes_from(range(self.config.num_nodes))
        graph.add_edges_from(edges)
        return nx.is_connected(graph)

    def _expand_intersections(
        self,
        base_pos: dict[int, tuple[float, float]],
        base_edges: list[tuple[int, int]],
    ) -> tuple[nx.DiGraph, dict[int, list[int]], dict[tuple[int, int], int]]:
        graph = nx.DiGraph()
        neighbors_map: dict[int, list[int]] = {n: [] for n in range(self.config.num_nodes)}

        for u, v in base_edges:
            neighbors_map[u].append(v)
            neighbors_map[v].append(u)

        port_of: dict[tuple[int, int], int] = {}
        next_port_id = 0

        for center in range(self.config.num_nodes):
            cx, cy = base_pos[center]
            local_neighbors = neighbors_map[center]

            if not local_neighbors:
                node_id = next_port_id
                next_port_id += 1
                graph.add_node(
                    node_id,
                    pos=(cx, cy),
                    intersection=center,
                    is_pass_through=True,
                )
                port_of[(center, -1)] = node_id
                continue

            for other in local_neighbors:
                px, py = self._offset_position(base_pos[center], base_pos[other])
                port_id = next_port_id
                next_port_id += 1
                graph.add_node(
                    port_id,
                    pos=(px, py),
                    intersection=center,
                    neighbor_intersection=other,
                )
                port_of[(center, other)] = port_id

        return graph, neighbors_map, port_of

    def _offset_position(
        self,
        center: tuple[float, float],
        neighbor: tuple[float, float],
    ) -> tuple[float, float]:
        cx, cy = center
        ox, oy = neighbor
        dx = ox - cx
        dy = oy - cy
        norm = math.sqrt(dx * dx + dy * dy)
        ux, uy = (0.0, 0.0) if norm == 0 else (dx / norm, dy / norm)

        px = min(1.0, max(0.0, cx + ux * self.config.port_offset))
        py = min(1.0, max(0.0, cy + uy * self.config.port_offset))
        return px, py

    def _connect_roads(
        self,
        graph: nx.DiGraph,
        base_edges: list[tuple[int, int]],
        port_of: dict[tuple[int, int], int],
    ) -> None:
        for u, v in base_edges:
            u_pass_through = (u, -1) in port_of
            v_pass_through = (v, -1) in port_of

            if u_pass_through and v_pass_through:
                self._add_random_connection(graph, port_of[(u, -1)], port_of[(v, -1)], edge_kind="road")
                continue

            if u_pass_through and (v, u) in port_of:
                self._add_random_connection(graph, port_of[(u, -1)], port_of[(v, u)], edge_kind="road")
                continue

            if v_pass_through and (u, v) in port_of:
                self._add_random_connection(graph, port_of[(u, v)], port_of[(v, -1)], edge_kind="road")
                continue

            if (u, v) in port_of and (v, u) in port_of:
                self._add_random_connection(graph, port_of[(u, v)], port_of[(v, u)], edge_kind="road")

    def _connect_internal_turns(
        self,
        graph: nx.DiGraph,
        neighbors_map: dict[int, list[int]],
        port_of: dict[tuple[int, int], int],
    ) -> None:
        for center in range(self.config.num_nodes):
            local_neighbors = neighbors_map[center]
            if len(local_neighbors) <= 1:
                continue

            local_ports = [port_of[(center, other)] for other in local_neighbors]
            if len(local_ports) < 2:
                continue

            entry_ports = [
                port
                for port in local_ports
                if self._has_incoming_road_from_other_intersection(graph, port, center)
            ]

            exit_ports = [
                port
                for port in local_ports
                if self._has_outgoing_road_to_other_intersection(graph, port, center)
            ]
            if not entry_ports or not exit_ports:
                continue

            if len(local_ports) == 2:
                source_a, source_b = local_ports
                if source_a in entry_ports and source_b in exit_ports:
                    self._add_directed(graph, source_a, source_b, edge_kind="turn")
                if source_b in entry_ports and source_a in exit_ports:
                    self._add_directed(graph, source_b, source_a, edge_kind="turn")
                continue

            for source_port in entry_ports:
                available_targets = [target_port for target_port in exit_ports if target_port != source_port]
                if not available_targets:
                    continue
                target_port = self.random_generator.choice(available_targets)
                self._add_directed(graph, source_port, target_port, edge_kind="turn")

            for source_port in entry_ports:
                for target_port in exit_ports:
                    if source_port == target_port or graph.has_edge(source_port, target_port):
                        continue
                    if self.random_generator.random() < self.config.extra_turn_probability:
                        self._add_directed(graph, source_port, target_port, edge_kind="turn")

    def _has_incoming_road_from_other_intersection(
        self,
        graph: nx.DiGraph,
        node_id: int,
        intersection_id: int,
    ) -> bool:
        for source_id, _, edge_data in graph.in_edges(node_id, data=True):
            if edge_data.get("edge_kind") != "road":
                continue
            source_intersection = graph.nodes[source_id].get("intersection", source_id)
            if source_intersection != intersection_id:
                return True
        return False

    def _has_outgoing_road_to_other_intersection(
        self,
        graph: nx.DiGraph,
        node_id: int,
        intersection_id: int,
    ) -> bool:
        for _, target_id, edge_data in graph.out_edges(node_id, data=True):
            if edge_data.get("edge_kind") != "road":
                continue
            target_intersection = graph.nodes[target_id].get("intersection", target_id)
            if target_intersection != intersection_id:
                return True
        return False

    def _enforce_strong_connectivity(self, graph: nx.DiGraph) -> None:
        if graph.number_of_nodes() <= 1:
            return

        max_rounds = graph.number_of_nodes() * self.config.reconnect_round_multiplier

        for _ in range(max_rounds):
            if nx.is_strongly_connected(graph):
                return

            sccs = list(nx.strongly_connected_components(graph))
            condensation = nx.condensation(graph, sccs)
            source_components = [c for c in condensation.nodes() if condensation.in_degree(c) == 0]
            sink_components = [c for c in condensation.nodes() if condensation.out_degree(c) == 0]

            if not source_components or not sink_components:
                break

            links_to_add = max(len(source_components), len(sink_components))
            for i in range(links_to_add):
                sink_comp = sink_components[i % len(sink_components)]
                source_comp = source_components[(i + 1) % len(source_components)]

                sink_member = next(iter(condensation.nodes[sink_comp]["members"]))
                source_member = next(iter(condensation.nodes[source_comp]["members"]))
                self._add_directed(graph, sink_member, source_member, edge_kind="reconnect")

        if nx.is_strongly_connected(graph):
            return

        fallback_nodes = list(graph.nodes())
        for i in range(len(fallback_nodes)):
            self._add_directed(
                graph,
                fallback_nodes[i],
                fallback_nodes[(i + 1) % len(fallback_nodes)],
                edge_kind="reconnect",
            )

    def _set_graph_metadata(
        self,
        graph: nx.DiGraph,
        base_pos: dict[int, tuple[float, float]],
        base_edges: list[tuple[int, int]],
        neighbors_map: dict[int, list[int]],
    ) -> None:
        intersections_meta = {}

        for intersection_id in range(self.config.num_nodes):
            intersection_nodes = [
                node_id
                for node_id, attrs in graph.nodes(data=True)
                if attrs.get("intersection") == intersection_id
            ]
            sorted_nodes = sorted(intersection_nodes)
            priority_edge_groups = self._build_random_edge_groups(graph, sorted_nodes)
            intersections_meta[intersection_id] = {
                "nodes": sorted_nodes,
                "priority_nodes": sorted_nodes,
                "priority_edge_groups": priority_edge_groups,
                "min_green_duration": 5,
                "priority_weights": {
                    "waiting_cars": 1.0,
                    "waiting_seconds": 1.0,
                },
                "is_pass_through": len(neighbors_map[intersection_id]) <= 2,
                "neighbor_intersections": sorted(neighbors_map[intersection_id]),
                "position": base_pos[intersection_id],
            }

        graph.graph["base_intersection_count"] = self.config.num_nodes
        graph.graph["roads"] = sorted(tuple(sorted((u, v))) for u, v in base_edges)
        graph.graph["intersections"] = intersections_meta

    def _build_random_edge_groups(
        self,
        graph: nx.DiGraph,
        intersection_nodes: list[int],
    ) -> list[list[list[int]]]:
        nodes_set = set(intersection_nodes)
        groups: list[list[list[int]]] = []

        for source_node in intersection_nodes:
            outgoing = [
                target_node
                for _, target_node in graph.out_edges(source_node)
                if target_node in nodes_set
            ]
            outgoing = sorted(outgoing)

            if not outgoing:
                continue

            partitions = self._partition_targets_randomly(outgoing)
            for partition in partitions:
                groups.append([[source_node, target_node] for target_node in partition])

        return groups

    def _partition_targets_randomly(self, targets: list[int]) -> list[list[int]]:
        if not targets:
            return []

        if len(targets) == 1:
            return [targets[:]]

        shuffled = targets[:]
        self.random_generator.shuffle(shuffled)

        max_groups = len(shuffled)
        num_groups = self.random_generator.randint(1, max_groups)

        partitions: list[list[int]] = [[] for _ in range(num_groups)]
        for index, target in enumerate(shuffled):
            partitions[index % num_groups].append(target)

        for partition in partitions:
            partition.sort()

        return partitions

    def _add_random_connection(self, graph: nx.DiGraph, u: int, v: int, edge_kind: str) -> None:
        if self.random_generator.random() < self.config.bidirectional_probability:
            self._add_directed(graph, u, v, edge_kind=edge_kind)
            self._add_directed(graph, v, u, edge_kind=edge_kind)
            return

        if self.random_generator.random() < 0.5:
            self._add_directed(graph, u, v, edge_kind=edge_kind)
        else:
            self._add_directed(graph, v, u, edge_kind=edge_kind)

    def _add_directed(self, graph: nx.DiGraph, u: int, v: int, edge_kind: str) -> None:
        p1 = graph.nodes[u]["pos"]
        p2 = graph.nodes[v]["pos"]
        dist = math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

        if graph.has_edge(u, v):
            return

        graph.add_edge(u, v, weight=dist, edge_kind=edge_kind)

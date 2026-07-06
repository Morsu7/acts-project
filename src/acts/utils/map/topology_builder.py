from __future__ import annotations

import math
import random
from typing import Optional, Any

import networkx as nx

from acts.map import RoadNetwork

class TopologyBuilder:

    def __init__(self, config: Any, seed: Optional[int] = None):
        self.config = config
        self.random_generator = random.Random(seed)
        self.network = RoadNetwork()

    def build(self) -> nx.DiGraph:
        base_pos = self._build_base_positions()
        base_graph = self._build_strongly_connected_base(base_pos)
        base_edges = list(base_graph.edges())
        
        for node_id, pos in base_pos.items():
            self.network.set_intersection_center(node_id, pos)

        neighbors_map, port_of = self._expand_intersections(base_pos, base_edges)
        self._connect_roads(base_edges, port_of)
        self._connect_internal_turns(neighbors_map, port_of)
        
        for intersection_id in range(self.config.num_nodes):
            sorted_nodes = sorted([
                n for n, attrs in self.network.graph.nodes(data=True) 
                if attrs.get("intersection") == intersection_id
            ])
            
            # Genera fasi randomiche
            random_phases = {f"tl_{n}_dir0": self.random_generator.randint(1, max(1, len(sorted_nodes))) for n in sorted_nodes}
            self.network.set_intersection_phases(intersection_id, random_phases)
            
            # Genera gruppi di priorità randomici usando la vecchia funzione del builder
            random_groups = self._build_random_edge_groups(sorted_nodes)
            self.network.set_intersection_priority_groups(intersection_id, random_groups)
        
        # Compilazione finale (ora puramente deterministica sulle strutture)
        self.network.compile_metadata()
        
        return self.network.graph

    def _build_random_edge_groups(self, intersection_nodes: list[int]) -> list[list[list[int]]]:
        nodes_set = set(intersection_nodes)
        groups = []
        for source_node in intersection_nodes:
            outgoing = sorted([v for _, v in self.network.graph.out_edges(source_node) if v in nodes_set])
            if not outgoing: continue
            
            # Partizionamento randomico spostato qui nel builder
            shuffled = outgoing[:]
            self.random_generator.shuffle(shuffled)
            num_groups = self.random_generator.randint(1, len(shuffled))
            partitions = [[] for _ in range(num_groups)]
            for index, target in enumerate(shuffled):
                partitions[index % num_groups].append(target)
            
            for partition in partitions:
                partition.sort()
                groups.append([[source_node, target_node] for target_node in partition])
        return groups

    def _build_base_positions(self) -> dict[int, tuple[float, float]]:
        positions: dict[int, tuple[float, float]] = {}
        cols, rows = self.config.cols, self.config.rows

        for node_id in range(self.config.num_nodes):
            row = node_id // cols
            col = node_id % cols
            x = col / (cols - 1) if cols > 1 else 0.5
            y = row / (rows - 1) if rows > 1 else 0.5
            positions[node_id] = (x, y)

        return positions

    def _build_strongly_connected_base(self, base_pos: dict[int, tuple[float, float]]) -> nx.DiGraph:
        cols, rows = self.config.cols, self.config.rows
        num_nodes = self.config.num_nodes
        
        base_ugraph = nx.Graph()
        base_ugraph.add_nodes_from(range(num_nodes))
        
        for node_id in range(num_nodes):
            col = node_id % cols
            row = node_id // cols
            
            neighbors = []
            if col < cols - 1: 
                neighbors.append((node_id + 1, self.config.road_probability))
            if row < rows - 1: 
                neighbors.append((node_id + cols, self.config.road_probability))
            if row < rows - 1 and col < cols - 1: 
                neighbors.append((node_id + cols + 1, self.config.diagonal_road_probability))
            if row < rows - 1 and col > 0: 
                neighbors.append((node_id + cols - 1, self.config.diagonal_road_probability))

            for neighbor, prob in neighbors:
                if neighbor < num_nodes and self.random_generator.random() < prob:
                    base_ugraph.add_edge(node_id, neighbor)

        while not nx.is_connected(base_ugraph):
            components = list(nx.connected_components(base_ugraph))
            comp_a = components[0]
            
            found_connection = False
            for node_a in comp_a:
                col_a, row_a = node_a % cols, node_a // cols
                
                potential_neighbors = []
                if col_a > 0: potential_neighbors.append(node_a - 1)
                if col_a < cols - 1: potential_neighbors.append(node_a + 1)
                if row_a > 0: potential_neighbors.append(node_a - cols)
                if row_a < rows - 1: potential_neighbors.append(node_a + cols)
                
                for neighbor in potential_neighbors:
                    if neighbor not in comp_a:
                        base_ugraph.add_edge(node_a, neighbor)
                        found_connection = True
                        break
                if found_connection:
                    break
            
            if not found_connection:
                break 

        base_digraph = nx.DiGraph()
        base_digraph.add_nodes_from(base_ugraph.nodes())
        
        for u, v in base_ugraph.edges():
            rand = self.random_generator.random()
            if rand < self.config.bidirectional_probability:
                base_digraph.add_edge(u, v)
                base_digraph.add_edge(v, u)
            elif rand < 0.5:
                base_digraph.add_edge(u, v)
            else:
                base_digraph.add_edge(v, u)

        for n in base_digraph.nodes():
            if base_digraph.in_degree(n) == 0 and base_digraph.out_degree(n) > 0:
                target = list(base_digraph.successors(n))[0]
                base_digraph.add_edge(target, n)
            elif base_digraph.out_degree(n) == 0 and base_digraph.in_degree(n) > 0:
                source = list(base_digraph.predecessors(n))[0]
                base_digraph.add_edge(n, source)
                
        while not nx.is_strongly_connected(base_digraph):
            sccs = list(nx.strongly_connected_components(base_digraph))
            if len(sccs) <= 1:
                break
            
            comp_a = sccs[0]
            repaired = False
            
            for u in comp_a:
                for v in base_digraph.successors(u):
                    if v not in comp_a:
                        base_digraph.add_edge(v, u)
                        repaired = True
                        break
                if repaired: 
                    break
            
            if not repaired:
                for u in comp_a:
                    for v in base_ugraph.neighbors(u):
                        if v not in comp_a:
                            base_digraph.add_edge(u, v)
                            base_digraph.add_edge(v, u)
                            repaired = True
                            break
                    if repaired: 
                        break

        return base_digraph

    def _expand_intersections(
        self,
        base_pos: dict[int, tuple[float, float]],
        base_edges: list[tuple[int, int]],
    ) -> tuple[dict[int, list[int]], dict[tuple[int, int], int]]:
        neighbors_map: dict[int, list[int]] = {n: [] for n in range(self.config.num_nodes)}

        for u, v in base_edges:
            if v not in neighbors_map[u]: neighbors_map[u].append(v)
            if u not in neighbors_map[v]: neighbors_map[v].append(u)

        port_of: dict[tuple[int, int], int] = {}
        next_port_id = 0

        for center in range(self.config.num_nodes):
            cx, cy = base_pos[center]
            local_neighbors = neighbors_map[center]

            if not local_neighbors:
                self.network.add_port(next_port_id, center, (cx, cy), is_pass_through=True)
                port_of[(center, -1)] = next_port_id
                next_port_id += 1
                continue

            for other in local_neighbors:
                px, py = self._offset_position(base_pos[center], base_pos[other])
                self.network.add_port(next_port_id, center, (px, py))
                port_of[(center, other)] = next_port_id
                next_port_id += 1

        return neighbors_map, port_of

    def _offset_position(self, center: tuple[float, float], neighbor: tuple[float, float]) -> tuple[float, float]:
        cx, cy = center
        dx, dy = neighbor[0] - cx, neighbor[1] - cy
        norm = math.hypot(dx, dy)
        
        ux, uy = (dx / norm, dy / norm) if norm > 0 else (0.0, 0.0)
        px = max(0.0, min(1.0, cx + ux * self.config.port_offset))
        py = max(0.0, min(1.0, cy + uy * self.config.port_offset))
        return px, py

    def _connect_roads(self, base_edges: list[tuple[int, int]], port_of: dict[tuple[int, int], int]) -> None:
        for u, v in base_edges:
            u_port = port_of.get((u, v))
            v_port = port_of.get((v, u))
            
            if u_port is not None and v_port is not None:
                p1, p2 = self.network.graph.nodes[u_port]["pos"], self.network.graph.nodes[v_port]["pos"]
                
                map_scale_meters = getattr(self.config, "map_scale_meters", 500.0)
                geo_length = math.hypot(p1[0] - p2[0], p1[1] - p2[1]) * map_scale_meters
                
                road_tier = self.random_generator.choice(["local", "arterial", "highway"])
                match road_tier:
                    case "highway": road_speed = 25.0
                    case "arterial": road_speed = 14.0
                    case "local" | _: road_speed = 8.0
                
                self.network.add_road_edge(u_port, v_port, length=geo_length, max_speed=road_speed, tier=road_tier)

    def _connect_internal_turns(self, neighbors_map: dict[int, list[int]], port_of: dict[tuple[int, int], int]) -> None:
        for center in range(self.config.num_nodes):
            local_neighbors = neighbors_map[center]
            
            if len(local_neighbors) <= 1:
                if len(local_neighbors) == 1:
                    port = port_of[(center, local_neighbors[0])]
                    self.network.add_turn_edge(port, port, edge_kind="u_turn")
                continue

            local_ports = [port_of[(center, other)] for other in local_neighbors]
            entry_ports = [p for p in local_ports if self._check_road_direction(p, center, is_incoming=True)]
            exit_ports = [p for p in local_ports if self._check_road_direction(p, center, is_incoming=False)]

            if not entry_ports or not exit_ports:
                entry_ports = exit_ports = local_ports

            for source_port in entry_ports:
                available_targets = [t for t in exit_ports if t != source_port]
                if not available_targets:
                    available_targets = [source_port]
                
                target_port = self.random_generator.choice(available_targets)
                self.network.add_turn_edge(source_port, target_port, edge_kind="turn")

                for extra_target in available_targets:
                    if extra_target != target_port and self.random_generator.random() < self.config.extra_turn_probability:
                        self.network.add_turn_edge(source_port, extra_target, edge_kind="turn")

            for port in local_ports:
                other_ports = [p for p in local_ports if p != port]
                if not other_ports: continue
                
                internal_in_edges = [s for s, t in self.network.graph.in_edges(port) if s in local_ports]
                if not internal_in_edges:
                    p_pos = self.network.graph.nodes[port]["pos"]
                    closest_source = min(
                        other_ports, 
                        key=lambda op: math.hypot(self.network.graph.nodes[op]["pos"][0] - p_pos[0], self.network.graph.nodes[op]["pos"][1] - p_pos[1])
                    )
                    self.network.add_turn_edge(closest_source, port, edge_kind="turn_fix_internal_in")

                internal_out_edges = [t for s, t in self.network.graph.out_edges(port) if t in local_ports]
                if not internal_out_edges:
                    p_pos = self.network.graph.nodes[port]["pos"]
                    closest_target = min(
                        other_ports, 
                        key=lambda op: math.hypot(self.network.graph.nodes[op]["pos"][0] - p_pos[0], self.network.graph.nodes[op]["pos"][1] - p_pos[1])
                    )
                    self.network.add_turn_edge(port, closest_target, edge_kind="turn_fix_internal_out")

    def _check_road_direction(self, node_id: int, intersection_id: int, is_incoming: bool) -> bool:
        graph = self.network.graph
        edges = graph.in_edges(node_id, data=True) if is_incoming else graph.out_edges(node_id, data=True)
        for u, v, edge_data in edges:
            if edge_data.get("edge_kind") != "road":
                continue
            neighbor = u if is_incoming else v
            neighbor_intersection = graph.nodes[neighbor].get("intersection", neighbor)
            if neighbor_intersection != intersection_id:
                return True
        return False
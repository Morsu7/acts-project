from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional, Any

import networkx as nx

class TopologyBuilder:
    def __init__(self, config: Any, seed: Optional[int] = None):
        self.config = config
        self.random_generator = random.Random(seed)

    def build(self) -> nx.DiGraph:
        base_pos = self._build_base_positions()
        base_graph = self._build_strongly_connected_base(base_pos)
        base_edges = list(base_graph.edges())
        
        # Esplodi le intersezioni nei port interni locali
        graph, neighbors_map, port_of = self._expand_intersections(base_pos, base_edges)
        
        # Collega le strade esterne tra intersezioni diverse
        self._connect_roads(graph, base_edges, port_of)
        
        # Collega le svolte interne applicando i vincoli di connettività interna
        self._connect_internal_turns(graph, neighbors_map, port_of)
        
        # Salva i metadati strutturali nel grafo finale
        self._set_graph_metadata(graph, base_pos, base_edges, neighbors_map)
        
        return graph

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
    ) -> tuple[nx.DiGraph, dict[int, list[int]], dict[tuple[int, int], int]]:
        graph = nx.DiGraph()
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
                graph.add_node(next_port_id, pos=(cx, cy), intersection=center, is_pass_through=True)
                port_of[(center, -1)] = next_port_id
                next_port_id += 1
                continue

            for other in local_neighbors:
                px, py = self._offset_position(base_pos[center], base_pos[other])
                graph.add_node(next_port_id, pos=(px, py), intersection=center)
                port_of[(center, other)] = next_port_id
                next_port_id += 1

        return graph, neighbors_map, port_of

    def _offset_position(self, center: tuple[float, float], neighbor: tuple[float, float]) -> tuple[float, float]:
        cx, cy = center
        dx, dy = neighbor[0] - cx, neighbor[1] - cy
        norm = math.hypot(dx, dy)
        
        ux, uy = (dx / norm, dy / norm) if norm > 0 else (0.0, 0.0)
        px = max(0.0, min(1.0, cx + ux * self.config.port_offset))
        py = max(0.0, min(1.0, cy + uy * self.config.port_offset))
        return px, py

    def _connect_roads(self, graph: nx.DiGraph, base_edges: list[tuple[int, int]], port_of: dict[tuple[int, int], int]) -> None:
        for u, v in base_edges:
            u_port = port_of.get((u, v))
            v_port = port_of.get((v, u))
            
            if u_port is not None and v_port is not None:
                p1, p2 = graph.nodes[u_port]["pos"], graph.nodes[v_port]["pos"]
                
                # 1. Calculate realistic physical distance in meters
                # Assuming the 0.0-1.0 grid spans 500 meters across
                map_scale_meters = getattr(self.config, "map_scale_meters", 500.0)
                geo_length = math.hypot(p1[0] - p2[0], p1[1] - p2[1]) * map_scale_meters
                
                # 2. Assign Road Tier and Speed (meters/tick)
                road_tier = self.random_generator.choice(["local", "arterial", "highway"])
                
                match road_tier:
                    case "highway":
                        road_speed = 25.0   # e.g., ~90 km/h scaled to meters/tick
                    case "arterial":
                        road_speed = 14.0   # e.g., ~50 km/h scaled to meters/tick
                    case "local" | _:
                        road_speed = 8.0    # e.g., ~30 km/h scaled to meters/tick
                
                graph.add_edge(
                    u_port, v_port, 
                    weight=geo_length, 
                    length=geo_length,
                    max_speed=road_speed,
                    edge_kind="road",
                    tier=road_tier
                )

    def _connect_internal_turns(self, graph: nx.DiGraph, neighbors_map: dict[int, list[int]], port_of: dict[tuple[int, int], int]) -> None:
        for center in range(self.config.num_nodes):
            local_neighbors = neighbors_map[center]
            
            if len(local_neighbors) <= 1:
                if len(local_neighbors) == 1:
                    port = port_of[(center, local_neighbors[0])]
                    self._add_directed(graph, port, port, edge_kind="u_turn")
                continue

            local_ports = [port_of[(center, other)] for other in local_neighbors]
            entry_ports = [p for p in local_ports if self._check_road_direction(graph, p, center, is_incoming=True)]
            exit_ports = [p for p in local_ports if self._check_road_direction(graph, p, center, is_incoming=False)]

            if not entry_ports or not exit_ports:
                entry_ports = exit_ports = local_ports

            # Generazione iniziale delle svolte
            for source_port in entry_ports:
                available_targets = [t for t in exit_ports if t != source_port]
                if not available_targets:
                    available_targets = [source_port]
                
                target_port = self.random_generator.choice(available_targets)
                self._add_directed(graph, source_port, target_port, edge_kind="turn")

                for extra_target in available_targets:
                    if extra_target != target_port and self.random_generator.random() < self.config.extra_turn_probability:
                        self._add_directed(graph, source_port, extra_target, edge_kind="turn")

            # --- CORREZIONE COMPLETA DEI GRADI DI CONNETTIVITÀ INTERNA ---
            # Isoliando l'incrocio, nessun port deve avere in_degree interno == 0 o out_degree interno == 0.
            for port in local_ports:
                other_ports = [p for p in local_ports if p != port]
                if not other_ports:
                    continue
                
                # Calcola quanti archi INTERNI (svolte) ENTRANO in questo port
                internal_in_edges = [s for s, t in graph.in_edges(port) if s in local_ports]
                
                # SE NON ENTRA NESSUN ARCO INTERNO (Il tuo caso specifico: era un nodo di sola uscita interna)
                if not internal_in_edges:
                    p_pos = graph.nodes[port]["pos"]
                    # Trova il port interno dell'incrocio geometricamente più vicino
                    closest_source = min(
                        other_ports, 
                        key=lambda op: math.hypot(graph.nodes[op]["pos"][0] - p_pos[0], graph.nodes[op]["pos"][1] - p_pos[1])
                    )
                    # Forza una svolta interna dal port più vicino verso questo port
                    self._add_directed(graph, closest_source, port, edge_kind="turn_fix_internal_in")

                # Calcola quanti archi INTERNI (svolte) ESCONO da questo port
                internal_out_edges = [t for s, t in graph.out_edges(port) if t in local_ports]
                
                # SE NON ESCE NESSUN ARCO INTERNO (Nodo di sola entrata interna)
                if not internal_out_edges:
                    p_pos = graph.nodes[port]["pos"]
                    closest_target = min(
                        other_ports, 
                        key=lambda op: math.hypot(graph.nodes[op]["pos"][0] - p_pos[0], graph.nodes[op]["pos"][1] - p_pos[1])
                    )
                    # Forza una svolta interna da questo port verso il port più vicino
                    self._add_directed(graph, port, closest_target, edge_kind="turn_fix_internal_out")

    def _check_road_direction(self, graph: nx.DiGraph, node_id: int, intersection_id: int, is_incoming: bool) -> bool:
        edges = graph.in_edges(node_id, data=True) if is_incoming else graph.out_edges(node_id, data=True)
        for u, v, edge_data in edges:
            if edge_data.get("edge_kind") != "road":
                continue
            neighbor = u if is_incoming else v
            neighbor_intersection = graph.nodes[neighbor].get("intersection", neighbor)
            if neighbor_intersection != intersection_id:
                return True
        return False

    def _set_graph_metadata(self, graph: nx.DiGraph, base_pos: dict[int, tuple[float, float]], base_edges: list[tuple[int, int]], neighbors_map: dict[int, list[int]]) -> None:
        intersections_meta = {}
        for intersection_id in range(self.config.num_nodes):
            intersection_nodes = [n for n, attrs in graph.nodes(data=True) if attrs.get("intersection") == intersection_id]
            sorted_nodes = sorted(intersection_nodes)
            
            # --- NEW: FIND NEIGHBORING TRAFFIC LIGHTS / EXTERNAL PORTS ---
            neighbor_traffic_lights = set()
            external_connections = []  # List of dicts for exact port-to-port links

            for local_port in sorted_nodes:
                # Look at external roads coming INTO this intersection
                for src, _ in graph.in_edges(local_port):
                    src_meta = graph.nodes[src]
                    src_intersection = src_meta.get("intersection")
                    if src_intersection is not None and src_intersection != intersection_id:
                        # Fetch live edge data attributes
                        edge_data = graph.get_edge_data(src, local_port, default={})
                        
                        neighbor_traffic_lights.add(src_intersection)
                        external_connections.append({
                            "direction": "incoming",
                            "neighbor_intersection": src_intersection,
                            "neighbor_port": src,
                            "local_port": local_port,
                            "length": edge_data.get("length", 100.0),       # Added here
                            "max_speed": edge_data.get("max_speed", 13.89)  # Added here
                        })

                # Look at external roads going OUT of this intersection
                for _, dst in graph.out_edges(local_port):
                    dst_meta = graph.nodes[dst]
                    dst_intersection = dst_meta.get("intersection")
                    if dst_intersection is not None and dst_intersection != intersection_id:
                        # Fetch live edge data attributes
                        edge_data = graph.get_edge_data(local_port, dst, default={})
                        
                        neighbor_traffic_lights.add(dst_intersection)
                        external_connections.append({
                            "direction": "outgoing",
                            "neighbor_intersection": dst_intersection,
                            "neighbor_port": dst,
                            "local_port": local_port,
                            "length": edge_data.get("length", 100.0),       # Added here
                            "max_speed": edge_data.get("max_speed", 13.89)  # Added here
                        })
            # -------------------------------------------------------------

            intersections_meta[intersection_id] = {
                "nodes": sorted_nodes,
                "is_pass_through": len(neighbors_map[intersection_id]) <= 2,
                "neighbor_intersections": sorted(neighbors_map[intersection_id]),
                "position": base_pos[intersection_id],
                "priority_edge_groups": self._build_random_edge_groups(graph, sorted_nodes),
                # Storing the new topology fields here
                "neighbor_traffic_lights": sorted(list(neighbor_traffic_lights)),
                "external_connections": external_connections
            }

        graph.graph["base_intersection_count"] = self.config.num_nodes
        graph.graph["roads"] = sorted(tuple(sorted((u, v))) for u, v in base_edges)
        graph.graph["intersections"] = intersections_meta

    def _build_random_edge_groups(self, graph: nx.DiGraph, intersection_nodes: list[int]) -> list[list[list[int]]]:
        nodes_set = set(intersection_nodes)
        groups: list[list[list[int]]] = []

        for source_node in intersection_nodes:
            outgoing = sorted([v for _, v in graph.out_edges(source_node) if v in nodes_set])
            if not outgoing:
                continue

            for partition in self._partition_targets_randomly(outgoing):
                groups.append([[source_node, target_node] for target_node in partition])
        return groups

    def _partition_targets_randomly(self, targets: list[int]) -> list[list[int]]:
        if not targets:
            return []
        if len(targets) == 1:
            return [targets[:]]

        shuffled = targets[:]
        self.random_generator.shuffle(shuffled)
        num_groups = self.random_generator.randint(1, len(shuffled))

        partitions: list[list[int]] = [[] for _ in range(num_groups)]
        for index, target in enumerate(shuffled):
            partitions[index % num_groups].append(target)

        for p in partitions:
            p.sort()
        return partitions

    def _add_directed(self, graph: nx.DiGraph, u: int, v: int, edge_kind: str) -> None:
        if graph.has_edge(u, v):
            return

        INTERNAL_LENGTH = 15.0  # meters
        INTERNAL_SPEED = INTERNAL_LENGTH / 3.0  # 5.0 meters/tick

        p1, p2 = graph.nodes[u]["pos"], graph.nodes[v]["pos"]
        #dist = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
        graph.add_edge(
            u, 
            v, 
            weight=INTERNAL_LENGTH, 
            edge_kind=edge_kind,
            length=INTERNAL_LENGTH,
            max_speed=INTERNAL_SPEED
        )
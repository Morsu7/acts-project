from __future__ import annotations

import math
from typing import Optional, Any
import networkx as nx


class RoadNetwork:
    """
    Gestisce la struttura fisica del grafo stradale ed espone le operazioni 
    atomiche per la creazione manuale o automatica della topologia.
    """
    def __init__(self):
        self.graph = nx.DiGraph()
        self.intersection_centers: dict[int, tuple[float, float]] = {}
        
        # Archivi per i metadati inseriti manualmente (sovrascrivono i default)
        self.manual_phases: dict[int, dict[str, int]] = {}
        self.manual_priority_groups: dict[int, list[list[list[int]]]] = {}

    def set_intersection_center(self, intersection_id: int, pos: tuple[float, float]) -> None:
        """Definisce la posizione geografica centrale di un'intersezione macro."""
        self.intersection_centers[intersection_id] = pos

    def add_port(self, port_id: int, intersection_id: int, pos: tuple[float, float], is_pass_through: bool = False) -> None:
        """Azione Atomica: Aggiunge un nodo port (corsia interna) associato a un'intersezione."""
        attrs = {"pos": pos, "intersection": intersection_id}
        if is_pass_through:
            attrs["is_pass_through"] = True
        self.graph.add_node(port_id, **attrs)

    def add_road_edge(self, u_port: int, v_port: int, length: float, max_speed: float, tier: str) -> None:
        """Azione Atomica: Collega due port appartenenti a incroci diversi (Strada Esterna)."""
        self.graph.add_edge(
            u_port, v_port,
            weight=length,
            length=length,
            max_speed=max_speed,
            edge_kind="road",
            tier=tier
        )

    def add_turn_edge(self, u_port: int, v_port: int, edge_kind: str, length: float = 15.0, max_speed: float = 5.0) -> None:
        """Azione Atomica: Collega due port interni allo stesso incrocio (Svolta o Inversione)."""
        if self.graph.has_edge(u_port, v_port):
            return
        weight = 999999.0 if edge_kind == "u_turn" else length
        self.graph.add_edge(
            u_port, v_port,
            weight=weight,
            edge_kind=edge_kind,
            length=length,
            max_speed=max_speed
        )

    def set_intersection_phases(self, intersection_id: int, phases: dict[str, int]) -> None:
        """Azione Atomica Manuale: Imposta esplicitamente le fasi semaforiche per un incrocio."""
        self.manual_phases[intersection_id] = phases

    def set_intersection_priority_groups(self, intersection_id: int, groups: list[list[list[int]]]) -> None:
        """Azione Atomica Manuale: Imposta esplicitamente i gruppi di manovre prioritarie."""
        self.manual_priority_groups[intersection_id] = groups

    def compile_metadata(self) -> None:
        """
        Raccoglie le connessioni geografiche ed assegna default fissi se i metadati 
        comportamentali (fasi, priorità) non sono stati impostati manualmente.
        """
        intersections = {
            attrs["intersection"] 
            for _, attrs in self.graph.nodes(data=True) 
            if "intersection" in attrs
        }
        
        base_intersection_count = max(intersections) + 1 if intersections else 0
        self.graph.graph["base_intersection_count"] = base_intersection_count

        # Ricostruzione deterministica di macro-strade e vicini
        base_edges_set = set()
        neighbors_map: dict[int, set[int]] = {i: set() for i in intersections}

        for u, v, data in self.graph.edges(data=True):
            if data.get("edge_kind") == "road":
                u_int = self.graph.nodes[u].get("intersection")
                v_int = self.graph.nodes[v].get("intersection")
                if u_int is not None and v_int is not None and u_int != v_int:
                    base_edges_set.add(tuple(sorted((u_int, v_int))))
                    neighbors_map[u_int].add(v_int)
                    neighbors_map[v_int].add(u_int)

        self.graph.graph["roads"] = sorted(list(base_edges_set))
        intersections_meta = {}

        for intersection_id in intersections:
            sorted_nodes = sorted([
                n for n, attrs in self.graph.nodes(data=True) 
                if attrs.get("intersection") == intersection_id
            ])

            neighbor_traffic_lights = set()
            external_connections = []

            for local_port in sorted_nodes:
                # Ingressi esterni
                for src, _ in self.graph.in_edges(local_port):
                    src_int = self.graph.nodes[src].get("intersection")
                    if src_int is not None and src_int != intersection_id:
                        edge_data = self.graph.get_edge_data(src, local_port, default={})
                        neighbor_traffic_lights.add(src_int)
                        external_connections.append({
                            "direction": "incoming",
                            "neighbor_intersection": src_int,
                            "neighbor_port": src,
                            "local_port": local_port,
                            "length": edge_data.get("length", 100.0),
                            "max_speed": edge_data.get("max_speed", 13.89)
                        })

                # Uscite esterne
                for _, dst in self.graph.out_edges(local_port):
                    dst_int = self.graph.nodes[dst].get("intersection")
                    if dst_int is not None and dst_int != intersection_id:
                        edge_data = self.graph.get_edge_data(local_port, dst, default={})
                        neighbor_traffic_lights.add(dst_int)
                        external_connections.append({
                            "direction": "outgoing",
                            "neighbor_intersection": dst_int,
                            "neighbor_port": dst,
                            "local_port": local_port,
                            "length": edge_data.get("length", 100.0),
                            "max_speed": edge_data.get("max_speed", 13.89)
                        })
            
            local_phases = self.manual_phases.get(intersection_id)
            if local_phases is None:
                local_phases = {f"tl_{n}_dir0": 1 for n in sorted_nodes}

            edge_groups = self.manual_priority_groups.get(intersection_id)
            if edge_groups is None:
                edge_groups = self._build_deterministic_edge_groups(sorted_nodes)

            intersections_meta[intersection_id] = {
                "nodes": sorted_nodes,
                "is_pass_through": len(neighbors_map.get(intersection_id, set())) <= 2,
                "neighbor_intersections": sorted(list(neighbors_map.get(intersection_id, set()))),
                "position": self.intersection_centers.get(intersection_id, (0.0, 0.0)),
                "priority_edge_groups": edge_groups,
                "neighbor_traffic_lights": sorted(list(neighbor_traffic_lights)),
                "external_connections": external_connections,
                "phases": local_phases
            }

        self.graph.graph["intersections"] = intersections_meta

    def _build_deterministic_edge_groups(self, intersection_nodes: list[int]) -> list[list[list[int]]]:
        """Crea gruppi di priorità standard deterministici (ogni svolta è indipendente)."""
        nodes_set = set(intersection_nodes)
        groups = []
        for source_node in intersection_nodes:
            outgoing = sorted([v for _, v in self.graph.out_edges(source_node) if v in nodes_set])
            for target_node in outgoing:
                # Ogni singola manovra da sorgente a destinazione fa gruppo a sé
                groups.append([[source_node, target_node]])
        return groups
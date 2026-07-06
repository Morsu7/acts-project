from mesa import Model
from mesa.space import NetworkGrid
from mesa.time import RandomActivation

import networkx as nx

from acts.agents.traffic_light import TrafficLightAgent


class CityModel(Model):
    def __init__(self, graph: nx.DiGraph):
        super().__init__()
        self.G = graph
        self.grid = NetworkGrid(self.G)
        self.schedule = RandomActivation(self)
        self.running = True
        
        self.intersection_meta = self.G.graph.get("intersections", {})
        self.intersection_nodes = {
            intersection_id: list(meta["nodes"])
            for intersection_id, meta in self.intersection_meta.items()
        }
        
        # Fallback se i metadati globali non fossero pronti
        if not self.intersection_nodes:
            for node in self.G.nodes():
                intersection_id = self.G.nodes[node].get("intersection", node)
                self.intersection_nodes.setdefault(intersection_id, []).append(node)

        # Inizializza i semafori basandosi sul grafo fornito
        self._setup_traffic_lights()

    def _setup_traffic_lights(self) -> None:
        for intersection_id, intersection_nodes in self.intersection_nodes.items():
            meta = self.intersection_meta.get(intersection_id, {})
            external_conns = meta.get("external_connections", [])
            
            for node in intersection_nodes:
                priority_edge_groups = meta.get("priority_edge_groups", [])
                structured_edge_groups = []
                
                for group in priority_edge_groups:
                    if not any(edge[0] == node for edge in group):
                        continue
                        
                    destinations = list(set(
                        f"tl_{edge[1]}" for edge in group 
                        if edge[1] != node
                    ))
                    
                    structured_edge_groups.append({
                        "edges": group,
                        "destinations": destinations
                    })
                            
                # Calcolo dei tempi di percorrenza stimati (ETA) versos i vicini esterni
                external_neighbor_travel_times = {}
                for conn in external_conns:
                    if conn["local_port"] == node:
                        neighbor_id = f"tl_{conn['neighbor_port']}"
                        edge_length = conn.get("length", 100)      
                        max_speed = conn.get("max_speed", 13.89)   
                        
                        estimated_time = round(edge_length / max_speed)
                        external_neighbor_travel_times[neighbor_id] = estimated_time

                # Instanziazione Agente Semaforo
                tl = TrafficLightAgent(
                    f"tl_{node}",
                    self,
                    intersection_id,
                    node_id=node,
                    inter_neighbors=len(intersection_nodes) - 1,
                    controlled_directions=structured_edge_groups,
                    outgoing_external_neighbors_travel_times=external_neighbor_travel_times
                )
                self.schedule.add(tl)
                self.grid.place_agent(tl, node)     
                self.G.nodes[node]["traffic_light_id"] = tl.unique_id

                # Associazione dell'ID del gruppo semaforico agli archi del grafo
                for group_idx, group in enumerate(structured_edge_groups):
                    for edge in group["edges"]:
                        if self.G.has_edge(edge[0], edge[1]):
                            self.G[edge[0]][edge[1]]["tl_group_id"] = f"{node}_group{group_idx}"

    def step(self):
        self.schedule.step()
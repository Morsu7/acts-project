from mesa import Model
from mesa.space import NetworkGrid
from mesa.time import RandomActivation
from acts.utils.map.generator import generate_topology
from acts.agents.vehicle import VehicleAgent
from acts.agents.traffic_light import TrafficLightAgent

class CityModel(Model):
    def __init__(self, N=10):
        super().__init__()
        self.num_cars = int(N)
        
        # 1. Grafo
        # Ogni nodo rappresenta un semaforo in un incrocio. Ciascun semaforo contiene un riferimento
        # all'incrocio a cui appartiene.
        # Un arco puo' essere una strada interna all'incrocio (gestita dal semaforo) oppure una esterna
        # ad accesso libero.
        self.G = generate_topology(num_nodes=16)

        #print per debug
        #print(f"{self.G.nodes(data=True)}\n")
        #print(f"{self.G.edges(data=True)}\n")
        
        # 2. Spazio standard Mesa in cui gli agenti sono posizionati sui nodi del grafo
        self.grid = NetworkGrid(self.G)
        self.schedule = RandomActivation(self)
        self.running = True
        
        # Costruzione mappa incrocio -> semafori (nodi)
        nodes = list(self.G.nodes())
        self.intersection_meta = self.G.graph.get("intersections", {})
        self.intersection_nodes = {
            intersection_id: list(meta["nodes"])
            for intersection_id, meta in self.intersection_meta.items()
        }
        if not self.intersection_nodes:
            for node in nodes:
                intersection_id = self.G.nodes[node].get("intersection", node)
                self.intersection_nodes.setdefault(intersection_id, []).append(node)

        #print per debug
        #print(f"{self.intersection_nodes}\n")
        #print(f"{self.intersection_meta}\n")

        # 3. Creazione degli agenti: Semafori
        for intersection_id, intersection_nodes in self.intersection_nodes.items():
            for node in intersection_nodes:
                priority_edge_groups = self.intersection_meta.get(intersection_id, {}).get("priority_edge_groups", [])
                node_groups = [group for group in priority_edge_groups if any(node == edge[0] for edge in group)]
                tl = TrafficLightAgent(
                    f"tl_{node}",                           # unique_id
                    self,                                   # model
                    intersection_id,                        # intersection_id
                    node_id=node,                           # node_id
                    neighbors=len(intersection_nodes)-1,    # neighbors
                    controlled_directions=node_groups       # controlled_directions
                )
                self.schedule.add(tl)
                self.grid.place_agent(tl, node)     # Ogni Agente Semaforo viene posizionato sul nodo corrispondente
                self.G.nodes[node]["traffic_light_id"] = tl.unique_id

                for group_idx, group in enumerate(node_groups):
                    for edge in group:
                        if self.G.has_edge(edge[0], edge[1]):
                            self.G[edge[0]][edge[1]]["tl_group_id"] = f"{node}_group{group_idx}"
                #print(f"Nodes\n {self.G.nodes[node]}")

        # 4. Creazione dei Veicoli: External Agents (The System reacts to them, but they are not part of the system)
        for i in range(self.num_cars):
            a = VehicleAgent(f"car_{i}", self)
            self.schedule.add(a)
            self.grid.place_agent(a, self.random.choice(nodes))

        

    def step(self):
        self.schedule.step()
from mesa import Model
from mesa.space import NetworkGrid
from mesa.time import RandomActivation
from acts.utils.map.generator import generate_topology
from acts.agents.vehicle import VehicleAgent
from acts.agents.traffic_light import TrafficLightAgent

class CityModel(Model):
    def __init__(self, N=10):
        super().__init__()
        self.num_agents = int(N)
        
        # 1. Grafo
        self.G = generate_topology(num_nodes=16)

        #print per debug
        #print(f"{self.G.nodes(data=True)}\n")
        #print(f"{self.G.edges(data=True)}\n")
        
        # 2. Spazio standard Mesa
        self.grid = NetworkGrid(self.G)
        self.schedule = RandomActivation(self)
        self.running = True
        
        # Costruzione mappa incrocio -> nodi
        nodes = list(self.G.nodes())
        self.intersection_meta = self.G.graph.get("intersections", {})
        print(f"Intersection Meta: {self.intersection_meta}\n")
        self.intersection_nodes = {
            intersection_id: list(meta["nodes"])
            for intersection_id, meta in self.intersection_meta.items()
        }
        print(f"Intersection Nodes: {self.intersection_nodes}\n")
        if not self.intersection_nodes:
            for node in nodes:
                intersection_id = self.G.nodes[node].get("intersection", node)
                self.intersection_nodes.setdefault(intersection_id, []).append(node)

        #print per debug
        #print(f"{self.intersection_nodes}\n")
        #print(f"{self.intersection_meta}\n")

        # 3. Agenti
        for intersection_id, controlled_nodes in self.intersection_nodes.items():
            meta = self.intersection_meta.get(intersection_id, {})
            for node in controlled_nodes:
                tl = TrafficLightAgent(
                    node,  # unique_id
                    self,
                    intersection_id,
                    intersection_meta=meta,
                )
                self.schedule.add(tl)
                self.grid.place_agent(tl, controlled_nodes[0])
                self.G.nodes[node]["traffic_light_id"] = tl.unique_id
                #print(f"Nodes\n {self.G.nodes[node]}")

        for i in range(self.num_agents):
            a = VehicleAgent(100+i, self)
            self.schedule.add(a)
            self.grid.place_agent(a, self.random.choice(nodes))

        

    def step(self):
        self.schedule.step()
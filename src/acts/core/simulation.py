from mesa import Model
from mesa.space import NetworkGrid
from mesa.time import RandomActivation
from acts.utils.map_generator import generate_topology
from acts.agents.vehicle import VehicleAgent
from acts.agents.infrastructure import TrafficLightAgent

class CityModel(Model):
    def __init__(self, N=10):
        super().__init__()
        self.num_agents = int(N)
        
        # 1. Grafo
        self.G = generate_topology(num_nodes=16)
        
        # 2. Spazio standard Mesa
        self.grid = NetworkGrid(self.G)
        self.schedule = RandomActivation(self)
        self.running = True

        nodes = list(self.G.nodes())
        self.intersection_nodes = {
            intersection_id: list(meta["nodes"])
            for intersection_id, meta in self.G.graph.get("intersections", {}).items()
        }
        if not self.intersection_nodes:
            for node in nodes:
                intersection_id = self.G.nodes[node].get("intersection", node)
                self.intersection_nodes.setdefault(intersection_id, []).append(node)

        # 3. Agenti
        for intersection_id, controlled_nodes in self.intersection_nodes.items():
            tl = TrafficLightAgent(f"TL_{intersection_id}", self, intersection_id, controlled_nodes)
            self.schedule.add(tl)
            self.grid.place_agent(tl, controlled_nodes[0])
            for node in controlled_nodes:
                self.G.nodes[node]["traffic_light_id"] = tl.unique_id

        for i in range(self.num_agents):
            a = VehicleAgent(100+i, self)
            self.schedule.add(a)
            self.grid.place_agent(a, self.random.choice(nodes))

    def step(self):
        self.schedule.step()
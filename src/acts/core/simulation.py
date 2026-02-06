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
        self.G = generate_topology(num_nodes=15)
        
        # 2. Spazio standard Mesa
        self.grid = NetworkGrid(self.G)
        self.schedule = RandomActivation(self)
        self.running = True

        nodes = list(self.G.nodes())

        # 3. Agenti
        for node in nodes:
            tl = TrafficLightAgent(node, self)
            self.schedule.add(tl)
            self.grid.place_agent(tl, node)

        for i in range(self.num_agents):
            a = VehicleAgent(100+i, self)
            self.schedule.add(a)
            self.grid.place_agent(a, self.random.choice(nodes))

    def step(self):
        self.schedule.step()
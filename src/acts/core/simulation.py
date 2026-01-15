from mesa import Model
from mesa.time import RandomActivation
from mesa.space import NetworkGrid # <--- FONDAMENTALE
from acts.agents.vehicle import VehicleAgent
from acts.utils.map_generator import generate_topology

class CityModel(Model):
    def __init__(self, N=10):
        super().__init__()
        self.num_agents = N
        
        # 1. Genera il Grafo Matematico
        self.G = generate_topology(num_nodes=20)
        
        # 2. Usa NetworkGrid (Gestisce Nodi e Archi)
        self.grid = NetworkGrid(self.G)
        self.schedule = RandomActivation(self)
        self.running = True

        # 3. Piazza le Macchine sui Nodi
        nodes = list(self.G.nodes())
        for i in range(self.num_agents):
            a = VehicleAgent(i, self)
            self.schedule.add(a)
            
            # Scegli un ID nodo a caso
            start_node = self.random.choice(nodes)
            self.grid.place_agent(a, start_node)

    def step(self):
        self.schedule.step()
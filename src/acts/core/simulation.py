from mesa import Model
from mesa.space import NetworkGrid
from mesa.time import RandomActivation
from acts.utils.map_generator import generate_topology
from acts.agents.vehicle import VehicleAgent
from acts.agents.infrastructure import TrafficLightAgent # <--- Importa il nuovo agente

class CityModel(Model):
    def __init__(self, N=5):
        super().__init__()
        self.num_agents = int(N)
        
        self.G = generate_topology(num_nodes=20)
        self.grid = NetworkGrid(self.G)
        self.schedule = RandomActivation(self)
        self.running = True

        nodes = list(self.G.nodes())

        # 1. PIAZZA I SEMAFORI (Uno per ogni nodo)
        for node_id in nodes:
            tl = TrafficLightAgent(node_id, self) # ID del semaforo = ID del nodo
            self.schedule.add(tl)
            # Nota: In NetworkGrid non serve "piazzarli" spazialmente per la logica, 
            # ma lo facciamo per coerenza se volessimo disegnarli.
            self.grid.place_agent(tl, node_id)

        # 2. PIAZZA I VEICOLI
        for i in range(self.num_agents):
            # Usiamo ID univoci che non confliggano con i semafori
            # I nodi sono 0..19. Le auto saranno 100..100+N
            car_id = 100 + i 
            a = VehicleAgent(car_id, self)
            self.schedule.add(a)
            
            start_node = self.random.choice(nodes)
            self.grid.place_agent(a, start_node)

    def step(self):
        self.schedule.step()
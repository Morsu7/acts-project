from acts.utils.map.generator import generate_topology
from acts.map.road_network import RoadNetwork 

from acts.agents.vehicle import VehicleAgent

from acts.city_model.base_model import CityModel

class ProceduralCityModel(CityModel):
    def __init__(self, num_intersections: int = 16, num_cars: int = 10):
        procedural_graph = generate_topology(num_nodes=num_intersections)
        
        super().__init__(graph=procedural_graph)
        
        self.num_cars = int(num_cars)
        nodes = list(self.G.nodes())
        
        for i in range(self.num_cars):
            car = VehicleAgent(f"car_{i}", self)
            self.schedule.add(car)
            self.grid.place_agent(car, self.random.choice(nodes))
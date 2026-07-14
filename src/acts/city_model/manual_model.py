from acts.utils.map.generator import generate_topology
from acts.map.road_network import RoadNetwork 

from acts.agents.vehicle import VehicleAgent
from acts.city_model.base_model import CityModel

class ManualCityModel(CityModel):
    def __init__(self, road_network: RoadNetwork, vehicle_spawns: list[tuple[str, int]]):
        super().__init__(graph=road_network.graph)
        
        for car_id, spawn_node, path in vehicle_spawns:
            if not self.G.has_node(spawn_node):
                raise ValueError(f"Il nodo di spawn {spawn_node} per {car_id} non esiste nel grafo manuale.")
                
            car = VehicleAgent(car_id, self, start_path=path, replan_destination=False)
            self.schedule.add(car)
            self.grid.place_agent(car, spawn_node)
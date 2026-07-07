from mesa import Model
from acts.city_model import ProceduralCityModel, ManualCityModel
import importlib

class UnifiedCityModel(Model):
    def __init__(self, config_type="Procedurale", num_cars=10, num_intersections=16):
        super().__init__()
        
        if config_type == "Procedurale":
            self.underlying_model = ProceduralCityModel(
                num_intersections=num_intersections, 
                num_cars=num_cars
            )
        else:
            filename = config_type.replace("Manuale: ", "")
            
            demo_module = importlib.import_module(f"acts.city_model.demo.{filename}")
            road_network, vehicle_spawns = demo_module.get_config()
            
            self.underlying_model = ManualCityModel(
                road_network=road_network, 
                vehicle_spawns=vehicle_spawns
            )
            
        self.G = self.underlying_model.G
        self.grid = self.underlying_model.grid
        self.schedule = self.underlying_model.schedule
        self.running = self.underlying_model.running

    def step(self):
        self.underlying_model.step()

    def toggle_traffic_light(self, traffic_light_id: str):
        return self.underlying_model.toggle_traffic_light(traffic_light_id)

    def get_traffic_light_overview(self):
        return self.underlying_model.get_traffic_light_overview()

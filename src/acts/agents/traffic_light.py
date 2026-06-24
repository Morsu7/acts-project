from mesa import Agent

from acts.utils.utils_agents import _is_vehicle_agent

class TrafficLightAgent(Agent):

    def __init__(self, unique_id, model, intersection_id, intersection_meta):
        super().__init__(unique_id, model)
        self.intersection_id = intersection_id
        self.intersection_meta = intersection_meta
        self.state = "RED"  # Initial state of the traffic light

    # Public API: called by Mesa scheduler.
    def step(self):
        #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} has meta {self.intersection_meta} and is currently {self.state}\n")
        # Logic for traffic light state changes can be implemented here
        agents = self.model.G.nodes[self.unique_id].get("agent", [])
        cars = [a for a in agents if _is_vehicle_agent(a)]

        queued_cars = [car for car in cars if car.state == "QUEUED"]

        if queued_cars:
            print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} sees {len(queued_cars)} queued cars\n")
        pass
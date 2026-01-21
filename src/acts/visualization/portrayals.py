from acts.agents.vehicle import VehicleAgent
from acts.agents.infrastructure import Road, Obstacle, TrafficLight

def agent_portrayal(agent):
    if agent is None: return
    
    portrayal = {
        "Shape": "rect",
        "Filled": "true",
        "w": 1, "h": 1,
        "Layer": 0
    }

    if isinstance(agent, Road):
        portrayal["Color"] = "#B0B0B0" # Asfalto Grigio
        portrayal["Layer"] = 0
    
    elif isinstance(agent, Obstacle):
        portrayal["Color"] = "#202020" # Edifici Neri
        portrayal["Layer"] = 0

    elif isinstance(agent, TrafficLight):
        portrayal["Color"] = "#00FF00" # Verde Fluo
        portrayal["Layer"] = 0
        portrayal["w"] = 0.8
        portrayal["h"] = 0.8

    elif isinstance(agent, VehicleAgent):
        portrayal["Shape"] = "circle"
        portrayal["Color"] = "#FF0000" # Macchina Rossa
        portrayal["Layer"] = 1 # Sopra la strada
        portrayal["r"] = 0.6

    return portrayal
from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.modules import NetworkModule
from mesa.visualization.UserParam import Slider
from acts.core.simulation import CityModel
from acts.agents.vehicle import VehicleAgent
from acts.agents.infrastructure import TrafficLightAgent

def network_portrayal(G):
    portrayal = dict()
    portrayal['nodes'] = []
    portrayal['edges'] = []

    for source, target in G.edges():
        portrayal['edges'].append({
            'source': source, 'target': target,
            'color': '#000000', 'width': 1,
        })

    for node in G.nodes():
        agents = G.nodes[node].get("agent", [])
        
        tl = next((a for a in agents if isinstance(a, TrafficLightAgent)), None)
        cars = [a for a in agents if isinstance(a, VehicleAgent)]
        
        # Base: Semaforo
        color = "#00FF00" if tl and tl.state == "GREEN" else "#FF0000"
        size = 8
        label = str(node)
        tooltip = f"Nodo {node}<br>Stato: {tl.state if tl else 'None'}"

        # Se ci sono auto
        if cars:
            # Distinguiamo visivamente chi è in coda e chi è in "viaggio" (DRIVING)
            driving_cars = [c for c in cars if c.state == "DRIVING"]
            queued_cars = [c for c in cars if c.state == "QUEUED"]
            
            if driving_cars:
                color = "#FFA500" # Arancione = In transito (sta partendo)
                tooltip += f"<br>🚗 In partenza: {len(driving_cars)}"
            
            if queued_cars:
                color = "#0000FF" # Blu = In coda
                size = 12 + (len(queued_cars) * 2) # Più grosso se c'è coda
                label = f"{node} ({len(queued_cars)})"
                tooltip += f"<br>🚙 In coda: {len(queued_cars)}"

        portrayal['nodes'].append({
            "id": node, "size": size, "color": color, "label": label, "tooltip": tooltip
        })

    return portrayal

network = NetworkModule(network_portrayal, 600, 600)
server = ModularServer(CityModel, [network], "ACTS: Distributed Graphs", {"N": Slider("Auto", 5, 1, 20)})
server.port = 8521
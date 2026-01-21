from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.modules import NetworkModule
from mesa.visualization.UserParam import Slider

from acts.core.simulation import CityModel
from acts.agents.infrastructure import TrafficLightAgent
from acts.agents.vehicle import VehicleAgent

def network_portrayal(G):
    portrayal = dict()
    portrayal['nodes'] = []
    portrayal['edges'] = []

    # Disegna le strade (Archi)
    for source, target in G.edges():
        portrayal['edges'].append({
            'source': source, 
            'target': target,
            'color': '#333333', 
            'width': 2,
        })

    # Disegna i Nodi (Semafori e Auto)
    for node in G.nodes():
        agents = G.nodes[node].get("agent", [])
        
        # 1. Cerchiamo chi c'è nel nodo
        tl_agent = None
        cars = []
        for a in agents:
            if isinstance(a, TrafficLightAgent): 
                tl_agent = a
            if isinstance(a, VehicleAgent): 
                cars.append(a)

        # 2. Colore base: dipende dal SEMAFORO
        color = "#CCCCCC" # Default (Spento/Grigio)
        if tl_agent:
            if tl_agent.state == "GREEN": 
                color = "#00FF00" # Verde
            else: 
                color = "#FF0000" # Rosso

        size = 10
        label = str(node)
        
        # 3. Se ci sono AUTO, sovrascriviamo la visualizzazione
        # Le auto sono blu per vederle bene sopra il rosso/verde
        if len(cars) > 0:
            size = 18
            color = "#0000FF" # Blu Elettrico
            label = f"{node} ({len(cars)})"

        portrayal['nodes'].append({
            "id": node,
            "size": size,
            "color": color,
            "label": label,
        })

    return portrayal

# --- QUESTA È LA PARTE CHE MANCAVA ---

# Configurazione del Network Module
network = NetworkModule(network_portrayal, 600, 600)

model_params = {
    "N": Slider("Numero Veicoli", 5, 1, 15, 1) 
}

# Avvio del Server
server = ModularServer(
    CityModel,
    [network],
    "ACTS: Distributed Traffic System",
    model_params
)

server.port = 8521
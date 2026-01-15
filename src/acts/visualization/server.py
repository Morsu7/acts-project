from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.UserParam import Slider
from mesa.visualization.modules import NetworkModule # <--- Modulo Visuale Grafo

from acts.core.simulation import CityModel

def network_portrayal(G):
    """
    Logica di disegno:
    - Nodi: Cerchi
    - Archi: Linee
    """
    portrayal = dict()
    portrayal['nodes'] = []
    portrayal['edges'] = []

    # Disegna gli Archi (Strade)
    for source, target in G.edges():
        portrayal['edges'].append({
            'source': source,
            'target': target,
            'color': '#000000', # Linee nere
            'width': 1,
        })

    # Disegna i Nodi (Incroci)
    for node in G.nodes():
        # Conta quanti agenti ci sono in questo nodo
        agents = G.nodes[node].get("agent", [])
        
        # Colore di default (Nodo Vuoto)
        color = "#CCCCCC" # Grigio chiaro
        size = 5
        
        # Se c'è una macchina, diventa Rosso e grosso
        if len(agents) > 0:
            color = "#FF0000"
            size = 8

        portrayal['nodes'].append({
            "id": node,
            "size": size,
            "color": color,
        })

    return portrayal

# Configurazione Grafica (Canvas 500x500 pixel)
network = NetworkModule(network_portrayal, 500, 500)

model_params = {
    "N": Slider("Numero Veicoli", 5, 1, 20, 1)
}

server = ModularServer(
    CityModel,
    [network], 
    "ACTS: Network Topology",
    model_params
)

server.port = 8521
from acts.agents.vehicle import VehicleAgent
from acts.agents.infrastructure import Road, Obstacle, TrafficLight

def agent_portrayal(agent):
    """
    Definisce come disegnare ogni agente nel browser.
    """
    if agent is None:
        return

    # --- 1. CONFIGURAZIONE DI DEFAULT (Sicurezza) ---
    # Impostiamo dei valori base così se i controlli sotto falliscono,
    # il server non crasha (vedrai un quadratino rosa di debug).
    portrayal = {
        "Shape": "rect",
        "Filled": "true",
        "Layer": 0,        # FONDAMENTALE: Sfondo (default)
        "w": 1, 
        "h": 1,
        "Color": "pink"    # Colore di debug (se vedi rosa, manca un if sotto)
    }

    # --- 2. LOGICA PER OGNI TIPO DI AGENTE ---

    # A. STRADA (Con Frecce Direzionali)
    if isinstance(agent, Road):
        portrayal["Color"] = "#D3D3D3" # Grigio chiaro
        portrayal["Layer"] = 0
        
        # Aggiungi frecce testuali in base alla direzione
        # (1,0)=Est, (-1,0)=Ovest, (0,1)=Nord, (0,-1)=Sud
        if agent.direction == (1, 0): 
            portrayal["text"] = "→"
        elif agent.direction == (-1, 0): 
            portrayal["text"] = "←"
        elif agent.direction == (0, 1): 
            portrayal["text"] = "↑"
        elif agent.direction == (0, -1): 
            portrayal["text"] = "↓"
            
        portrayal["text_color"] = "black"

    # B. VEICOLO (Pallini Rossi sopra la strada)
    elif isinstance(agent, VehicleAgent):
        portrayal["Shape"] = "circle"
        portrayal["Color"] = "#FF0000" # Rosso acceso
        portrayal["r"] = 0.5
        portrayal["Layer"] = 1  # IMPORTANTE: Layer 1 sta sopra al Layer 0

    # C. SEMAFORO (Verde/Rosso)
    elif isinstance(agent, TrafficLight):
        portrayal["Color"] = "green" if agent.state else "red"
        portrayal["Layer"] = 0
        portrayal["w"] = 0.8 
        portrayal["h"] = 0.8

    # D. PALAZZO (Ostacolo scuro)
    elif isinstance(agent, Obstacle):
        portrayal["Color"] = "#202020" # Quasi nero
        portrayal["Layer"] = 0

    return portrayal
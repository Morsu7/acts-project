from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.UserParam import Slider
from acts.core.simulation import CityModel
from acts.agents.vehicle import VehicleAgent
from acts.visualization.network_module_custom import CustomNetworkModule

from acts.utils.utils_agents import _is_vehicle_agent

def _compute_vehicle_marker(car, current_node, G):
    base = {
        "id": f"car_{car.unique_id}",
        "node": current_node,
        "state": car.state,
    }

    # Estraiamo il nodo successivo se presente nel percorso
    next_node = car.path[1] if (car.path and len(car.path) > 1) else None
    
    # Costruiamo il pezzo di testo del tooltip dedicato alla destinazione successiva
    next_node_text = f"<br>Direzione: verso nodo {next_node}" if next_node else "<br>Direzione: Nessuna (Fine percorso)"
    
    # Tooltip base di default
    base["tooltip"] = f"Auto {car.unique_id}<br>Stato: {car.state}{next_node_text}"

    if not next_node:
        base["mode"] = "node"
        return base

    if not G.has_edge(current_node, next_node):
        base["mode"] = "node"
        return base

    current_intersection = G.nodes[current_node].get("intersection", current_node)
    next_intersection = G.nodes[next_node].get("intersection", next_node)
    external_entry = current_intersection != next_intersection

    if car.state == "DRIVING":
        total = max(getattr(car, "edge_total_timer", 0), 1)
        remaining = max(car.travel_timer, 0)
        progress = 1.0 - (remaining / total)
        progress = min(max(progress, 0.02), 0.92)
        base.update(
            {
                "mode": "edge",
                "from": current_node,
                "to": next_node,
                "progress": progress,
                "laneOffset": 4,
            }
        )
        return base

    if car.state == "QUEUED" and external_entry:
        base["mode"] = "node"
        # Sovrascriviamo il tooltip specifico per la coda mantenendo l'info del prossimo nodo
        base["tooltip"] = f"Auto {car.unique_id}<br>Stato: IN CODA{next_node_text}"
        return base

    base["mode"] = "node"
    return base

def network_portrayal(G):
    portrayal = dict()
    portrayal['nodes'] = []
    portrayal['edges'] = []
    portrayal['vehicles'] = []

    # --- 1. EDGE LOOP (Renders edges AND driving vehicles) ---
    for source, target in G.edges():
        source_intersection = G.nodes[source].get("intersection", source)
        target_intersection = G.nodes[target].get("intersection", target)
        edge_data = G.get_edge_data(source, target) or {}
        internal_edge = source_intersection == target_intersection

        if not internal_edge:
            edge_color = '#000000'
            edge_tooltip = None
            constraint_group = None
        else:
            edge_tl_state = edge_data.get("tl_state", "RED")
            match edge_tl_state:
                case "GREEN":
                    edge_color = '#00B050'
                case "YELLOW":
                    edge_color = '#FFC000'
                case "RED":
                    edge_color = '#D7263D'
            waiting_cars = int(edge_data.get("tl_waiting_cars", 0))
            waiting_seconds = int(edge_data.get("tl_waiting_seconds", 0))
            waiting_cars_score = float(edge_data.get("tl_waiting_cars_score", 0.0))
            waiting_time_score = float(edge_data.get("tl_waiting_time_score", 0.0))
            priority_score = float(edge_data.get("tl_priority_score", 0.0))
            constraint_group = edge_data.get("tl_group_id", None)
            group_priority_score = float(edge_data.get("tl_group_score", 0.0))
            edge_tooltip = (
                f"Arco {source}->{target}"
                f"<br>Constraint group: {constraint_group if constraint_group is not None else '-'}"
                f"<br>Queued cars: {waiting_cars}"
                f"<br>Waiting seconds: {waiting_seconds}"
                f"<br>Priority score: {priority_score:.2f}"
                f"<br>Group summed score: {group_priority_score:.2f}"
                f"<br>Status light: {edge_tl_state}"
            )

        portrayal['edges'].append({
            'source': source, 'target': target,
            'color': edge_color,
            'width': 1.4 if source_intersection == target_intersection else 1,
            'tooltip': edge_tooltip,
            'constraintGroup': constraint_group,
            'hoverable': internal_edge,
        })

        # --- NEW: Catch driving cars floating inside this edge ---
        driving_cars = edge_data.get("vehicles", [])
        for car in driving_cars:
            # When driving, car.pos is a tuple (source, target), but _compute_vehicle_marker 
            # expects the source node ID to determine the base coordinate system.
            portrayal['vehicles'].append(_compute_vehicle_marker(car, source, G))

    # --- 2. NODE LOOP (Renders vertices AND queued vehicles) ---
    for node in G.nodes():
        node_data = G.nodes[node]
        agents = node_data.get("agent", [])
        pos = node_data.get("pos", (0.0, 0.0))
        intersection_id = node_data.get("intersection", node)
        
        cars = [a for a in agents if _is_vehicle_agent(a)]
        
        if node_data.get("is_gate", False):
            color = "#007BFF"  # Blu brillante per i nodi spawn/sink
            size = 12          # Più grande rispetto ai nodi regolari
            tooltip = f"🚪 <b>GATE DI ACCESSO (Nodo {node})</b><br>Punto di ingresso/uscita veicoli"
        else:
            color = "#777777"  # Grigio standard
            size = 6
            tooltip = f"Nodo {node}<br>Incrocio: {intersection_id}<br>Stop line"

        if cars:
            tooltip += f"<br>Auto nel nodo: {len(cars)}"

        for car in cars:
            portrayal['vehicles'].append(_compute_vehicle_marker(car, node, G))

        portrayal['nodes'].append({
            "id": node,
            "size": size,
            "color": color,
            "tooltip": tooltip,
            "intersection": intersection_id,
            "x": float(pos[0]),
            "y": float(pos[1]),
        })

    return portrayal
network = CustomNetworkModule(network_portrayal, 600, 600)
server = ModularServer(CityModel, [network], "ACTS: Distributed Graphs", {"N": Slider("Auto", 5, 1, 20)})
server.port = 8521
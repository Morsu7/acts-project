from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.UserParam import Slider
from acts.core.simulation import CityModel
from acts.agents.vehicle import VehicleAgent
from acts.visualization.network_module_custom import CustomNetworkModule


def _is_vehicle_agent(agent):
    return isinstance(agent, VehicleAgent) or agent.__class__.__name__ == "VehicleAgent"


def _compute_vehicle_marker(car, current_node, G):
    base = {
        "id": f"car_{car.unique_id}",
        "node": current_node,
        "state": car.state,
        "tooltip": f"Auto {car.unique_id}<br>Stato: {car.state}",
    }

    if not car.path or len(car.path) <= 1:
        base["mode"] = "node"
        return base

    next_node = car.path[1]
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
        base["tooltip"] = f"Auto {car.unique_id}<br>Stato: IN CODA"
        return base

    base["mode"] = "node"
    return base

def network_portrayal(G):
    portrayal = dict()
    portrayal['nodes'] = []
    portrayal['edges'] = []
    portrayal['vehicles'] = []

    for source, target in G.edges():
        source_intersection = G.nodes[source].get("intersection", source)
        target_intersection = G.nodes[target].get("intersection", target)
        edge_data = G.get_edge_data(source, target) or {}

        if source_intersection != target_intersection:
            edge_color = '#000000'
        else:
            edge_tl_state = edge_data.get("tl_state", "RED")
            edge_color = '#00B050' if edge_tl_state == "GREEN" else '#D7263D'

        waiting_cars_raw = int(edge_data.get("tl_waiting_cars_raw", 0))
        waiting_seconds_raw = int(edge_data.get("tl_waiting_seconds_raw", 0))
        waiting_cars_score = float(edge_data.get("tl_waiting_cars_score", 0.0))
        waiting_time_score = float(edge_data.get("tl_waiting_time_score", 0.0))
        priority_score = float(edge_data.get("tl_priority_score", 0.0))
        edge_tooltip = (
            f"Arco {source}->{target}"
            f"<br>Raw queued cars: {waiting_cars_raw}"
            f"<br>Raw waiting seconds: {waiting_seconds_raw}"
            f"<br>Score waiting cars: {waiting_cars_score:.2f}"
            f"<br>Score waiting time: {waiting_time_score:.2f}"
            f"<br>Priority score: {priority_score:.2f}"
        )

        portrayal['edges'].append({
            'source': source, 'target': target,
            'color': edge_color,
            'width': 1.4 if source_intersection == target_intersection else 1,
            'tooltip': edge_tooltip,
        })

    for node in G.nodes():
        agents = G.nodes[node].get("agent", [])
        pos = G.nodes[node].get("pos", (0.0, 0.0))
        intersection_id = G.nodes[node].get("intersection", node)
        
        cars = [a for a in agents if _is_vehicle_agent(a)]
        
        color = "#777777"

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
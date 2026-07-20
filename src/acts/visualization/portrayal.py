from acts.visualization.vehicles import compute_vehicle_marker

from acts.utils.utils_agents import _is_vehicle_agent

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
                case 'FLASHING_YELLOW':
                    if edge_data.get("tl_state_time", 0) % 2 == 0:
                        edge_color = '#FFC000'
                    else:
                        edge_color = '#000000'

            waiting_cars = int(edge_data.get("tl_waiting_cars", 0))
            waiting_seconds = int(edge_data.get("tl_waiting_seconds", 0))
            waiting_cars_score = float(edge_data.get("tl_waiting_cars_score", 0.0))
            waiting_time_score = float(edge_data.get("tl_waiting_time_score", 0.0))
            priority_score = float(edge_data.get("tl_priority_score", 0.0))
            last_used_score = float(edge_data.get("tl_last_used_score", 0.0))
            constraint_group = edge_data.get("tl_group_id", None)
            group_priority_score = float(edge_data.get("tl_group_score", 0.0))
            permissions_ids = edge_data.get("tl_permissions_ids", [])
            edge_tooltip = (
                f"Arco {source}->{target}"
                f"<br>Constraint group: {constraint_group if constraint_group is not None else '-'}"
                f"<br>Queued cars: {waiting_cars}"
                f"<br>Waiting seconds: {waiting_seconds}"
                f"<br>Priority score: {priority_score:.2f}"
                f"<br>Last used score: {last_used_score:.2f}"
                f"<br>Group summed score: {group_priority_score:.2f}"
                f"<br>Status light: {edge_tl_state}"
                f"<br>Permissions IDs: {', '.join(permissions_ids) if permissions_ids else '-'}"
            )

        portrayal['edges'].append({
            'source': source, 'target': target,
            'color': edge_color,
            'width': 1.4 if source_intersection == target_intersection else 1,
            'tooltip': edge_tooltip,
            'constraintGroup': constraint_group,
            'hoverable': internal_edge,
        })

        driving_cars = edge_data.get("vehicles", [])
        for car in driving_cars:
            # When driving, car.pos is a tuple (source, target), but _compute_vehicle_marker 
            # expects the source node ID to determine the base coordinate system.
            portrayal['vehicles'].append(compute_vehicle_marker(car, source, G))

    # --- 2. NODE LOOP (Renders vertices AND queued vehicles) ---
    for node in G.nodes():
        node_data = G.nodes[node]
        agents = node_data.get("agent", [])
        pos = node_data.get("pos", (0.0, 0.0))
        intersection_id = node_data.get("intersection", node)
        
        cars = [a for a in agents if _is_vehicle_agent(a)]
        
        if node_data.get("is_gate", False):
            color = "#007BFF"
            size = 12
            tooltip = f"🚪 <b>GATE DI ACCESSO (Nodo {node})</b><br>Punto di ingresso/uscita veicoli"
        else:
            color = "#777777"
            size = 6
            tooltip = f"Nodo {node}<br>Incrocio: {intersection_id}<br>Stop line"

        if cars:
            tooltip += f"<br>Auto nel nodo: {len(cars)}"

        for car in cars:
            portrayal['vehicles'].append(compute_vehicle_marker(car, node, G))

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
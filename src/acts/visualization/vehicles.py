def compute_vehicle_marker(car, current_node, G):
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

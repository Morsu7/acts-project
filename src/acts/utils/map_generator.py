import networkx as nx
import math
import random

def generate_topology(num_nodes=10, max_degree=5, grid_size=15, cell_size=5):
    # 1) Griglia base degli incroci
    cols = math.ceil(math.sqrt(num_nodes))
    rows = math.ceil(num_nodes / cols)
    jitter = 0.03
    road_probability = 0.75
    diagonal_road_probability = 0.45

    base_pos = {}
    base_undirected_edges = []

    for node_id in range(num_nodes):
        row = node_id // cols
        col = node_id % cols

        base_x = col / max(cols - 1, 1)
        base_y = row / max(rows - 1, 1)

        x = min(1.0, max(0.0, base_x + random.uniform(-jitter, jitter)))
        y = min(1.0, max(0.0, base_y + random.uniform(-jitter, jitter)))
        base_pos[node_id] = (x, y)

        right = node_id + 1
        down = node_id + cols
        down_right = node_id + cols + 1
        down_left = node_id + cols - 1

        if col < cols - 1 and right < num_nodes and random.random() < road_probability:
            base_undirected_edges.append((node_id, right))

        if row < rows - 1 and down < num_nodes and random.random() < road_probability:
            base_undirected_edges.append((node_id, down))

        if (
            row < rows - 1
            and col < cols - 1
            and down_right < num_nodes
            and random.random() < diagonal_road_probability
        ):
            base_undirected_edges.append((node_id, down_right))

        if (
            row < rows - 1
            and col > 0
            and down_left < num_nodes
            and random.random() < diagonal_road_probability
        ):
            base_undirected_edges.append((node_id, down_left))

    # 2) Espansione: ogni incrocio diventa un mini-grafo di "porte"
    H = nx.DiGraph()
    neighbors_map = {n: [] for n in range(num_nodes)}
    for u, v in base_undirected_edges:
        neighbors_map[u].append(v)
        neighbors_map[v].append(u)

    port_of = {}
    next_port_id = 0
    port_offset = 0.045

    for center in range(num_nodes):
        cx, cy = base_pos[center]
        local_neighbors = neighbors_map[center]

        for other in local_neighbors:
            ox, oy = base_pos[other]
            dx = ox - cx
            dy = oy - cy
            norm = math.sqrt(dx * dx + dy * dy)
            if norm == 0:
                ux, uy = 0.0, 0.0
            else:
                ux, uy = dx / norm, dy / norm

            px = min(1.0, max(0.0, cx + ux * port_offset))
            py = min(1.0, max(0.0, cy + uy * port_offset))

            port_id = next_port_id
            next_port_id += 1
            H.add_node(
                port_id,
                pos=(px, py),
                intersection=center,
                neighbor_intersection=other,
            )
            port_of[(center, other)] = port_id

    # 3) Collegamenti strada: porta(u->v) <-> porta(v->u)
    def add_bidirectional(u, v):
        p1 = H.nodes[u]["pos"]
        p2 = H.nodes[v]["pos"]
        dist = math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
        H.add_edge(u, v, weight=dist)
        H.add_edge(v, u, weight=dist)

    for u, v in base_undirected_edges:
        puv = port_of[(u, v)]
        pvu = port_of[(v, u)]
        add_bidirectional(puv, pvu)

    # 4) Collegamenti interni all'incrocio (random, senza forzare connettività globale)
    extra_turn_probability = 0.45

    for center in range(num_nodes):
        local_ports = [port_of[(center, other)] for other in neighbors_map[center]]
        if len(local_ports) < 2:
            continue

        # Spina dorsale: ciclo locale per garantire attraversabilità dell'incrocio
        shuffled = local_ports[:]
        random.shuffle(shuffled)
        for i in range(len(shuffled)):
            add_bidirectional(shuffled[i], shuffled[(i + 1) % len(shuffled)])

        # Archi extra random (svolte aggiuntive)
        for i in range(len(local_ports)):
            for j in range(i + 1, len(local_ports)):
                a = local_ports[i]
                b = local_ports[j]
                if not H.has_edge(a, b) and random.random() < extra_turn_probability:
                    add_bidirectional(a, b)

    for node in H.nodes():
        print(f"Nodo {node} posizionato in {H.nodes[node]['pos']}")

    return H
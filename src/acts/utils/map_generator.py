import networkx as nx
import math
import random

def generate_topology(num_nodes=10, max_degree=5, grid_size=15, cell_size=5):
    # 1) Griglia base degli incroci
    cols = math.ceil(math.sqrt(num_nodes))
    rows = math.ceil(num_nodes / cols)
    road_probability = 0.75
    diagonal_road_probability = 0.45

    base_pos = {}
    for node_id in range(num_nodes):
        row = node_id // cols
        col = node_id % cols

        x = col / max(cols - 1, 1)
        y = row / max(rows - 1, 1)
        base_pos[node_id] = (x, y)

    def build_base_edges():
        edges = []
        for node_id in range(num_nodes):
            row = node_id // cols
            col = node_id % cols

            right = node_id + 1
            down = node_id + cols
            down_right = node_id + cols + 1
            down_left = node_id + cols - 1

            if col < cols - 1 and right < num_nodes and random.random() < road_probability:
                edges.append((node_id, right))

            if row < rows - 1 and down < num_nodes and random.random() < road_probability:
                edges.append((node_id, down))

            if (
                row < rows - 1
                and col < cols - 1
                and down_right < num_nodes
                and random.random() < diagonal_road_probability
            ):
                edges.append((node_id, down_right))

            if (
                row < rows - 1
                and col > 0
                and down_left < num_nodes
                and random.random() < diagonal_road_probability
            ):
                edges.append((node_id, down_left))
        return edges

    base_undirected_edges = []
    max_attempts = 50
    for _ in range(max_attempts):
        candidate_edges = build_base_edges()
        base_graph = nx.Graph()
        base_graph.add_nodes_from(range(num_nodes))
        base_graph.add_edges_from(candidate_edges)
        if num_nodes <= 1 or nx.is_connected(base_graph):
            base_undirected_edges = candidate_edges
            break
    else:
        base_undirected_edges = candidate_edges

    # 2) Espansione: ogni incrocio diventa un mini-grafo di "porte"
    H = nx.DiGraph()
    neighbors_map = {n: [] for n in range(num_nodes)}
    for u, v in base_undirected_edges:
        neighbors_map[u].append(v)
        neighbors_map[v].append(u)

    port_of = {}
    next_port_id = 0
    port_offset = 0.09

    for center in range(num_nodes):
        cx, cy = base_pos[center]
        local_neighbors = neighbors_map[center]
        
        # For intersections with ≤2 neighbors, create a single pass-through node
        if len(local_neighbors) <= 2:
            node_id = next_port_id
            next_port_id += 1
            H.add_node(
                node_id,
                pos=(cx, cy),
                intersection=center,
                is_pass_through=True,
            )
            # Store a special marker for this intersection
            port_of[(center, -1)] = node_id
            continue

        # For intersections with > 2 neighbors, create ports
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

    bidirectional_probability = 0.45

    # 3) Collegamenti strada (random mono/bidirezionali)
    def add_directed(u, v):
        p1 = H.nodes[u]["pos"]
        p2 = H.nodes[v]["pos"]
        dist = math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
        if not H.has_edge(u, v):
            H.add_edge(u, v, weight=dist)

    def add_random_connection(u, v):
        if random.random() < bidirectional_probability:
            add_directed(u, v)
            add_directed(v, u)
        elif random.random() < 0.5:
            add_directed(u, v)
        else:
            add_directed(v, u)

    for u, v in base_undirected_edges:
        # Handle connections based on whether endpoints are exploded or pass-through
        u_is_pass_through = (u, -1) in port_of
        v_is_pass_through = (v, -1) in port_of
        
        if u_is_pass_through and v_is_pass_through:
            # Both are pass-through nodes - connect them directly
            pu = port_of[(u, -1)]
            pv = port_of[(v, -1)]
            add_random_connection(pu, pv)
        elif u_is_pass_through:
            # u is pass-through, v is exploded
            if (v, u) in port_of:
                pu = port_of[(u, -1)]
                pvu = port_of[(v, u)]
                add_random_connection(pu, pvu)
        elif v_is_pass_through:
            # v is pass-through, u is exploded
            if (u, v) in port_of:
                puv = port_of[(u, v)]
                pv = port_of[(v, -1)]
                add_random_connection(puv, pv)
        else:
            # Both are exploded intersections
            if (u, v) in port_of and (v, u) in port_of:
                puv = port_of[(u, v)]
                pvu = port_of[(v, u)]
                add_random_connection(puv, pvu)

    # 4) Collegamenti interni all'incrocio (random, senza forzare connettività globale)
    extra_turn_probability = 0.45

    for center in range(num_nodes):
        local_neighbors = neighbors_map[center]
        
        # Skip pass-through intersections (no internal connections needed)
        if len(local_neighbors) <= 2:
            continue
            
        local_ports = [port_of[(center, other)] for other in local_neighbors]
        if len(local_ports) < 2:
            continue

        # Spina dorsale: ciclo locale per garantire attraversabilità dell'incrocio
        shuffled = local_ports[:]
        random.shuffle(shuffled)
        for i in range(len(shuffled)):
            add_random_connection(shuffled[i], shuffled[(i + 1) % len(shuffled)])

        # Archi extra random (svolte aggiuntive)
        for i in range(len(local_ports)):
            for j in range(i + 1, len(local_ports)):
                a = local_ports[i]
                b = local_ports[j]
                if not H.has_edge(a, b) and not H.has_edge(b, a) and random.random() < extra_turn_probability:
                    add_random_connection(a, b)

    # 5) Garanzia di connettività forte del grafo diretto
    def enforce_strong_connectivity():
        if H.number_of_nodes() <= 1:
            return

        max_rounds = H.number_of_nodes() * 2
        for _ in range(max_rounds):
            if nx.is_strongly_connected(H):
                return

            sccs = list(nx.strongly_connected_components(H))
            condensation = nx.condensation(H, sccs)
            source_components = [c for c in condensation.nodes() if condensation.in_degree(c) == 0]
            sink_components = [c for c in condensation.nodes() if condensation.out_degree(c) == 0]

            if not source_components or not sink_components:
                break

            links_to_add = max(len(source_components), len(sink_components))
            for i in range(links_to_add):
                sink_comp = sink_components[i % len(sink_components)]
                source_comp = source_components[(i + 1) % len(source_components)]

                sink_member = next(iter(condensation.nodes[sink_comp]["members"]))
                source_member = next(iter(condensation.nodes[source_comp]["members"]))
                add_directed(sink_member, source_member)

        if not nx.is_strongly_connected(H):
            fallback_nodes = list(H.nodes())
            for i in range(len(fallback_nodes)):
                add_directed(fallback_nodes[i], fallback_nodes[(i + 1) % len(fallback_nodes)])

    enforce_strong_connectivity()

    return H
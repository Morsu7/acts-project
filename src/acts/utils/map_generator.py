import networkx as nx
import random
import math

def generate_topology(num_nodes=16):
    """
    Genera una 'Griglia Perturbata'.
    Simula una città a blocchi (tipo Manhattan o Barcellona) ma leggermente irregolare.
    Garantisce molteplici percorsi tra i nodi e grado massimo 4.
    """
    # 1. Calcoliamo le dimensioni della griglia (lato x lato)
    side = int(math.sqrt(num_nodes))
    if side * side < num_nodes:
        side += 1
        
    G = nx.Graph()
    
    # Dizionario temporaneo per mappare (row, col) -> node_id
    grid_map = {}
    node_counter = 0

    # 2. Creiamo i nodi su una griglia, ma con "Jitter" (spostamento casuale)
    # per renderla organica e non artificiale.
    for r in range(side):
        for c in range(side):
            if node_counter >= num_nodes: break
            
            # Posizione base (griglia 0..side)
            # Aggiungiamo un rumore casuale (-0.25 a +0.25)
            # Cosi le strade non sono perfettamente dritte
            jitter_x = random.uniform(-0.25, 0.25)
            jitter_y = random.uniform(-0.25, 0.25)
            
            pos = (c + jitter_x, r + jitter_y)
            
            G.add_node(node_counter, pos=pos)
            grid_map[(r, c)] = node_counter
            node_counter += 1

    # 3. Collega i vicini (Manhattan logic)
    # Questo garantisce MAX 4 connessioni per nodo (Nord, Sud, Est, Ovest)
    for r in range(side):
        for c in range(side):
            if (r, c) not in grid_map: continue
            current_id = grid_map[(r, c)]
            
            # Connetti a destra (Est)
            if (r, c+1) in grid_map:
                neighbor_id = grid_map[(r, c+1)]
                # Probabilità del 10% di SALTARE una connessione (crea vicoli ciechi o parchi)
                if random.random() > 0.1: 
                    add_weighted_edge(G, current_id, neighbor_id)

            # Connetti in basso (Sud)
            if (r+1, c) in grid_map:
                neighbor_id = grid_map[(r+1, c)]
                if random.random() > 0.1:
                    add_weighted_edge(G, current_id, neighbor_id)

    # 4. Assicurati che sia connesso
    if not nx.is_connected(G):
        largest_cc = max(nx.connected_components(G), key=len)
        G = G.subgraph(largest_cc).copy()
        mapping = {node: i for i, node in enumerate(G.nodes())}
        G = nx.relabel_nodes(G, mapping)

    return G

def add_weighted_edge(G, u, v):
    """Calcola la distanza fisica e aggiunge l'arco pesato"""
    pos_u = G.nodes[u]['pos']
    pos_v = G.nodes[v]['pos']
    dist = math.sqrt((pos_u[0] - pos_v[0])**2 + (pos_u[1] - pos_v[1])**2)
    G.add_edge(u, v, weight=dist)
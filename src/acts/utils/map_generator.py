import networkx as nx
import random
import math

def generate_topology(num_nodes=15):
    """
    Genera un grafo connesso semplice.
    """
    # Usiamo un grafo geometrico per avere distanze sensate
    G = nx.random_geometric_graph(num_nodes, radius=0.4)
    
    # Rinomina nodi da 0 a N
    mapping = {node: i for i, node in enumerate(G.nodes())}
    G = nx.relabel_nodes(G, mapping)
    
    # Connettività garantita
    if not nx.is_connected(G):
        largest_cc = max(nx.connected_components(G), key=len)
        G = G.subgraph(largest_cc).copy()
        mapping = {node: i for i, node in enumerate(G.nodes())}
        G = nx.relabel_nodes(G, mapping)

    # Calcolo pesi (Distanza Euclidea) per simulare il tempo di viaggio
    for u, v in G.edges():
        p1 = G.nodes[u]['pos']
        p2 = G.nodes[v]['pos']
        dist = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
        # Salviamo il peso (distanza) sull'arco
        G[u][v]['weight'] = dist

    return G
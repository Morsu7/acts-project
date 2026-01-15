import networkx as nx

def generate_topology(num_nodes=20):
    """
    Genera un grafo casuale geometrico (Random Geometric Graph).
    È il modello standard per simulare reti di sensori o città connesse.
    """
    # Radius 0.3 determina quanto devono essere vicini i nodi per connettersi
    G = nx.random_geometric_graph(num_nodes, 0.3)
    
    # Rinomina i nodi in interi sequenziali (0, 1, 2...) per evitare problemi con Mesa
    mapping = {node: i for i, node in enumerate(G.nodes())}
    G = nx.relabel_nodes(G, mapping)

    # Assicuriamoci che sia connesso (niente isole)
    if not nx.is_connected(G):
        largest_cc = max(nx.connected_components(G), key=len)
        G = G.subgraph(largest_cc).copy()
        
        # Rinomina di nuovo per sicurezza dopo il taglio
        mapping = {node: i for i, node in enumerate(G.nodes())}
        G = nx.relabel_nodes(G, mapping)

    return G
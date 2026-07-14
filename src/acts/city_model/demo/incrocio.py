from acts.map.road_network import RoadNetwork

def get_config():
    """
    Scenario deterministico: Incrocio a 4 vie simmetrico.
    - Assi paralleli sincronizzati sulla stessa fase.
    - Ogni semaforo ha un unico gruppo (dir0) che si dirama verso tutti gli altri.
    - Ogni semaforo ha collegato un nodo esterno da cui arrivano i veicoli.
    """
    net = RoadNetwork()
    
    # 1. Definizione del centro dell'incrocio (ID: 0)
    net.set_intersection_center(0, (0.0, 0.0))
    
    # 2. Posizionamento dei 4 nodi esterni (porte d'accesso)
    net.add_port(port_id=10, intersection_id=0, pos=(0.0, 15.0))   # NORD
    net.add_port(port_id=20, intersection_id=0, pos=(15.0, 0.0))   # EST
    net.add_port(port_id=30, intersection_id=0, pos=(0.0, -15.0))  # SUD
    net.add_port(port_id=40, intersection_id=0, pos=(-15.0, 0.0))  # OVEST

    # 3. Posizionamento dei 4 nodi esterni
    north_node_distance = 50.0
    east_node_distance = 60.0
    south_node_distance = 25.0
    west_node_distance = 15.0

    net.add_port(port_id=100, intersection_id=1, pos=(0.0, 15.0+north_node_distance))   # NORD
    net.add_port(port_id=200, intersection_id=2, pos=(15.0+east_node_distance, 0.0))   # EST
    net.add_port(port_id=300, intersection_id=3, pos=(0.0, -15.0-south_node_distance))  # SUD
    net.add_port(port_id=400, intersection_id=4, pos=(-15.0-west_node_distance, 0.0))  # OVEST

    # 4. Collego i nodi esterni all'incrocio
    net.add_road_edge(100, 10, tier="local")  # NORD
    net.add_road_edge(200, 20, tier="local")  # EST
    net.add_road_edge(300, 30, tier="local")  # SUD
    net.add_road_edge(400, 40, tier="local")  # OVEST

    # 5. Creazione delle corsie interne (Ogni semaforo va verso tutti gli altri 3)
    # Da NORD (10) verso gli altri
    net.add_turn_edge(10, 20, edge_kind="turn")
    net.add_turn_edge(10, 30, edge_kind="turn")
    net.add_turn_edge(10, 40, edge_kind="turn")

    # Da EST (20) verso gli altri
    net.add_turn_edge(20, 10, edge_kind="turn")
    net.add_turn_edge(20, 30, edge_kind="turn")
    net.add_turn_edge(20, 40, edge_kind="turn")

    # Da SUD (30) verso gli altri
    net.add_turn_edge(30, 10, edge_kind="turn")
    net.add_turn_edge(30, 20, edge_kind="turn")
    net.add_turn_edge(30, 40, edge_kind="turn")

    # Da OVEST (40) verso gli altri
    net.add_turn_edge(40, 10, edge_kind="turn")
    net.add_turn_edge(40, 20, edge_kind="turn")
    net.add_turn_edge(40, 30, edge_kind="turn")

    # 6. Configurazione dei gruppi di priorità
    # Creiamo un gruppo isolato per ogni semaforo, contenente tutte le sue uscite.
    # In questo modo il ciclo estrarrà esattamente un solo "dir0" per ogni agente semaforo.    
    priority_nord  = [[10, 20], [10, 30], [10, 40]]
    priority_est   = [[20, 10], [20, 30], [20, 40]]
    priority_sud   = [[30, 10], [30, 20], [30, 40]]
    priority_ovest = [[40, 10], [40, 20], [40, 30]]
    
    net.set_intersection_priority_groups(0, [
        priority_nord, 
        priority_est, 
        priority_sud, 
        priority_ovest
    ])

    # 7. Configurazione delle Fasi (Semafori paralleli = Stessa fase)
    # Asse Verticale (Nord / Sud) -> Fase 1
    # Asse Orizzontale (Est / Ovest) -> Fase 2
    net.set_intersection_phases(0, {
        "tl_10_dir0": 1,  # Nord
        "tl_30_dir0": 1,  # Sud
        "tl_20_dir0": 2,  # Est
        "tl_40_dir0": 2   # Ovest
    })
    
    # Compilazione dei metadati strutturali del grafo
    net.compile_metadata()
    
    # 8. Piano di spawn bilanciato (un veicolo pronto per ogni sorgente)
    vehicle_spawns = [
        ("car_nord",  100, [10,20]),
        ("car_est", 200, [20,30]),
        ("car_sud", 300, [30,40]),
        ("car_ovest", 400, [40,10])
    ]
    
    return net, vehicle_spawns
from acts.map.road_network import RoadNetwork

def get_config():
    """
    Scenario deterministico: Incrocio a 4 vie simmetrico.
    - Assi paralleli sincronizzati sulla stessa fase.
    - Ogni semaforo ha un unico gruppo (dir0) che si dirama verso tutti gli altri.
    """
    net = RoadNetwork()
    
    # 1. Definizione del centro dell'incrocio (ID: 0)
    net.set_intersection_center(0, (0.0, 0.0))
    
    # 2. Posizionamento dei 4 nodi esterni (porte d'accesso)
    net.add_port(port_id=10, intersection_id=0, pos=(0.0, 1.0))   # NORD
    net.add_port(port_id=20, intersection_id=0, pos=(1.0, 0.0))   # EST
    net.add_port(port_id=30, intersection_id=0, pos=(0.0, -1.0))  # SUD
    net.add_port(port_id=40, intersection_id=0, pos=(-1.0, 0.0))  # OVEST

    # 3. Creazione delle corsie interne (Ogni semaforo va verso tutti gli altri 3)
    # Da NORD (10) verso gli altri
    net.add_turn_edge(10, 20, edge_kind="turn", length=20.0)
    net.add_turn_edge(10, 30, edge_kind="turn", length=20.0)
    net.add_turn_edge(10, 40, edge_kind="turn", length=20.0)

    # Da EST (20) verso gli altri
    net.add_turn_edge(20, 10, edge_kind="turn", length=20.0)
    net.add_turn_edge(20, 30, edge_kind="turn", length=20.0)
    net.add_turn_edge(20, 40, edge_kind="turn", length=20.0)

    # Da SUD (30) verso gli altri
    net.add_turn_edge(30, 10, edge_kind="turn", length=20.0)
    net.add_turn_edge(30, 20, edge_kind="turn", length=20.0)
    net.add_turn_edge(30, 40, edge_kind="turn", length=20.0)

    # Da OVEST (40) verso gli altri
    net.add_turn_edge(40, 10, edge_kind="turn", length=20.0)
    net.add_turn_edge(40, 20, edge_kind="turn", length=20.0)
    net.add_turn_edge(40, 30, edge_kind="turn", length=20.0)

    # 4. Configurazione dei gruppi di priorità
    # Creiamo un gruppo isolato per ogni semaforo, contenente tutte le sue uscite.
    # In questo modo il ciclo estrarrà esattamente un solo "dir0" per ogni agente semaforo.    priority_nord  = [[10, 20], [10, 30], [10, 40]]
    priority_est   = [[20, 10], [20, 30], [20, 40]]
    priority_sud   = [[30, 10], [30, 20], [30, 40]]
    priority_ovest = [[40, 10], [40, 20], [40, 30]]
    
    net.set_intersection_priority_groups(0, [
        priority_nord, 
        priority_est, 
        priority_sud, 
        priority_ovest
    ])

    # 5. Configurazione delle Fasi (Semafori paralleli = Stessa fase)
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
    
    # 6. Piano di spawn bilanciato (un veicolo pronto per ogni sorgente)
    vehicle_spawns = [
        ("car_nord", 10),
        ("car_est", 20),
        ("car_sud", 30),
        ("car_ovest", 40)
    ]
    
    return net, vehicle_spawns
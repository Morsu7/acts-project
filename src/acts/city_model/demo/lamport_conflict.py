from acts.map.road_network import RoadNetwork
from acts.map.road_network import Direction, DirectionGroup

def get_config():
    """
    Scenario Lamport Conflict:
    Dimostra la risoluzione deterministica di un conflitto simultaneo.
    Due veicoli arrivano all'incrocio nello stesso istante esatto da due 
    strade perpendicolari (Nord ed Est). I semafori calcolano lo stesso
    punteggio e generano richieste con lo stesso Lamport Clock.
    Il protocollo risolve il pareggio usando il confronto alfabetico degli ID.
    """
    net = RoadNetwork()

    # -------------------------------------------------
    # Centro dell'incrocio
    # -------------------------------------------------
    net.set_intersection_center(0, (0.0, 0.0))

    # Porte locali dell'incrocio (perfettamente equidistanti, raggio = 15m)
    net.add_port(10, 0, (0, 15))     # NORD
    net.add_port(20, 0, (15, 0))     # EST
    net.add_port(30, 0, (0, -15))    # SUD
    net.add_port(40, 0, (-15, 0))    # OVEST

    # -------------------------------------------------
    # Nodi Esterni (Spawn e Destinazioni)
    # Perfettamente simmetrici per garantire la simultaneità (raggio = 65m)
    # -------------------------------------------------
    net.add_port(100, 1, (0, 65))    # Origine NORD
    net.add_port(200, 2, (65, 0))    # Origine EST
    
    net.add_port(300, 3, (0, -65))   # Destinazione SUD
    net.add_port(400, 4, (-65, 0))   # Destinazione OVEST

    # -------------------------------------------------
    # Collegamenti
    # -------------------------------------------------
    # Ingressi (lunghezza fisica uguale)
    net.add_road_edge(100, 10, tier="local")
    net.add_road_edge(200, 20, tier="local")

    # Attraversamenti
    net.add_turn_edge(10, 30, "turn") # Nord -> Sud
    net.add_turn_edge(20, 40, "turn") # Est -> Ovest

    # Uscite
    net.add_road_edge(30, 300, tier="local")
    net.add_road_edge(40, 400, tier="local")

    # -------------------------------------------------
    # Fasi Semaforiche (In Conflitto)
    # -------------------------------------------------
    net.set_intersection_priority_groups(0, [
        DirectionGroup(directions=[Direction(10, 30)], phase_index=1),  # Semaforo asse Nord
        DirectionGroup(directions=[Direction(20, 40)], phase_index=2)   # Semaforo asse Est
    ])

    net.compile_metadata()

    # -------------------------------------------------
    # Generazione Veicoli
    # -------------------------------------------------
    # Vengono spawnati insieme al primo tick. Avendo la stessa strada da 
    # percorrere, forzeranno i due agenti semaforici a generare richieste 
    # di verde completamente identiche (Stesso Score, Stesso Clock).
    vehicle_spawns = [
        ("conflict_car_north", 100, [100, 10, 30, 300]),
        ("conflict_car_east",  200, [200, 20, 40, 400])
    ]

    return net, vehicle_spawns
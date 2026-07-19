from acts.map.road_network import RoadNetwork
from acts.map.road_network import Direction, DirectionGroup

def get_config():
    net = RoadNetwork()

    # -------------------------------------------------
    # Centri degli incroci
    # -------------------------------------------------
    net.set_intersection_center(0, (0.0, 0.0))
    net.add_port(10, 0, (0, 15))     # NORD
    net.add_port(20, 0, (15, 0))     # EST 
    net.add_port(30, 0, (0, -15))    # SUD
    net.add_port(40, 0, (-15, 0))    # OVEST 

    net.set_intersection_center(1, (60.0, 0.0))
    net.add_port(110, 1, (60, 15))   
    net.add_port(120, 1, (75, 0))    
    net.add_port(130, 1, (60, -15))  
    net.add_port(140, 1, (45, 0))    

    net.set_intersection_center(2, (120.0, 0.0))
    net.add_port(210, 2, (120, 15))  
    net.add_port(220, 2, (135, 0))   
    net.add_port(230, 2, (120, -15)) 
    net.add_port(240, 2, (105, 0))   


    # -------------------------------------------------
    # Nodi Esterni 
    # -------------------------------------------------
    # Arteria Ovest-Est: Avviciniamo lo spawn per fargli vincere la priorità temporale
    net.add_port(900, 90, (-35.0, 0.0))  # Start Ovest (più vicino)
    net.add_port(901, 91, (165.0, 0.0))  # End Est

    # Traffico laterale (Sud -> Nord, come nell'immagine)
    # Li allontaniamo molto in basso (Y = -80) per ritardare il loro arrivo
    net.add_port(930, 92, (0, -80))      # Start S0
    net.add_port(910, 93, (0, 45))       # End N0
    
    net.add_port(931, 94, (60, -80))     # Start S1
    net.add_port(911, 95, (60, 45))      # End N1
    
    net.add_port(932, 96, (120, -80))    # Start S2
    net.add_port(912, 97, (120, 45))     # End N2


    # -------------------------------------------------
    # Collegamenti
    # -------------------------------------------------
    # Arteria Orizzontale
    net.add_road_edge(900, 40, tier="local")        
    net.add_turn_edge(40, 20, "turn")               
    net.add_road_edge(20, 140, tier="local")        
    net.add_turn_edge(140, 120, "turn")             
    net.add_road_edge(120, 240, tier="local")       
    net.add_turn_edge(240, 220, "turn")             
    net.add_road_edge(220, 901, tier="local")       

    # Attraversamenti Sud -> Nord
    net.add_road_edge(930, 30, tier="local")
    net.add_turn_edge(30, 10, "turn")
    net.add_road_edge(10, 910, tier="local")
    
    net.add_road_edge(931, 130, tier="local")
    net.add_turn_edge(130, 110, "turn")
    net.add_road_edge(110, 911, tier="local")
    
    net.add_road_edge(932, 230, tier="local")
    net.add_turn_edge(230, 210, "turn")
    net.add_road_edge(210, 912, tier="local")


    # -------------------------------------------------
    # Fasi semaforiche (Aggiornate per Sud->Nord)
    # -------------------------------------------------
    net.set_intersection_priority_groups(0, [
        DirectionGroup(directions=[Direction(40, 20)], phase_index=1),
        DirectionGroup(directions=[Direction(30, 10)], phase_index=2)
    ])
    
    net.set_intersection_priority_groups(1, [
        DirectionGroup(directions=[Direction(140, 120)], phase_index=1),
        DirectionGroup(directions=[Direction(130, 110)], phase_index=2)
    ])
    
    net.set_intersection_priority_groups(2, [
        DirectionGroup(directions=[Direction(240, 220)], phase_index=1),
        DirectionGroup(directions=[Direction(230, 210)], phase_index=2)
    ])

    net.compile_metadata()


    # -------------------------------------------------
    # Generazione Veicoli
    # -------------------------------------------------
    vehicle_spawns = []

    # Plotone principale bello denso (15 veicoli)
    arterial_path = [900, 40, 20, 140, 120, 240, 220, 901]
    for i in range(15):
        vehicle_spawns.append((f"wave_car_{i}", 900, arterial_path[:]))

    # Traffico di disturbo Sud->Nord (meno auto per non creare congestioni infinite)
    cross_path_0 = [930, 30, 10, 910]
    cross_path_1 = [931, 130, 110, 911]
    cross_path_2 = [932, 230, 210, 912]

    for i in range(3):
        vehicle_spawns.append((f"cross_I0_{i}", 930, cross_path_0[:]))
        vehicle_spawns.append((f"cross_I1_{i}", 931, cross_path_1[:]))
        vehicle_spawns.append((f"cross_I2_{i}", 932, cross_path_2[:]))

    return net, vehicle_spawns
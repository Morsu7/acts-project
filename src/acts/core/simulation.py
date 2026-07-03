from mesa import Model
from mesa.space import NetworkGrid
from mesa.time import RandomActivation
from acts.utils.map.generator import generate_topology
from acts.agents.vehicle import VehicleAgent
from acts.agents.traffic_light import TrafficLightAgent

class CityModel(Model):
    def __init__(self, N=10):
        super().__init__()
        self.num_cars = int(N)
        
        # 1. Grafo
        # Ogni nodo rappresenta un semaforo in un incrocio. Ciascun semaforo contiene un riferimento
        # all'incrocio a cui appartiene.
        # Un arco puo' essere una strada interna all'incrocio (gestita dal semaforo) oppure una esterna
        # ad accesso libero.
        self.G = generate_topology(num_nodes=16)

        #print per debug
        #print(f"{self.G.nodes(data=True)}\n")
        #print(f"{self.G.edges(data=True)}\n")
        
        # 2. Spazio standard Mesa in cui gli agenti sono posizionati sui nodi del grafo
        self.grid = NetworkGrid(self.G)
        self.schedule = RandomActivation(self)
        self.running = True
        
        # Costruzione mappa incrocio -> semafori (nodi)
        nodes = list(self.G.nodes())
        self.intersection_meta = self.G.graph.get("intersections", {})
        self.intersection_nodes = {
            intersection_id: list(meta["nodes"])
            for intersection_id, meta in self.intersection_meta.items()
        }
        if not self.intersection_nodes:
            for node in nodes:
                intersection_id = self.G.nodes[node].get("intersection", node)
                self.intersection_nodes.setdefault(intersection_id, []).append(node)

        #print per debug
        #print(f"{self.intersection_nodes}\n")
        #print(f"{self.intersection_meta}\n")

        # 3. Creazione degli agenti: Semafori
        for intersection_id, intersection_nodes in self.intersection_nodes.items():
            # Recuperiamo i metadati di questa intersezione configurati dal TopologyBuilder
            meta = self.intersection_meta.get(intersection_id, {})
            external_conns = meta.get("external_connections", [])
            
            for node in intersection_nodes:
                priority_edge_groups = meta.get("priority_edge_groups", [])
                structured_edge_groups = []
                
                for group in priority_edge_groups:
                    # 1. ONLY process this group if it belongs to the current traffic light node
                    # (Checking if the source node 'edge[0]' matches our current 'node')
                    if not any(edge[0] == node for edge in group):
                        continue
                        
                    # 2. Gather unique target nodes, but strip out self-referencing links 
                    # to ensure a traffic light never sends messages to itself
                    destinations = list(set(
                        f"tl_{edge[1]}" for edge in group 
                        if edge[1] != node
                    ))
                    
                    structured_edge_groups.append({
                        "edges": group,
                        "destinations": destinations
                    })
                            
                # --- RECUPERO VICINI ESTERNI E TEMPI DI PERCORRENZA DAI METADATI ---
                external_neighbor_travel_times = {}
                for conn in external_conns:
                    if conn["local_port"] == node:
                        neighbor_id = f"tl_{conn['neighbor_port']}"
                        
                        # Calculate ETA based on edge attributes provided by your topology/graph
                        # Fallback to safety defaults if attributes are missing
                        edge_length = conn.get("length", 100)      # in meters
                        max_speed = conn.get("max_speed", 13.89)   # in m/tick
                        
                        # travel_time in seconds (or ticks, depending on your model scale)
                        estimated_time = round(edge_length / max_speed)
                        
                        # Store it in the dictionary
                        external_neighbor_travel_times[neighbor_id] = estimated_time
                # ---------------------------------------------

                tl = TrafficLightAgent(
                    f"tl_{node}",                                                                   # unique_id of the agent used in communication
                    self,                                                                           # model used for redis communication and mesa scheduling
                    intersection_id,                                                                # intersection_id used for redis communication
                    node_id=node,                                                                   # node_id used for mesa interaction 
                    inter_neighbors=len(intersection_nodes)-1,                                       
                    controlled_directions=structured_edge_groups,                                   
                    outgoing_external_neighbors_travel_times=external_neighbor_travel_times         
                )
                self.schedule.add(tl)
                self.grid.place_agent(tl, node)     
                self.G.nodes[node]["traffic_light_id"] = tl.unique_id

                for group_idx, group in enumerate(structured_edge_groups):
                    for edge in group["edges"]:
                        if self.G.has_edge(edge[0], edge[1]):
                            self.G[edge[0]][edge[1]]["tl_group_id"] = f"{node}_group{group_idx}"

        # 4. Creazione dei Veicoli: External Agents (The System reacts to them, but they are not part of the system)
        for i in range(self.num_cars):
            a = VehicleAgent(f"car_{i}", self)
            self.schedule.add(a)
            self.grid.place_agent(a, self.random.choice(nodes))

        

    def step(self):
        self.schedule.step()
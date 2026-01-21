import networkx as nx
import redis
import json
from mesa import Agent

class VehicleAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.path = [] 
        self.destination = None
        self.state = "MOVING" 
        self.wait_timer = 0
        
        # --- LOGICAL CLOCK (Algoritmo di Lamport) ---
        # Requisito fondamentale dei Sistemi Distribuiti.
        # Non usiamo l'orologio di sistema, ma un contatore di eventi.
        self.lamport_clock = 0 
        
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
            self.redis_client.ping()
        except redis.ConnectionError:
            self.redis_client = None

    def step(self):
        # Ogni step della simulazione è un "evento interno"
        self.tick_clock()
        
        if self.state == "MOVING":
            self.move_logic()
        elif self.state == "WAITING":
            self.wait_logic()

    def tick_clock(self):
        """Avanza il tempo logico interno"""
        self.lamport_clock += 1

    def move_logic(self):
        if not self.path:
            self.select_new_destination()
            return 

        if len(self.path) <= 1:
            self.publish_event("ARRIVED", {"node": self.pos})
            print(f"[{self.lamport_clock}] 🚗 Auto {self.unique_id}: ARRIVATA.")
            self.state = "WAITING"
            self.wait_timer = 10 
            self.path = [] 
            return

        next_node = self.path[1]
        
        # --- LOGICA DISTRIBUITA (SITUATEDNESS) ---
        # L'auto controlla lo stato del semaforo del nodo successivo su Redis.
        # Non chiede a Mesa, chiede al Middleware!
        can_enter = True
        if self.redis_client:
            try:
                # Leggiamo la chiave "tl_<next_node>"
                tl_status = self.redis_client.get(f"tl_{next_node}")
                if tl_status == "RED":
                    can_enter = False
            except:
                pass # Se Redis fallisce, prudenza (o passa lo stesso per debug)

        if can_enter:
            # VIA LIBERA
            prev_node = self.pos
            self.model.grid.move_agent(self, next_node)
            self.path.pop(0)
            
            self.publish_event("MOVED", {
                "from": prev_node, "to": next_node, "dest": self.destination
            })
        else:
            # SEMAFORO ROSSO
            # L'auto aspetta (non fa nulla in questo step)
            # Pubblichiamo evento di attesa (Opzionale, per debug)
            # print(f"[{self.lamport_clock}] 🚦 Auto {self.unique_id}: Ferma al rosso per nodo {next_node}")
            pass

    def wait_logic(self):
        self.wait_timer -= 1
        if self.wait_timer <= 0:
            self.tick_clock() # Ripartire è un evento
            print(f"[{self.lamport_clock}] 🚗 Auto {self.unique_id}: Riparte!")
            self.state = "MOVING"

    def select_new_destination(self):
        all_nodes = list(self.model.G.nodes())
        if self.pos in all_nodes:
            all_nodes.remove(self.pos)
            
        if all_nodes:
            self.destination = self.random.choice(all_nodes)
            try:
                self.path = nx.shortest_path(
                    self.model.G, 
                    source=self.pos, 
                    target=self.destination, 
                    weight='weight'
                )
                self.publish_event("PLANNING", {
                    "start": self.pos,
                    "end": self.destination,
                    "steps": len(self.path)
                })
            except nx.NetworkXNoPath:
                self.path = []

    def publish_event(self, event_type, data):
        """Invia messaggio con LAMPORT CLOCK"""
        if self.redis_client:
            message = {
                "agent_id": self.unique_id,
                "clock": self.lamport_clock, # <--- ECCOLO
                "event": event_type,
                "data": data
            }
            self.redis_client.publish('traffic_channel', json.dumps(message))
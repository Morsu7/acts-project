import networkx as nx
import redis
import json
from mesa import Agent

class VehicleAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.path = [] 
        self.destination = None
        self.state = "QUEUED"
        self.travel_timer = 0
        self.lamport_clock = 0 
        self.next_node_buffer = None 
        
        # Flag per non premere il sensore mille volte
        self.sensor_registered = False 

        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        except: self.redis_client = None

    def step(self):
        self.tick_clock()
        if self.state == "QUEUED":
            self.queue_logic()
        elif self.state == "DRIVING":
            self.driving_logic()

    def tick_clock(self): self.lamport_clock += 1

    def queue_logic(self):
        if not self.path: 
            self.select_new_destination()
            return
        
        if len(self.path) <= 1:
            self.path = []
            return

        next_node = self.path[1]
        current_node = self.pos
        
        # --- 1. SENSORE (Induction Loop) ---
        # Se sono fermo e non mi sono ancora registrato, dillo al semaforo
        if not self.sensor_registered and self.redis_client:
            # Incrementa contatore: sensor_NODO -> { DA_NODO: +1 }
            self.redis_client.hincrby(f"sensor_{next_node}", str(current_node), 1)
            self.sensor_registered = True

        can_enter = False
        
        if self.redis_client:
            try:
                # --- 2. CONTROLLO SEMAFORO (ACL) ---
                allowed_json = self.redis_client.get(f"tl_{next_node}_allowed")
                if allowed_json:
                    allowed_sources = json.loads(allowed_json)
                    if current_node in allowed_sources:
                        can_enter = True
                
                # --- 3. CONTROLLO FISICO (Mutex) ---
                if can_enter:
                    lock_key = f"lock_node_{next_node}"
                    is_locked = self.redis_client.set(lock_key, self.unique_id, nx=True, ex=5)
                    if not is_locked:
                        can_enter = False
            except: pass 
        
        if can_enter:
            # PARTENZA
            # Rimuovo la mia presenza dal sensore (decremento)
            if self.sensor_registered and self.redis_client:
                self.redis_client.hincrby(f"sensor_{next_node}", str(current_node), -1)
                self.sensor_registered = False

            try:
                edge = self.model.G.get_edge_data(self.pos, next_node)
                dist = edge.get('weight', 0.5)
                self.travel_timer = int(dist * 20) 
                if self.travel_timer < 5: self.travel_timer = 5
            except: self.travel_timer = 10

            self.next_node_buffer = next_node
            self.release_lock(self.pos)
            self.state = "DRIVING"
            
            self.publish_event("DEPARTING", {
                "from": self.pos, 
                "to": next_node, 
                "duration": self.travel_timer
            })

    def driving_logic(self):
        self.travel_timer -= 1
        if self.travel_timer <= 0:
            self.model.grid.move_agent(self, self.next_node_buffer)
            self.path.pop(0) 
            self.state = "QUEUED"
            self.sensor_registered = False # Reset stato sensore per il nuovo nodo
            self.publish_event("ARRIVED_NODE", {"node": self.pos})

    def select_new_destination(self):
        nodes = list(self.model.G.nodes())
        if self.pos in nodes: nodes.remove(self.pos)
        if nodes:
            self.destination = self.random.choice(nodes)
            try:
                self.path = nx.shortest_path(self.model.G, self.pos, self.destination, weight='weight')
                self.publish_event("PLANNING", {"dest": self.destination, "steps": len(self.path)})
            except: self.path = []

    def release_lock(self, node_id):
        if self.redis_client:
            try:
                key = f"lock_node_{node_id}"
                val = self.redis_client.get(key)
                if val and int(val) == self.unique_id:
                    self.redis_client.delete(key)
            except: pass

    def publish_event(self, evt, data):
        if self.redis_client:
            msg = {"agent_id": self.unique_id, "clock": self.lamport_clock, "event": evt, "data": data}
            self.redis_client.publish("traffic_channel", json.dumps(msg))
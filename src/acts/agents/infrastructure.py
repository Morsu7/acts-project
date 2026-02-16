from mesa import Agent
import redis
import json

class TrafficLightAgent(Agent):
    def __init__(self, unique_id, model, intersection_id, controlled_nodes):
        super().__init__(unique_id, model)
        self.intersection_id = intersection_id
        self.controlled_nodes = list(controlled_nodes)
        self.state = "GREEN"
        
        # --- CONFIGURAZIONE ---
        self.active_phase = 0 
        self.phase_timer = 0
        
        # FIX 1: Abbassiamo la soglia a 1. Basta 1 auto per chiamare il verde!
        self.cars_threshold = 1 
        
        self.side_street_duration = 15 
        
        incoming_by_intersection = {}
        controlled_set = set(self.controlled_nodes)

        for target_node in self.controlled_nodes:
            for source_node in model.G.predecessors(target_node):
                source_intersection = model.G.nodes[source_node].get("intersection", source_node)
                if source_intersection == self.intersection_id:
                    continue
                incoming_by_intersection.setdefault(source_intersection, set()).add(source_node)

        approaches = list(incoming_by_intersection.values())
        mid = len(approaches) // 2
        if mid == 0 and approaches:
            mid = 1

        phase0 = set()
        for group in approaches[:mid]:
            phase0.update(group)

        phase1 = set()
        for group in approaches[mid:]:
            phase1.update(group)

        self.phases = [sorted(phase0), sorted(phase1)]
        if not self.phases[1]:
            self.phases[1] = []

        try:
            self.redis = redis.Redis(host='localhost', port=6379, decode_responses=True)
            self.redis.delete(f"sensor_{self.intersection_id}")
            self.update_redis()
        except:
            self.redis = None

    def step(self):
        if self.active_phase == 0:
            # FASE DEFAULT: Resto verde finché non rilevo traffico laterale
            if self.should_switch_to_side():
                self.switch_phase(1)
                self.phase_timer = self.side_street_duration
        else:
            # FASE LATERALE: Conto alla rovescia
            self.phase_timer -= 1
            if self.phase_timer <= 0:
                self.switch_phase(0) # Torna al Default

    def should_switch_to_side(self):
        if not self.redis: return False
        
        # DEBUG: Vediamo cosa legge il semaforo!
        sensor_key = f"sensor_{self.intersection_id}"
        sensor_data = self.redis.hgetall(sensor_key)
        
        # Se non c'è fase laterale, esci
        if not self.phases[1]: return False

        side_nodes = self.phases[1]
        waiting_cars = 0
        
        for node in side_nodes:
            count = sensor_data.get(str(node), 0)
            waiting_cars += int(count)
            
        # FIX 2: Debug nel terminale se c'è qualcuno
        if waiting_cars > 0:
            print(f"[DEBUG TL_{self.intersection_id}] Coda rilevata da {side_nodes}: {waiting_cars} auto (Soglia: {self.cars_threshold})")

        return waiting_cars >= self.cars_threshold

    def switch_phase(self, new_phase_idx):
        self.active_phase = new_phase_idx
        # Aggiorno stato grafico (Verde solo se Main Street)
        self.state = "GREEN" if self.active_phase == 0 else "RED"
        self.update_redis()

    def update_redis(self):
        for node_id in self.controlled_nodes:
            self.model.G.nodes[node_id]["tl_state"] = self.state

        if self.redis:
            allowed_nodes = self.phases[self.active_phase]
            self.redis.set(f"tl_{self.intersection_id}_allowed", json.dumps(allowed_nodes))

            msg = {
                "agent_id": f"TL_{self.intersection_id}",
                "clock": 0,
                "event": "PHASE_CHANGE",
                "data": {
                    "intersection": self.intersection_id,
                    "new_phase": "DEFAULT" if self.active_phase == 0 else "SIDE",
                    "allowed_from": allowed_nodes
                }
            }
            self.redis.publish("traffic_channel", json.dumps(msg))
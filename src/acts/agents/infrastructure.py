from mesa import Agent
import redis
import json

class TrafficLightAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.state = "GREEN"
        
        # --- CONFIGURAZIONE ---
        self.active_phase = 0 
        self.phase_timer = 0
        
        # FIX 1: Abbassiamo la soglia a 1. Basta 1 auto per chiamare il verde!
        self.cars_threshold = 1 
        
        self.side_street_duration = 15 
        
        self.neighbors = list(model.G.neighbors(unique_id))
        mid = len(self.neighbors) // 2
        if mid == 0 and self.neighbors: mid = 1
        
        self.phases = [
            self.neighbors[:mid],  # Fase 0 (DEFAULT)
            self.neighbors[mid:]   # Fase 1 (LATERALE)
        ]
        # Se la fase laterale è vuota (vicolo cieco), non serve logica adattiva
        if not self.phases[1]: self.phases[1] = []

        try:
            self.redis = redis.Redis(host='localhost', port=6379, decode_responses=True)
            self.redis.delete(f"lock_node_{unique_id}")
            self.redis.delete(f"sensor_{unique_id}")
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
        sensor_key = f"sensor_{self.unique_id}"
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
            print(f"[DEBUG TL_{self.unique_id}] Coda rilevata da {side_nodes}: {waiting_cars} auto (Soglia: {self.cars_threshold})")

        return waiting_cars >= self.cars_threshold

    def switch_phase(self, new_phase_idx):
        self.active_phase = new_phase_idx
        # Aggiorno stato grafico (Verde solo se Main Street)
        self.state = "GREEN" if self.active_phase == 0 else "RED"
        self.update_redis()

    def update_redis(self):
        if self.redis:
            allowed_nodes = self.phases[self.active_phase]
            self.redis.set(f"tl_{self.unique_id}_allowed", json.dumps(allowed_nodes))
            
            # Pubblica evento
            msg = {
                "agent_id": f"TL_{self.unique_id}",
                "clock": 0,
                "event": "PHASE_CHANGE",
                "data": {
                    "new_phase": "DEFAULT" if self.active_phase == 0 else "SIDE",
                    "allowed_from": allowed_nodes
                }
            }
            self.redis.publish("traffic_channel", json.dumps(msg))
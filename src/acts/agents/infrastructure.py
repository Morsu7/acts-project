from mesa import Agent
import redis

class TrafficLightAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.state = "GREEN" # Stati: GREEN, RED
        self.timer = self.random.randint(5, 15) # Tempo casuale per sfasare i semafori
        
        # Connessione al Middleware (Redis)
        # Ogni semaforo è un processo autonomo che pubblica il suo stato
        try:
            self.redis = redis.Redis(host='localhost', port=6379, decode_responses=True)
            # Scriviamo subito lo stato iniziale nel DB condiviso
            # Chiave: "tl_<node_id>", Valore: "GREEN"
            self.redis.set(f"tl_{unique_id}", self.state)
        except redis.ConnectionError:
            self.redis = None

    def step(self):
        # Logica semplice: cambia colore ogni tot step
        self.timer -= 1
        if self.timer <= 0:
            self.switch_light()
            self.timer = 10 # Reset timer

    def switch_light(self):
        if self.state == "GREEN":
            self.state = "RED"
        else:
            self.state = "GREEN"
            
        # AGGIORNAMENTO DISTRIBUITO
        # Scriviamo su Redis. Le auto leggeranno da qui, non dalla memoria di Python!
        if self.redis:
            self.redis.set(f"tl_{self.unique_id}", self.state)
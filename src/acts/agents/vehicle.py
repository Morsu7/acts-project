from mesa import Agent

class VehicleAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)

    def step(self):
        self.move()

    def move(self):
        # In una NetworkGrid, get_neighbors restituisce gli ID dei nodi connessi (es: [3, 5, 9])
        possible_steps = self.model.grid.get_neighbors(self.pos, include_center=False)
        
        if len(possible_steps) > 0:
            # Scegli un nodo a caso
            new_node_id = self.random.choice(possible_steps)
            
            # MUOVI L'AGENTE (Passando l'ID del nodo, NON coordinate x,y)
            self.model.grid.move_agent(self, new_node_id)
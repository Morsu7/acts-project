from mesa import Agent

class Road(Agent):
    """
    Un pezzo di asfalto con una direzione specifica.
    direction: una tupla (dx, dy) che indica dove si può andare.
               Es: (1, 0) = Est, (0, -1) = Nord (in Mesa y cresce verso l'alto solitamente)
    """
    def __init__(self, unique_id, model, direction=None):
        super().__init__(unique_id, model)
        self.type = "road"
        self.direction = direction # Tupla (dx, dy)

class Obstacle(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.type = "building"

class TrafficLight(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.type = "traffic_light"
        self.state = True
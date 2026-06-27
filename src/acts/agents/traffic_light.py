from acts.utils.utils_agents import _is_vehicle_agent
from acts.agents.state.traffic_light_state import TrafficLightRuntimeState, LightStatus

from acts.agents.publishing_agent import PublishingAgent

from dataclasses import dataclass, field

@dataclass
class Request:
    requester_id: str
    requester_direction_id: str
    requester_score: float
    request_clock: int

@dataclass
class DirectionState:   # Each indipendent group of edges controlled by a traffic light has its own state
    runtime: TrafficLightRuntimeState = field(default_factory=TrafficLightRuntimeState)
    permissions: dict = field(default_factory=dict)     # Dictionary to store agents that have granted permission to turn green
    time_since_last_request: int = 0                    # Counter to track time since the last request was sent
    request_clock: int = 0                              # Lamport clock value when the last request was sent
    must_turn_yellow: bool = False                      # Flag to indicate if the light must turn yellow (before giving permission to another traffic light)

class ControlledDirection:
    """A group of edges that change color together."""
    def __init__(self, direction_id: str, edges: list):
        self.direction_id = direction_id
        self.edges = edges
        self.state = DirectionState()

class TrafficLightAgent(PublishingAgent):

    # PARAMETERS (TODO: make them configurable and move them to a config file)
    MIN_GREEN_TIME = 5
    YELLOW_TIME = 2
    TIME_BETWEEN_REQUESTS = 3 # In mesa ticks

    def __init__(self, unique_id, model, intersection_id, node_id, controlled_directions, neighbors=None):
        super().__init__(unique_id, model, f"channel_{intersection_id}")
        self.intersection_id = intersection_id
        self.node_id = node_id
        self.num_neighbors = neighbors
        self.lamport_clock = 0

        # Turn the groups of edges in ControlledDirection objects
        #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} controls the following directions: {controlled_directions}")
        self.directions: list[ControlledDirection] = [
            ControlledDirection(direction_id=f"{self.unique_id}_dir{i}", edges=edges)
            for i, edges in enumerate(controlled_directions)
        ]

        self.controlled_directions = controlled_directions  # Independent groups of edges controlled by this traffic light.
                                                            # Each edge in a group has to be green at the same time, while edges in different groups can be green independently.

        self.requests: dict[str, Request] = {}

    # Public API: called by Mesa scheduler.
    def step(self):
        self._detect_queue_size()       # detect presence of waiting cars and update waiting time
                                        # TODO: detect arriving cars before they queue up
        self._receive_messages()        # receive messages from other tl
        self._decide_state()        

        # Each direction independently checks
        for direction in self.directions:
            if direction.state.runtime.status == LightStatus.RED and self._has_waiting_vehicles(direction):
                if direction.state.time_since_last_request >= self.TIME_BETWEEN_REQUESTS:
                    self._request_green_light(direction)    # The request is specific to the direction
                    #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} sent a request to turn green for direction {direction.direction_id} with score {self._compute_score(direction)}\n")
            direction.state.time_since_last_request += 1
        
        self._update_graph()

    def _send_event(self, event_type, data):
        self.lamport_clock += 1
        self.publish_event(event_type, data, self.lamport_clock)

    # TODO: calculate different score for each direction
    def _detect_queue_size(self):
        # Prende tutti gli agenti nella cella dell'incrocio
        agents = self.model.grid.get_cell_list_contents([self.node_id])

        # Filtra tenendo solo i veicoli realmente in coda ("QUEUED")
        queued_vehicles_count = sum(
            1 for a in agents 
            if _is_vehicle_agent(a) and a.state == "QUEUED"
        )

        # Assegna il totale indistintamente a tutte le direzioni dell'incrocio
        for direction in self.directions:
            direction_state = direction.state.runtime
            direction_state.queue_length = queued_vehicles_count
            
            if direction_state.queue_length > 0:
                direction_state.waiting_time += 1
            else:
                direction_state.waiting_time = 0  # Reset se non ci sono auto

    def _has_waiting_vehicles(self, direction: ControlledDirection) -> bool:
        return direction.state.runtime.queue_length > 0

    def _compute_score(self, direction: ControlledDirection = None) -> float:
        match direction.state.runtime.status:
            case LightStatus.GREEN if direction.state.runtime.status_time < self.MIN_GREEN_TIME:
                return 1000  # Maximum priority. Light must not change to red before minimum green time is reached.
            case LightStatus.YELLOW:
                return 1000  # Maximum priority to keep light until time is up
        
        return direction.state.runtime.queue_length * (direction.state.runtime.waiting_time + 1)  # +1 to avoid zero score

    def _request_green_light(self, direction: ControlledDirection):
        # Send a request to the intersection controller (or other traffic lights) to turn green
        #direction.state.permissions = {}  # Reset received permissions for this step
        direction.state.request_clock = self.lamport_clock  # Store the Lamport clock value when the request is sent
        direction.state.time_since_last_request = 0  # Reset the counter after sending a request
        data = {
            "direction_id": direction.direction_id,
            "queue_score": self._compute_score(direction)
        }
        self._send_event("REQUEST_GREEN", data)

    def _decide_state(self):
        for direction in self.directions:
            direction.state.runtime.status_time += 1 # Increment the time spent in the current state

            match direction.state.runtime.status:
                case LightStatus.YELLOW:
                    if direction.state.runtime.status_time >= self.YELLOW_TIME:
                        direction.state.runtime.status = LightStatus.RED
                        direction.state.runtime.status_time = 0
                case LightStatus.GREEN:
                    if direction.state.must_turn_yellow:
                        direction.state.runtime.status = LightStatus.YELLOW
                        direction.state.must_turn_yellow = False
                        direction.state.runtime.status_time = 0
                case LightStatus.RED:
                    if len(direction.state.permissions) == self.num_neighbors:
                        #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} has received all permissions to turn green for direction {direction.direction_id}\n")
                        direction.state.runtime.status = LightStatus.GREEN
                        direction.state.runtime.status_time = 0
                        direction.state.permissions = {}  # Reset permissions after turning green

    def _send_allow_green(self, target_tl_id, target_direction_id, request_clock):
        data = {
            "target_tl_id": target_tl_id,   # Include the destination agent to facilitate filtering on the receiving side
            "target_direction_id": target_direction_id,
            "request_clock": request_clock
        }
        self._send_event("ALLOW_GREEN", data)

    # When receiving a green permission, store it if not outdated
    def _store_permission(self, message):
        message_data = message["data"]
        for direction in self.directions:
            if direction.direction_id == message_data["target_direction_id"]:
                if message_data["request_clock"] < direction.state.request_clock:
                    return  # Ignore outdated permission messages
                direction.state.permissions[message["agent_id"]] = True

    def _receive_messages(self):
        # filter per message type and update the requests dictionary
        messages = self.get_messages() or []
        for msg in messages:
            self.lamport_clock = max(self.lamport_clock, msg["clock"]) + 1
            match msg['event']:
                case "ALLOW_GREEN":
                    if msg["data"]["target_tl_id"] == self.unique_id:
                        self._store_permission(msg)
                case "REQUEST_GREEN":
                    requester_id = msg["agent_id"]
                    if requester_id == self.unique_id:
                        continue  # Ignore requests from self
                    requester_direction_id = msg["data"]["direction_id"]
                    requester_score = msg["data"]["queue_score"]
                    request_clock = msg["clock"]
                    self._store_request(requester_id, requester_direction_id, requester_score, request_clock)

        to_process = list(self.requests.keys())
        for id in to_process:
            request = self.requests[id]
            # TODO: each direction independently checks if it can give permission to the requester
            if self._can_give_permission(request):
                if self._are_all_directions_red():
                    self._send_allow_green(request.requester_id, request.requester_direction_id, request.request_clock)
                    self.requests.pop(id)  # Remove the request after granting permission
                else:
                    for direction in self.directions:
                        if direction.state.runtime.status == LightStatus.GREEN:
                            direction.state.must_turn_yellow = True  # Set the flag to turn yellow before granting permission
            else:
                self.requests.pop(id)  # Remove the request if it cannot be granted
        
        #self.requests.clear()  # Clear requests after processing

    def _are_all_directions_red(self) -> bool:
        return all(direction.state.runtime.status == LightStatus.RED for direction in self.directions)
            
    def _can_give_permission(self, request: Request) -> bool:
        # TODO: check based on constraint groups
        for direction in self.directions:
            if self._compute_score(direction) > request.requester_score:
                #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} cannot grant permission to {request.requester_id} for direction {request.requester_direction_id} because its score ({self._compute_score(direction)}) is higher than the requester's score ({request.requester_score})\n")
                return False
                
        return True  # TEMPORARY: If no direction has a higher score, grant permission

    def _store_request(self, requester_id: str, requester_direction_id: str, requester_score: float, request_clock: int) -> None:
        existing = self.requests.get(requester_direction_id)

        # keep only most recent request per requester
        if existing is None or request_clock > existing.request_clock:
            self.requests[requester_direction_id] = Request(requester_id, requester_direction_id, requester_score, request_clock)

    def _update_graph(self):
        # Update the graph with the current state of the traffic light
        edges = self.model.G.edges(self.node_id, data=True)
        for source, target, edge_data in edges:
            for direction in self.directions:
                if any(target == edge[1] for edge in direction.edges):
                    edge_data["tl_priority_score"] = self._compute_score(direction)
                    edge_data["tl_waiting_cars"] = direction.state.runtime.queue_length
                    edge_data["tl_waiting_seconds"] = direction.state.runtime.waiting_time
                    edge_data["tl_state"] = direction.state.runtime.status
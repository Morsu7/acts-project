from acts.utils.utils_agents import _is_vehicle_agent
from acts.agents.state import DirectionState, TrafficLightRuntimeState, LightStatus

from acts.agents.system_agent import SystemAgent

from dataclasses import dataclass, field

@dataclass
class Request:
    requester_id: str
    requester_direction_id: str
    requester_score: float
    request_clock: int

class ControlledDirection:
    """A group of edges that change color together."""
    def __init__(self, direction_id: str, edges: list, destinations_ids: list):
        self.direction_id = direction_id
        self.edges = edges
        self.destinations_ids = destinations_ids
        self.state = DirectionState()

class IncomingTrafficWave:
    """A group of cars that are approaching the traffic light from a specific direction."""
    def __init__(self, source_id: str, num_cars: int, expected_arrival_time: int):
        self.source_id = source_id
        self.num_cars = num_cars
        self.expected_arrival_time = expected_arrival_time

class TrafficLightAgent(SystemAgent):

    # PARAMETERS (TODO: make them configurable and move them to a config file)
    MIN_GREEN_TIME = 5
    YELLOW_TIME = 2
    TIME_BETWEEN_REQUESTS = 3 # How often I can ask for green (In mesa ticks)
    TIME_BETWEEN_SIGNALS = 5 # How often I can tell a neighbour about incoming traffic (In mesa ticks)
    UNCERTAINTY_FACTOR = 0.5 # How much weight to give to incoming traffic when computing the score
    INTERSECTION_CROSSING_TIME = 3 # How long it takes for a car to cross the intersection (In mesa ticks)

    def __init__(self, unique_id, model, intersection_id, node_id, controlled_directions, inter_neighbors=None, outgoing_external_neighbors_travel_times=None):
        super().__init__(unique_id, model, f"channel_{intersection_id}")
        self.intersection_id = intersection_id
        self.node_id = node_id
        self.num_neighbors = inter_neighbors
        self.outgoing_external_neighbors_travel_times = outgoing_external_neighbors_travel_times
        self.ingoing_edges = None  # Wil l be lazily evaluated after every agent is placed
        self.lamport_clock = 0

        # Turn the groups of edges in ControlledDirection objects
        #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} controls the following directions: {controlled_directions}")
        self.directions: list[ControlledDirection] = [
            ControlledDirection(
                direction_id=f"{self.unique_id}_dir{i}", 
                edges=direction["edges"], 
                destinations_ids=direction["destinations"])
            for i, direction in enumerate(controlled_directions)
        ]

        self.requests: dict[str, Request] = {}

        self.possible_incoming_waves: list[IncomingTrafficWave] = []

    # Public API: called by Mesa scheduler.
    def step(self):
        self._detect_queue_size()       # detect presence of waiting cars and update waiting time
        self._receive_messages()        # receive messages from other tl
        self._decide_state()        

        # Each direction independently checks
        for direction in self.directions:
            if self._wants_green(direction):
                match direction.state.runtime.status:
                    case LightStatus.RED:
                        if direction.state.time_since_last_request >= self.TIME_BETWEEN_REQUESTS:
                            self._request_green_light(direction)    # The request is specific to the direction
                            #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} sent a request to turn green for direction {direction.direction_id} with score {self._compute_score(direction)}\n")
                    case LightStatus.GREEN:
                        if direction.state.time_since_last_signal >= self.TIME_BETWEEN_SIGNALS:
                            if direction.state.runtime.queue_length > 0:
                                #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} is sending traffic signal for direction {direction.direction_id} with score {self._compute_score(direction)}\n")
                                self._send_traffic_signal(direction)  # The signal is specific to the direction
                            
            direction.state.add_time_past(1)

        self._update_incoming_waves_ETA()
        self._update_graph()

    def _update_incoming_waves_ETA(self):
        for wave in self.possible_incoming_waves:
            wave.expected_arrival_time -= 1

        # Remove waves that should be arrived if existent
        self.possible_incoming_waves = [wave for wave in self.possible_incoming_waves if wave.expected_arrival_time > 0]

    def _send_event(self, event_type, data, broadcast=False):
        self.lamport_clock += 1
        if broadcast:
            self.broadcast_message(event_type, data, self.lamport_clock)
        else:
            self.publish_event(event_type, data, self.lamport_clock)

    def _get_ingoing_edges(self):   # lazy evaluation of ingoing edges, makes sure that each agent is already placed on the grid before trying to find them
        if self.ingoing_edges is None:
            self.ingoing_edges = self._build_ingoing_edges(self.outgoing_external_neighbors_travel_times.keys())

        return self.ingoing_edges

    def _build_ingoing_edges(self, agents_ids):
        # Edges that come from neighboring intersections and lead to this traffic light
        ingoing_edges = self.model.G.in_edges(self.node_id, data=False)
        
        neighbor_node_ids = set()
        for source, _ in ingoing_edges:
            cell_agents = self.model.grid.get_cell_list_contents([source])
            for agent in cell_agents:
                if getattr(agent, "unique_id", None) in getattr(self, "outgoing_external_neighbors_travel_times", []).keys():
                    neighbor_node_ids.add(source)
                    break # Found the matching external neighbor agent on this node

        ingoing_lanes = [
            (source, target) for source, target in ingoing_edges
            if source in neighbor_node_ids
        ]

        return ingoing_lanes

    # This method gets information directly from the model's graph and not from the distributed system
    # this is a wanted behavior, because this function simulates a physical sensor placed on the traffic light
    # that detects the cars in front of the lanes. 
    def _detect_queue_size(self):
        # 1. Get vehicles that are already QUEUED at the stop line (on the node)
        node_agents = self.model.grid.get_cell_list_contents([self.node_id])
        queued_vehicles = [a for a in node_agents if _is_vehicle_agent(a) and a.state == "QUEUED"]

        # Define how close a driving car must be (in simulation ticks) to be counted
        NEAR_TRAFFIC_LIGHT_THRESHOLD = 5 

        for direction in self.directions:
            direction_state = direction.state.runtime
            #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} with edges {direction.edges}\n")
            # Edges that go inside the intersection
            outgoing_lanes = set(int(edge[1]) for edge in direction.edges)
            ingoing_lanes = self._get_ingoing_edges()
            #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} sees the following outgoing lanes: {outgoing_lanes}\n")
            #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} sees the following ingoing lanes: {ingoing_lanes}\n")
            
            count = 0

            # --- CASE 1: COUNT QUEUED VEHICLES ---
            # They are at the light. Check where they want to exit right now (path[1]).
            for v in queued_vehicles:
                if v.path and len(v.path) > 1:
                    next_node_intent = v.path[1]
                    # Check if this exit trajectory belongs to the current direction handler
                    if next_node_intent in outgoing_lanes:
                        count += 1

            # --- CASE 2: COUNT CLOSE DRIVING VEHICLES (ANTICIPATION) ---
            # They are approaching. Check in which lane they are (path[2]).
            for source, target in ingoing_lanes:

                edge_data = self.model.G.get_edge_data(source, target) or {}
                driving_vehicles_on_edge = edge_data.get("vehicles", [])

                for v in driving_vehicles_on_edge:
                    if v.state == "DRIVING" and v.travel_timer <= NEAR_TRAFFIC_LIGHT_THRESHOLD:
                        if v.path and len(v.path) > 2:
                            #print(f"car path: {v.path}\n")
                            # path[1] is this light. path[2] is their downstream turn.
                            downstream_node_intent = v.path[2]
                            
                            # Check if that future turn aligns with this direction grouping
                            if downstream_node_intent in outgoing_lanes:
                                count += 1
                        else:
                            # Fallback if the traffic light itself is their absolute destination
                            count += 1
                    
            direction_state.queue_length = count
            
            # Update waiting time tracking
            if direction_state.queue_length > 0:
                direction_state.waiting_time += 1
            else:
                direction_state.waiting_time = 0

    def _wants_green(self, direction: ControlledDirection) -> bool:
        return 0 < self._compute_score(direction) < float('inf')

    def _compute_score(self, direction: ControlledDirection = None) -> float:
        own_score = direction.state.runtime.queue_length * (direction.state.runtime.waiting_time + 1)     # +1 to avoid zero score

        score = own_score + sum(wave.num_cars / (1 + (wave.expected_arrival_time / 10)) for wave in self.possible_incoming_waves) * self.UNCERTAINTY_FACTOR
        
        return score

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

    def _send_traffic_signal(self, direction: ControlledDirection):
        for id in direction.destinations_ids:
            data = {
                "target_tl_id": id,
                "num_cars": direction.state.runtime.queue_length
            }
            self._send_event("TRAFFIC_SIGNAL", data)
            print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} sent traffic signal to {id} with {data['num_cars']} cars\n")
        
        direction.state.time_since_last_signal = 0

    def _forward_traffic_signal(self, incoming_score: float):
        for id, eta in self.outgoing_external_neighbors_travel_times.items():
            data = {
                "target_tl_id": id,
                "eta": eta + self.INTERSECTION_CROSSING_TIME,
                "num_cars": incoming_score
            }
            self._send_event("TRAFFIC_SIGNAL_FORWARD", data, broadcast=True)
            print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} forwarded traffic signal to {id} with {incoming_score} cars\n")

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
        messages = [*self.get_messages(), *self.get_broadcast_messages()]

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
                case "TRAFFIC_SIGNAL":
                    if msg["data"]["target_tl_id"] == self.unique_id:
                        self._forward_traffic_signal(msg["data"]["num_cars"])
                case "TRAFFIC_SIGNAL_FORWARD":
                    if msg["data"]["target_tl_id"] == self.unique_id:
                        print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} COULD receive traffic signal with {msg['data']['num_cars']} cars from {msg['agent_id']}\n")
                        wave = IncomingTrafficWave(source_id=msg["agent_id"], num_cars=msg["data"]["num_cars"], expected_arrival_time=msg["data"]["eta"])
                        print(f"Made a wave from {msg['agent_id']} with {msg['data']['num_cars']} cars and ETA {msg['data']['eta']}\n")
                        self.possible_incoming_waves.append(wave)

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
        phases = self.model.intersection_meta[self.intersection_id].get("phases", {})
        requester_phase = phases.get(request.requester_direction_id)

        for direction in self.directions:
            my_phase = phases.get(direction.direction_id)

            # skip blocks if we share the same green phase
            if my_phase is not None and my_phase == requester_phase:
                continue

            match direction.state.runtime.status:
                case LightStatus.GREEN if direction.state.runtime.status_time < self.MIN_GREEN_TIME:
                    return False            # enforce minimum green time
                case LightStatus.YELLOW:
                    return False            # wait for yellow to finish

            # deny if we have more traffic waiting
            if self._compute_score(direction) > request.requester_score:
                return False
                
        return True

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
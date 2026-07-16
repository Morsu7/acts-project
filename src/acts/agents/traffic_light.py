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
    TIME_BETWEEN_REQUESTS = 3 # How often I can ask for green (In mesa ticks)
    TIME_BETWEEN_SIGNALS = 5 # How often I can tell a neighbour about incoming traffic (In mesa ticks)
    UNCERTAINTY_FACTOR = 0.5 # How much weight to give to incoming traffic when computing the score
    INTERSECTION_CROSSING_TIME = 3 # How long it takes for a car to cross the intersection (In mesa ticks)
    FAILSAFE_THRESHOLD = 6 # How long to wait before checking for failsafe (In mesa ticks)
    HEALTH_CHECK_THRESHOLD = 3 # How long before going into failsafe if no replies (In mesa ticks)

    RECOVERY_THRESHOLD = 6 # How long to wait before checking for recovery (In mesa ticks)

    YELLOW_TIME = INTERSECTION_CROSSING_TIME

    MIN_GREEN_TIME = 5
    MAX_GREEN_TIME = 30 # After this time, i need to concede green permission even when asked even if my score is higher
    GREEN_COOLDOWN_TIME = YELLOW_TIME + 5 # After turning yellow, i must wait at least this time before asking to turn green again

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

        # Failsafe mechanism to detect not working traffic lights (deadlock detection)
        self.neighbor_quiet_time = {}
        self.failsafe_active = False
        self.health_check_active = False    # Is the traffic light currently checking the health of its neighbors
        self.health_check_replies = set()   
        self.health_check_timer = 0

        # Recovery mechanism during failsafe mode
        self.last_recovery_request_timer = 0

        self.turned_off = False

    # Public API: called by Mesa scheduler.
    def step(self):
        if self.turned_off:
            self._update_graph()
            return

        self._detect_queue_size()       # detect presence of waiting cars and update waiting time
        self._receive_messages()        # receive messages from other tl
        self._decide_state()        

        self._update_failsafe_timers()
        self._update_cooldown_timers()

        # 3 possible states: 1) normal operation, 2) failsafe active, 3) agent turned off (not working)
        if self.failsafe_active:
            self._handle_failsafe_recovery()
        else:   # normal operation
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

    def toggle_power(self) -> bool:
        self.set_power(self.turned_off)
        return not self.turned_off

    def set_power(self, power_on: bool) -> None:
        # if i set power_on on a traffic light that is off, i reset its state to RED
        if power_on and not self.is_working():
            for direction in self.directions:
                direction.state.runtime.status = LightStatus.RED
                direction.state.runtime.status_time = 0
                direction.state.must_turn_yellow = False
        self.turned_off = not power_on

    def is_working(self) -> bool:
        return not self.turned_off

    def get_status_summary(self) -> str:
        if self.turned_off:
            return "OFF"

        statuses = []
        for direction in self.directions:
            status = direction.state.runtime.status
            if status not in statuses:
                statuses.append(status)

        return "/".join(statuses) if statuses else "UNKNOWN"

    def _update_failsafe_timers(self):
        if self.failsafe_active:
            return
        
        for neighbor in self.neighbor_quiet_time:
            self.neighbor_quiet_time[neighbor] += 1

        trigger_check = any(t >= self.FAILSAFE_THRESHOLD for t in self.neighbor_quiet_time.values())

        if trigger_check and not self.health_check_active:
            self.health_check_active = True
            self.health_check_replies.clear()
            
            self._send_event("HEALTH_CHECK", {})   
            self.health_check_timer = 0

        if self.health_check_active:
            if len(self.health_check_replies) == self.num_neighbors:
                self.health_check_active = False
                self.health_check_timer = 0
                self.neighbor_quiet_time = {neighbor: 0 for neighbor in self.neighbor_quiet_time}  # Reset quiet time for all neighbors
                return
            if self.health_check_timer >= self.HEALTH_CHECK_THRESHOLD:
                self._activate_failsafe_mode()
                return
            self.health_check_timer += 1

    def _update_cooldown_timers(self):
        for direction in self.directions:
            if direction.state.green_cooldown > 0:
                direction.state.green_cooldown -= 1

    def _activate_failsafe_mode(self):
        self.failsafe_active = True
        self.health_check_active = False
        self.health_check_timer = 0
        for direction in self.directions:
            direction.state.runtime.status = LightStatus.FLASHING_YELLOW
            direction.state.runtime.status_time = 0

        print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} has entered failsafe mode\n")

    def _deactivate_failsafe_mode(self):
        self.failsafe_active = False
        self.health_check_active = False
        self.health_check_timer = 0
        self.last_recovery_request_timer = 0
        self.health_check_replies.clear()
        for direction in self.directions:
            direction.state.runtime.status = LightStatus.RED
            direction.state.runtime.status_time = 0
        print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} has exited failsafe mode\n")

    def _handle_failsafe_recovery(self):
        if self.last_recovery_request_timer >= self.RECOVERY_THRESHOLD:
            self._send_event("HEALTH_CHECK", {})
            self.last_recovery_request_timer = 0
            self.health_check_replies.clear()
        
        self.last_recovery_request_timer += 1
        #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} is in failsafe mode, waiting for recovery replies ({len(self.health_check_replies)}/{self.num_neighbors}) from sec {self.last_recovery_request_timer}\n")
        if len(self.health_check_replies) >= self.num_neighbors:
            self._deactivate_failsafe_mode()


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

        # Define how close a driving car must be (in meters) to be counted
        NEAR_TRAFFIC_LIGHT_THRESHOLD = 30 

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
                    if v.state == "DRIVING" and v.distance_to_node_meters <= NEAR_TRAFFIC_LIGHT_THRESHOLD:
                        if v.path and len(v.path) > 2:
                            #print(f"car path: {v.path}\n")
                            # path[1] is this light. path[2] is their downstream turn.
                            downstream_node_intent = v.path[2]
                            
                            # Check if that future turn aligns with this direction grouping
                            if downstream_node_intent in outgoing_lanes:
                                proximity_factor = (
                                    NEAR_TRAFFIC_LIGHT_THRESHOLD - v.distance_to_node_meters
                                ) / NEAR_TRAFFIC_LIGHT_THRESHOLD

                                count += proximity_factor
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
        if direction.state.green_cooldown > 0: return False
        return 0 < self._compute_score(direction) < float('inf')

    def _compute_score(self, direction):

        queue = direction.state.runtime.queue_length
        wait = direction.state.runtime.waiting_time

        own_score = (
            queue * 5 +
            wait
        )

        incoming = sum(
            wave.num_cars /
            (1 + wave.expected_arrival_time / 10)
            for wave in self.possible_incoming_waves
        )

        return own_score + incoming * self.UNCERTAINTY_FACTOR

    def _request_green_light(self, direction: ControlledDirection):
        # Send a request to the intersection controller (or other traffic lights) to turn green
        #direction.state.permissions = {}  # Reset received permissions for this step
        if not direction.state.permissions:
            direction.state.request_clock = self.lamport_clock  # Store the Lamport clock value when the request is sent

        direction.state.score = self._compute_score(direction)
        direction.state.time_since_last_request = 0  # Reset the counter after sending a request
        data = {
            "direction_id": direction.direction_id,
            "queue_score": direction.state.score,
            "request_clock": direction.state.request_clock
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
                        direction.state.green_cooldown = self.GREEN_COOLDOWN_TIME
                case LightStatus.GREEN:
                    if direction.state.must_turn_yellow and direction.state.runtime.status_time >= self.MIN_GREEN_TIME:
                        direction.state.runtime.status = LightStatus.YELLOW
                        direction.state.must_turn_yellow = False
                        direction.state.runtime.status_time = 0
                case LightStatus.RED:
                    if len(direction.state.permissions) == self.num_neighbors:
                        #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} has received all permissions to turn green for direction {direction.direction_id}\n")
                        direction.state.runtime.status = LightStatus.GREEN
                        direction.state.runtime.status_time = 0

                        direction.state.permissions = {}  # Reset permissions after turning green
                        direction.state.score = 0.0  # Reset score after turning green
                        self.deadlock_timer = 0  # Reset deadlock timer after successfully turning green (every agent is currently working)

    def _send_allow_green(self, target_tl_id, target_direction_id, request_clock):
        data = {
            "target_tl_id": target_tl_id,   # Include the destination agent to facilitate filtering on the receiving side
            "target_direction_id": target_direction_id,
            "request_clock": request_clock
        }
        self._send_event("ALLOW_GREEN", data)
        #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} sent ALLOW_GREEN to {target_tl_id} for direction {target_direction_id} with request clock {request_clock}\n")

    def _send_traffic_signal(self, direction: ControlledDirection):
        for id in direction.destinations_ids:
            data = {
                "target_tl_id": id,
                "num_cars": direction.state.runtime.queue_length
            }
            self._send_event("TRAFFIC_SIGNAL", data)
            #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} sent traffic signal to {id} with {data['num_cars']} cars\n")
        
        direction.state.time_since_last_signal = 0

    def _forward_traffic_signal(self, incoming_score: float):
        for id, eta in self.outgoing_external_neighbors_travel_times.items():
            data = {
                "target_tl_id": id,
                "eta": eta + self.INTERSECTION_CROSSING_TIME,
                "num_cars": incoming_score
            }
            self._send_event("TRAFFIC_SIGNAL_FORWARD", data, broadcast=True)
            #print(f"Traffic Light {self.unique_id} at intersection {self.intersection_id} forwarded traffic signal to {id} with {incoming_score} cars\n")

    # When receiving a green permission, store it if not outdated
    def _store_permission(self, message):
        message_data = message["data"]
        for direction in self.directions:
            if direction.direction_id == message_data["target_direction_id"]:
                if message_data["request_clock"] < direction.state.request_clock:
                    return  # Ignore outdated permission messages
                direction.state.permissions[message["agent_id"]] = True

    def _store_alive_signal(self, message):
        message_data = message["data"]
        if message_data["target_tl_id"] == self.unique_id:
            self.health_check_replies.add(message["agent_id"])

    def _receive_messages(self):
        # filter per message type and update the requests dictionary
        messages = [*self.get_messages(), *self.get_broadcast_messages()]
        messages.sort(key=lambda m: (m["clock"], m["agent_id"]))

        for msg in messages:
            self.lamport_clock = max(self.lamport_clock, msg["clock"]) + 1

            # We keep track of still working neighbors
            sender_id = msg["agent_id"]
            if sender_id != self.unique_id:
                self.neighbor_quiet_time[sender_id] = 0

            match msg['event']:
                # --- Universal Failsafe Protocol (Always Active) ---
                case "HEALTH_CHECK":
                    if msg['agent_id'] != self.unique_id:
                        self._send_alive_signal(msg["agent_id"])

                case "ALIVE_SIGNAL":
                    self._store_alive_signal(msg)

                # --- Operational Traffic Protocol (Ignored during Failsafe) ---
                case "ALLOW_GREEN" if not self.failsafe_active:
                    if msg["data"]["target_tl_id"] == self.unique_id:
                        self._store_permission(msg)

                case "REQUEST_GREEN" if not self.failsafe_active:
                    requester_id = msg["agent_id"]
                    if requester_id != self.unique_id:  # Using a direct conditional instead of 'continue'
                        self._store_request(
                            requester_id=requester_id,
                            requester_direction_id=msg["data"]["direction_id"],
                            requester_score=msg["data"]["queue_score"],
                            request_clock=msg["data"]["request_clock"]
                        )

                case "TRAFFIC_SIGNAL" if not self.failsafe_active:
                    if msg["data"]["target_tl_id"] == self.unique_id:
                        self._forward_traffic_signal(msg["data"]["num_cars"])

                case "TRAFFIC_SIGNAL_FORWARD" if not self.failsafe_active:
                    if msg["data"]["target_tl_id"] == self.unique_id:
                        wave = IncomingTrafficWave(
                            source_id=msg["agent_id"], 
                            num_cars=msg["data"]["num_cars"], 
                            expected_arrival_time=msg["data"]["eta"]
                        )
                        self.possible_incoming_waves.append(wave)

        if not self.failsafe_active:
            to_process = list(self.requests.keys())
            for id in to_process:
                request = self.requests[id]
                # TODO: each direction independently checks if it can give permission to the requester
                if self._can_give_permission(request):
                    if self._are_all_directions_red():
                        self._send_allow_green(request.requester_id, request.requester_direction_id, request.request_clock)
                        # TODO: fix check
                        for direction in self.directions:
                            if direction.state.permissions.get(request.requester_id):
                                phases = self.model.intersection_meta[self.intersection_id].get("phases", {})
                                my_phase = phases.get(direction.direction_id)
                                requester_phase = phases.get(request.requester_direction_id)
                                if my_phase is None or my_phase != requester_phase:
                                    direction.state.permissions.pop(request.requester_id)  # Remove the permission after granting it

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

    def _send_alive_signal(self, target_id: str):
        data = {
            "target_tl_id": target_id
        }
        self._send_event("ALIVE_SIGNAL", data)
            
    def _can_give_permission(self, request: Request) -> bool:
        phases = self.model.intersection_meta[self.intersection_id].get("phases", {})
        requester_phase = phases.get(request.requester_direction_id)

        for direction in self.directions:
            my_phase = phases.get(direction.direction_id)

            # skip blocks if we share the same green phase
            if my_phase is not None and my_phase == requester_phase:
                continue

            # concede green permission if i reached the maximum green time, even if my score is higher
            if direction.state.runtime.status == LightStatus.GREEN and direction.state.runtime.status_time >= self.MAX_GREEN_TIME:
                continue

            # concede green if i am currently in green cooldown, even if my score is higher
            if direction.state.green_cooldown > 0:
                continue

            match direction.state.runtime.status:
                case LightStatus.GREEN if direction.state.runtime.status_time < self.MIN_GREEN_TIME:
                    return False            # enforce minimum green time
                case LightStatus.YELLOW:
                    return False            # wait for yellow to finish

            if direction.state.runtime.status == LightStatus.GREEN:
                direction.state.score = self._compute_score(direction)
                # During a green light, constantly update my score

            my_score = direction.state.score
            
            if my_score > request.requester_score:
                return False

            # Tie-breaking
            if abs(my_score - request.requester_score) <= 1e-9:
                if direction.state.request_clock < request.request_clock:
                    return False
                
                if direction.state.request_clock == request.request_clock:
                    # Confronto alfabetico degli ID (es. "tl_1" vince contro "tl_2")
                    if self.unique_id < request.requester_id:
                        return False
                
        return True

    def _store_request(self, requester_id: str, requester_direction_id: str, requester_score: float, request_clock: int) -> None:
        existing = self.requests.get(requester_direction_id)

        # keep only most recent request per requester
        if existing is None or request_clock >= existing.request_clock:
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
                    edge_data["tl_state"] = "OFF" if self.turned_off else direction.state.runtime.status
                    edge_data['tl_state_time'] = direction.state.runtime.status_time
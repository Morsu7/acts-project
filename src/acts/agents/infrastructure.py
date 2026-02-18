from mesa import Agent

from acts.utils.redis_utils import (
    create_redis_client,
    publish_json,
    set_json,
)

class TrafficLightAgent(Agent):
    EVENT_CHANNEL = "traffic_channel"

    def __init__(self, unique_id, model, intersection_id, controlled_nodes):
        super().__init__(unique_id, model)
        self.intersection_id = intersection_id
        self.controlled_nodes = list(controlled_nodes)
        self.state = "GREEN"
        self.lamport_clock = 0

        self.active_phase = 0
        self.phase_timer = 0

        self.cars_threshold = 1
        self.side_street_duration = 15
        
        incoming_by_intersection = {}

        for target_node in self.controlled_nodes:
            self.model.G.nodes[target_node]["intersection_owner"] = self.intersection_id
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

        self.redis = create_redis_client()
        if self.redis:
            self.redis.delete(f"sensor_{self.intersection_id}")
        self.update_redis()

    def step(self):
        self.lamport_clock += 1
        if self.active_phase == 0:
            if self.should_switch_to_side():
                self.switch_phase(1)
                self.phase_timer = self.side_street_duration
        else:
            self.phase_timer -= 1
            if self.phase_timer <= 0:
                self.switch_phase(0)

    def should_switch_to_side(self):
        if not self.redis or not self.phases[1]:
            return False

        sensor_data = self.redis.hgetall(f"sensor_{self.intersection_id}")
        waiting_cars = 0
        for node in self.phases[1]:
            waiting_cars += int(sensor_data.get(str(node), 0))

        return waiting_cars >= self.cars_threshold

    def switch_phase(self, new_phase_idx):
        self.active_phase = new_phase_idx
        self.state = "GREEN" if self.active_phase == 0 else "RED"
        self.update_redis()

    def update_redis(self):
        allowed_nodes = self.phases[self.active_phase]

        for node_id in self.controlled_nodes:
            incoming_external = [
                source_node
                for source_node in self.model.G.predecessors(node_id)
                if self.model.G.nodes[source_node].get("intersection", source_node) != self.intersection_id
            ]

            if not incoming_external:
                node_state = "GREEN"
            elif any(source_node in allowed_nodes for source_node in incoming_external):
                node_state = "GREEN"
            else:
                node_state = "RED"

            self.model.G.nodes[node_id]["tl_state"] = node_state

        set_json(self.redis, f"tl_{self.intersection_id}_allowed", allowed_nodes)
        state_payload = {
            "intersection": self.intersection_id,
            "traffic_light_id": self.unique_id,
            "clock": self.lamport_clock,
            "state": self.state,
            "phase_index": self.active_phase,
            "allowed_from": allowed_nodes,
            "controlled_nodes": self.controlled_nodes,
        }
        set_json(self.redis, f"tl_{self.intersection_id}_state", state_payload)

        msg = {
            "agent_id": f"TL_{self.intersection_id}",
            "clock": self.lamport_clock,
            "event": "PHASE_CHANGE",
            "data": {
                "intersection": self.intersection_id,
                "new_phase": "DEFAULT" if self.active_phase == 0 else "SIDE",
                "allowed_from": allowed_nodes,
            },
        }
        publish_json(self.redis, self.EVENT_CHANNEL, msg)
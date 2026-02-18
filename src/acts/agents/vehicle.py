from __future__ import annotations

from typing import Optional

import networkx as nx
from mesa import Agent

from acts.utils.redis_utils import (
    create_redis_client,
    get_json,
    hash_increment,
    publish_json,
    release_lock_if_owner,
    try_acquire_lock,
)

class VehicleAgent(Agent):
    EVENT_CHANNEL = "traffic_channel"
    LOCK_TTL_SECONDS = 5

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.path = []
        self.destination = None
        self.state = "QUEUED"
        self.travel_timer = 0
        self.edge_total_timer = 0
        self.lamport_clock = 0
        self.next_node_buffer: Optional[int] = None

        self.sensor_registered = False
        self.sensor_target_intersection = None
        self.redis_client = create_redis_client()

    def _heuristic(self, source_node, target_node):
        source_pos = self.model.G.nodes[source_node].get("pos", (0.0, 0.0))
        target_pos = self.model.G.nodes[target_node].get("pos", (0.0, 0.0))
        dx = source_pos[0] - target_pos[0]
        dy = source_pos[1] - target_pos[1]
        return (dx * dx + dy * dy) ** 0.5

    def step(self):
        self.tick_clock()
        if self.state == "QUEUED":
            self.queue_logic()
        elif self.state == "DRIVING":
            self.driving_logic()

    def tick_clock(self):
        self.lamport_clock += 1

    def queue_logic(self):
        if not self.path:
            self.select_new_destination()
            return

        if len(self.path) <= 1:
            self.path = []
            return

        next_node = self.path[1]
        current_node = self.pos

        if not self.model.G.has_edge(current_node, next_node):
            self.plan_path_to_destination()
            return

        next_intersection = self.model.G.nodes[next_node].get("intersection", next_node)
        current_intersection = self.model.G.nodes[current_node].get("intersection", current_node)
        external_entry = current_intersection != next_intersection

        if external_entry and not self.sensor_registered:
            self._register_sensor(
                current_node=current_node,
                next_node=next_node,
                target_intersection=next_intersection,
            )

        can_enter = self._can_enter_next_node(
            current_node=current_node,
            next_node=next_node,
            current_intersection=current_intersection,
            next_intersection=next_intersection,
        )

        if can_enter:
            self._start_driving(current_node=current_node, next_node=next_node, next_intersection=next_intersection)

    def _register_sensor(self, current_node: int, next_node: int, target_intersection: int) -> None:
        sensor_key = f"sensor_{target_intersection}"
        if hash_increment(self.redis_client, sensor_key, str(current_node), 1):
            self.sensor_registered = True
            self.sensor_target_intersection = target_intersection
            self.publish_event("TL_REQUEST", {
                "from_node": current_node,
                "to_node": next_node,
                "target_intersection": target_intersection,
            })

    def _can_enter_next_node(
        self,
        current_node: int,
        next_node: int,
        current_intersection: int,
        next_intersection: int,
    ) -> bool:
        external_entry = current_intersection != next_intersection
        if not external_entry:
            return True

        if self.redis_client is None:
            return True

        allowed_sources = get_json(self.redis_client, f"tl_{next_intersection}_allowed", default=[])
        if current_node not in allowed_sources:
            self.publish_event("TL_WAIT", {
                "intersection": next_intersection,
                "from_node": current_node,
            })
            return False

        lock_key = f"lock_node_{next_node}"
        if not try_acquire_lock(
            self.redis_client,
            key=lock_key,
            owner_id=self.unique_id,
            ttl_seconds=self.LOCK_TTL_SECONDS,
        ):
            self.publish_event("LOCK_WAIT", {
                "node": next_node,
                "intersection": next_intersection,
            })
            return False

        return True

    def _start_driving(self, current_node: int, next_node: int, next_intersection: int) -> None:
        self._unregister_sensor(current_node=current_node)
        self.travel_timer = self._compute_travel_timer(next_node)
        self.edge_total_timer = self.travel_timer

        self.next_node_buffer = next_node
        self.release_lock(self.pos)
        self.state = "DRIVING"

        self.publish_event("DEPARTING", {
            "from": self.pos,
            "to": next_node,
            "duration": self.travel_timer,
            "intersection": next_intersection,
        })

    def _unregister_sensor(self, current_node: int) -> None:
        if not self.sensor_registered or self.sensor_target_intersection is None:
            return

        sensor_key = f"sensor_{self.sensor_target_intersection}"
        hash_increment(self.redis_client, sensor_key, str(current_node), -1)
        self.sensor_registered = False
        self.sensor_target_intersection = None

    def _compute_travel_timer(self, next_node: int) -> int:
        edge = self.model.G.get_edge_data(self.pos, next_node) or {}
        dist = edge.get("weight", 0.5)
        timer = int(dist * 20)
        return max(timer, 5)

    def driving_logic(self):
        self.travel_timer -= 1
        if self.travel_timer <= 0:
            self.model.grid.move_agent(self, self.next_node_buffer)
            self.path.pop(0)
            self.state = "QUEUED"
            self.edge_total_timer = 0
            self.sensor_registered = False
            self.sensor_target_intersection = None
            self.publish_event("ARRIVED_NODE", {"node": self.pos})

    def select_new_destination(self):
        nodes = list(self.model.G.nodes())
        if self.pos in nodes:
            nodes.remove(self.pos)
        if nodes:
            self.destination = self.random.choice(nodes)
            self.plan_path_to_destination()

    def plan_path_to_destination(self):
        if self.destination is None:
            self.path = []
            return
        try:
            self.path = nx.astar_path(
                self.model.G,
                self.pos,
                self.destination,
                heuristic=self._heuristic,
                weight='weight',
            )
            self.publish_event("PLANNING_ASTAR", {
                "dest": self.destination,
                "steps": len(self.path),
            })
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            self.path = []

    def release_lock(self, node_id):
        key = f"lock_node_{node_id}"
        release_lock_if_owner(self.redis_client, key=key, owner_id=self.unique_id)

    def publish_event(self, evt, data):
        msg = {
            "agent_id": self.unique_id,
            "clock": self.lamport_clock,
            "event": evt,
            "data": data,
        }
        publish_json(self.redis_client, self.EVENT_CHANNEL, msg)
from __future__ import annotations

from typing import Any, Optional

from mesa import Agent
from acts.agents.vehicle_logic.event_bus_publisher import EventBusPublisher
from acts.agents.vehicle_logic.movement_service import MovementService
from acts.agents.vehicle_logic.route_planner import ConstrainedRoutePlanner
from acts.agents.vehicle_logic.route_service import RouteService
from acts.agents.vehicle_logic.vehicle_state import VehicleRuntimeState

from acts.utils.redis_utils import (
    create_redis_client,
    get_json,
    release_lock_if_owner,
)


class VehicleAgent(Agent):
    EVENT_CHANNEL = "traffic_channel"
    LOCK_TTL_SECONDS = 5
    TRAVEL_TIME_SCALE = 20
    MIN_TRAVEL_TICKS = 5
    STATE_QUEUED = "QUEUED"
    STATE_DRIVING = "DRIVING"

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.runtime = VehicleRuntimeState(status=self.STATE_QUEUED)
        self.redis_client = create_redis_client()
        self.publisher = EventBusPublisher(self.redis_client, self.EVENT_CHANNEL, self.unique_id)
        self.route_planner = ConstrainedRoutePlanner(self.model.G, self._heuristic)
        self.route_service = RouteService(
            graph=self.model.G,
            random_source=self.random,
            planner=self.route_planner,
            runtime=self.runtime,
            publisher=self.publisher,
        )
        self.movement_service = MovementService(
            runtime=self.runtime,
            route_service=self.route_service,
            publisher=self.publisher,
            release_lock=self.release_lock,
            compute_travel_timer=self._compute_travel_timer,
            move_agent_to_node=self._move_agent_to_node,
            get_current_node=self._current_node,
            can_depart=self._can_depart_from_signal,
            state_queued=self.STATE_QUEUED,
            state_driving=self.STATE_DRIVING,
        )

    @property
    def path(self) -> list[int]:
        return self.runtime.path

    @path.setter
    def path(self, value: list[int]) -> None:
        self.runtime.path = value

    @property
    def destination(self) -> Optional[int]:
        return self.runtime.destination

    @destination.setter
    def destination(self, value: Optional[int]) -> None:
        self.runtime.destination = value

    @property
    def state(self) -> str:
        return self.runtime.status

    @state.setter
    def state(self, value: str) -> None:
        self.runtime.status = value

    @property
    def travel_timer(self) -> int:
        return self.runtime.travel_timer

    @travel_timer.setter
    def travel_timer(self, value: int) -> None:
        self.runtime.travel_timer = value

    @property
    def edge_total_timer(self) -> int:
        return self.runtime.edge_total_timer

    @edge_total_timer.setter
    def edge_total_timer(self, value: int) -> None:
        self.runtime.edge_total_timer = value

    @property
    def lamport_clock(self) -> int:
        return self.runtime.lamport_clock

    @lamport_clock.setter
    def lamport_clock(self, value: int) -> None:
        self.runtime.lamport_clock = value

    @property
    def next_node_buffer(self) -> Optional[int]:
        return self.runtime.next_node_buffer

    @next_node_buffer.setter
    def next_node_buffer(self, value: Optional[int]) -> None:
        self.runtime.next_node_buffer = value

    @property
    def sensor_registered(self) -> bool:
        return self.runtime.sensor_registered

    @sensor_registered.setter
    def sensor_registered(self, value: bool) -> None:
        self.runtime.sensor_registered = value

    @property
    def sensor_target_intersection(self) -> Optional[int]:
        return self.runtime.sensor_target_intersection

    @sensor_target_intersection.setter
    def sensor_target_intersection(self, value: Optional[int]) -> None:
        self.runtime.sensor_target_intersection = value

    def _heuristic(self, source_node: int, target_node: int) -> float:
        source_pos = self.model.G.nodes[source_node].get("pos", (0.0, 0.0))
        target_pos = self.model.G.nodes[target_node].get("pos", (0.0, 0.0))
        dx = source_pos[0] - target_pos[0]
        dy = source_pos[1] - target_pos[1]
        return (dx * dx + dy * dy) ** 0.5

    def _constrained_astar_path(self, source: int, target: int) -> list[int]:
        return self.route_planner.find_path(source, target)

    def step(self):
        self.tick_clock()
        if self.state == self.STATE_QUEUED:
            self.queue_logic()
        elif self.state == self.STATE_DRIVING:
            self.driving_logic()

    def tick_clock(self):
        self.runtime.lamport_clock += 1

    def queue_logic(self):
        self.movement_service.queue_step(owner_id=self.unique_id, current_node=self.pos)

    def _compute_travel_timer(self, next_node: int) -> int:
        edge = self.model.G.get_edge_data(self.pos, next_node) or {}
        dist = edge.get("weight", 0.5)
        timer = int(dist * self.TRAVEL_TIME_SCALE)
        return max(timer, self.MIN_TRAVEL_TICKS)

    def _move_agent_to_node(self, node_id: int) -> None:
        self.model.grid.move_agent(self, node_id)

    def _current_node(self) -> int:
        return self.pos

    def _can_depart_from_signal(self, current_node: int, next_node: int) -> bool:
        if self.redis_client is None:
            return True

        current_intersection = self.model.G.nodes[current_node].get("intersection", current_node)
        next_intersection = self.model.G.nodes[next_node].get("intersection", next_node)
        if current_intersection == next_intersection:
            return True

        allowed_sources = get_json(
            self.redis_client,
            f"tl_{next_intersection}_allowed",
            default=None,
        )
        if allowed_sources is None:
            return True

        return current_node in allowed_sources

    def driving_logic(self):
        self.movement_service.drive_step()

    def select_new_destination(self):
        self.route_service.select_new_destination(self.pos)

    def plan_path_to_destination(self):
        self.route_service.plan_path(self.pos)

    def release_lock(self, node_id: int):
        key = f"lock_node_{node_id}"
        release_lock_if_owner(self.redis_client, key=key, owner_id=self.unique_id)

    def publish_event(self, evt: str, data: dict[str, Any]):
        self.publisher.publish(evt, data, self.runtime.lamport_clock)
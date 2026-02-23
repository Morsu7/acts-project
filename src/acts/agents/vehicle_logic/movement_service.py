from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from acts.agents.vehicle_logic.event_bus_publisher import EventBusPublisher
from acts.agents.vehicle_logic.route_service import RouteService
from acts.agents.vehicle_logic.vehicle_state import VehicleRuntimeState


class MovementService:
    def __init__(
        self,
        runtime: VehicleRuntimeState,
        route_service: RouteService,
        publisher: EventBusPublisher,
        release_lock: Callable[[int], None],
        compute_travel_timer: Callable[[int], int],
        move_agent_to_node: Callable[[int], None],
        get_current_node: Callable[[], int],
        can_depart: Optional[Callable[[int, int], bool]],
        state_queued: str,
        state_driving: str,
    ):
        self.runtime = runtime
        self.route_service = route_service
        self.publisher = publisher
        self.release_lock = release_lock
        self.compute_travel_timer = compute_travel_timer
        self.move_agent_to_node = move_agent_to_node
        self.get_current_node = get_current_node
        self.can_depart = can_depart or (lambda _current, _next: True)
        self.state_queued = state_queued
        self.state_driving = state_driving

    def queue_step(self, owner_id: int, current_node: int) -> None:
        if self.route_service.has_no_route():
            self.route_service.select_new_destination(current_node)
            return

        if self.route_service.route_is_complete():
            self.runtime.path = []
            return

        current_node, next_node = self.route_service.current_and_next_node(current_node)
        if self.route_service.edge_is_missing(current_node, next_node):
            self.route_service.plan_path(current_node)
            return

        if not self.can_depart(current_node, next_node):
            return

        self.start_drive(current_node=current_node, next_node=next_node)

    def drive_step(self) -> None:
        self.runtime.travel_timer -= 1
        if self.runtime.travel_timer <= 0:
            self.finalize_arrival()

    def start_drive(self, current_node: int, next_node: int) -> None:
        self.runtime.travel_timer = self.compute_travel_timer(next_node)
        self.runtime.edge_total_timer = self.runtime.travel_timer
        self.runtime.next_node_buffer = next_node

        self.release_lock(current_node)
        self.runtime.status = self.state_driving

        self.publisher.publish(
            "DEPARTING",
            {
                "from": current_node,
                "to": next_node,
                "duration": self.runtime.travel_timer,
            },
            self.runtime.lamport_clock,
        )

    def finalize_arrival(self) -> None:
        self.move_agent_to_node(self.runtime.next_node_buffer)
        self.runtime.path.pop(0)
        self.runtime.status = self.state_queued
        self.runtime.edge_total_timer = 0
        self.runtime.sensor_registered = False
        self.runtime.sensor_target_intersection = None
        self.publisher.publish("ARRIVED_NODE", {"node": self.get_current_node()}, self.runtime.lamport_clock)

from __future__ import annotations

import networkx as nx

from acts.agents.vehicle_logic.event_bus_publisher import EventBusPublisher
from acts.agents.vehicle_logic.route_planner import ConstrainedRoutePlanner
from acts.agents.vehicle_logic.vehicle_state import VehicleRuntimeState


class RouteService:
    def __init__(
        self,
        graph,
        random_source,
        planner: ConstrainedRoutePlanner,
        runtime: VehicleRuntimeState,
        publisher: EventBusPublisher,
    ):
        self.graph = graph
        self.random = random_source
        self.planner = planner
        self.runtime = runtime
        self.publisher = publisher

    def has_no_route(self) -> bool:
        return not self.runtime.path

    def route_is_complete(self) -> bool:
        return len(self.runtime.path) <= 1

    def current_and_next_node(self, current_node: int) -> tuple[int, int]:
        return current_node, self.runtime.path[1]

    def edge_is_missing(self, current_node: int, next_node: int) -> bool:
        return not self.graph.has_edge(current_node, next_node)

    def destination_candidates(self, current_node: int) -> list[int]:
        return [node for node in self.graph.nodes() if node != current_node]

    def select_new_destination(self, current_node: int) -> None:
        candidates = self.destination_candidates(current_node)
        if not candidates:
            return
        self.runtime.destination = self.random.choice(candidates)
        self.plan_path(current_node)

    def plan_path(self, current_node: int) -> None:
        if self.runtime.destination is None:
            self.runtime.path = []
            return

        try:
            self.runtime.path = self.planner.find_path(current_node, self.runtime.destination)
            self.publisher.publish(
                "PLANNING_ASTAR",
                {
                    "dest": self.runtime.destination,
                    "steps": len(self.runtime.path),
                },
                self.runtime.lamport_clock,
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            self.runtime.path = []

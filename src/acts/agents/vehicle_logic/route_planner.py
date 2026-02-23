from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Callable, Optional

import networkx as nx


PlannerState = tuple[int, Optional[int], Optional[int], int]
TransitionDecision = tuple[bool, Optional[int], Optional[int], int]


@dataclass(frozen=True)
class PlannerRules:
    no_internal_steps: int = 0
    one_internal_step: int = 1
    max_internal_steps: int = 1
    start_cost: float = 0.0
    default_edge_weight: float = 1.0


class ConstrainedRoutePlanner:
    def __init__(
        self,
        graph: nx.DiGraph,
        heuristic: Callable[[int, int], float],
        rules: PlannerRules | None = None,
    ):
        self.graph = graph
        self.heuristic = heuristic
        self.rules = rules or PlannerRules()

    def _node_intersection(self, node_id: int) -> int:
        return self.graph.nodes[node_id].get("intersection", node_id)

    def _is_pass_through_intersection(self, intersection_id: int) -> bool:
        intersections = self.graph.graph.get("intersections", {})
        meta = intersections.get(intersection_id, {})
        return bool(meta.get("is_pass_through", False))

    def _is_transition_allowed(
        self,
        current_node: int,
        next_node: int,
        active_intersection: Optional[int],
        entry_from_intersection: Optional[int],
        internal_steps: int,
    ) -> TransitionDecision:
        current_intersection = self._node_intersection(current_node)
        next_intersection = self._node_intersection(next_node)

        if active_intersection is None:
            if current_intersection != next_intersection:
                return True, next_intersection, current_intersection, self.rules.no_internal_steps
            return True, current_intersection, current_intersection, self.rules.one_internal_step

        if current_intersection != active_intersection:
            if current_intersection != next_intersection:
                return True, next_intersection, current_intersection, self.rules.no_internal_steps
            return True, current_intersection, current_intersection, self.rules.one_internal_step

        if next_intersection == active_intersection:
            if internal_steps >= self.rules.max_internal_steps:
                return False, active_intersection, entry_from_intersection, internal_steps
            return True, active_intersection, entry_from_intersection, internal_steps + self.rules.one_internal_step

        if entry_from_intersection is not None and next_intersection == entry_from_intersection:
            return False, active_intersection, entry_from_intersection, internal_steps

        if not self._is_pass_through_intersection(active_intersection) and internal_steps != self.rules.one_internal_step:
            return False, active_intersection, entry_from_intersection, internal_steps

        return True, next_intersection, current_intersection, self.rules.no_internal_steps

    def _reconstruct_route(
        self,
        final_state: PlannerState,
        came_from: dict[PlannerState, PlannerState],
    ) -> list[int]:
        route_states = [final_state]
        while route_states[-1] in came_from:
            route_states.append(came_from[route_states[-1]])
        route_states.reverse()
        return [state[0] for state in route_states]

    def find_path(self, source: int, target: int) -> list[int]:
        start_state: PlannerState = (source, None, None, self.rules.no_internal_steps)
        open_heap: list[tuple[float, float, PlannerState]] = []
        heapq.heappush(open_heap, (self.heuristic(source, target), self.rules.start_cost, start_state))

        came_from: dict[PlannerState, PlannerState] = {}
        g_score: dict[PlannerState, float] = {start_state: self.rules.start_cost}

        while open_heap:
            _, current_cost, state = heapq.heappop(open_heap)
            current_node, active_intersection, entry_from_intersection, internal_steps = state

            if current_cost > g_score.get(state, float("inf")):
                continue

            if current_node == target:
                return self._reconstruct_route(state, came_from)

            for neighbor in self.graph.successors(current_node):
                allowed, next_active, next_entry_from, next_internal_steps = self._is_transition_allowed(
                    current_node=current_node,
                    next_node=neighbor,
                    active_intersection=active_intersection,
                    entry_from_intersection=entry_from_intersection,
                    internal_steps=internal_steps,
                )
                if not allowed:
                    continue

                edge_data = self.graph.get_edge_data(current_node, neighbor) or {}
                edge_cost = float(edge_data.get("weight", self.rules.default_edge_weight))
                tentative_cost = current_cost + edge_cost
                next_state: PlannerState = (neighbor, next_active, next_entry_from, next_internal_steps)

                if tentative_cost >= g_score.get(next_state, float("inf")):
                    continue

                came_from[next_state] = state
                g_score[next_state] = tentative_cost
                estimated_total = tentative_cost + self.heuristic(neighbor, target)
                heapq.heappush(open_heap, (estimated_total, tentative_cost, next_state))

        raise nx.NetworkXNoPath

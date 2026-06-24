from __future__ import annotations

import heapq
from typing import Callable, Optional

import networkx as nx


# PlannerState indices:
#   [0] current_node: nodo corrente nel grafo
#   [1] active_intersection: intersezione logica in cui ci si trova (None all'inizio)
#   [2] entry_from_intersection: intersezione da cui si e' entrati in active_intersection
#   [3] internal_steps: passi consecutivi fatti all'interno della stessa intersezione
#   [4] last_intersection: ultima intersezione appena lasciata (usata per evitare ritorni immediati)
PlannerState = tuple[int, Optional[int], Optional[int], int, Optional[int]]

# TransitionDecision indices:
#   [0] allowed: True se la transizione e' consentita
#   [1] next_active_intersection: nuovo active_intersection dopo la transizione
#   [2] next_entry_from_intersection: nuovo entry_from_intersection dopo la transizione
#   [3] next_internal_steps: nuovo contatore di passi interni
#   [4] next_last_intersection: nuovo valore di last_intersection
TransitionDecision = tuple[bool, Optional[int], Optional[int], int, Optional[int]]

NO_INTERNAL_STEPS = 0
ONE_INTERNAL_STEP = 1
MAX_INTERNAL_STEPS = 1
START_COST = 0.0
DEFAULT_EDGE_WEIGHT = 1.0


def _node_intersection(graph: nx.DiGraph, node_id: int) -> int:
    return graph.nodes[node_id].get("intersection", node_id)


def _is_pass_through_intersection(graph: nx.DiGraph, intersection_id: int) -> bool:
    intersections = graph.graph.get("intersections", {})
    meta = intersections.get(intersection_id, {})
    return bool(meta.get("is_pass_through", False))


def _is_transition_allowed(
    graph: nx.DiGraph,
    current_node: int,
    next_node: int,
    active_intersection: Optional[int],
    entry_from_intersection: Optional[int],
    internal_steps: int,
    last_intersection: Optional[int],
    no_internal_steps: int,
    one_internal_step: int,
    max_internal_steps: int,
) -> TransitionDecision:
    current_intersection = _node_intersection(graph, current_node)
    next_intersection = _node_intersection(graph, next_node)

    if last_intersection is not None and next_intersection == last_intersection:
        if current_intersection != last_intersection:
            return False, active_intersection, entry_from_intersection, internal_steps, last_intersection

    if active_intersection is None:
        if current_intersection != next_intersection:
            return True, next_intersection, current_intersection, no_internal_steps, last_intersection
        return True, current_intersection, current_intersection, one_internal_step, last_intersection

    if current_intersection != active_intersection:
        if current_intersection != next_intersection:
            return True, next_intersection, current_intersection, no_internal_steps, last_intersection
        return True, current_intersection, current_intersection, one_internal_step, last_intersection

    if next_intersection == active_intersection:
        if internal_steps >= max_internal_steps:
            return False, active_intersection, entry_from_intersection, internal_steps, last_intersection
        return True, active_intersection, entry_from_intersection, internal_steps + one_internal_step, last_intersection

    if entry_from_intersection is not None and next_intersection == entry_from_intersection:
        return False, active_intersection, entry_from_intersection, internal_steps, last_intersection

    if not _is_pass_through_intersection(graph, active_intersection) and internal_steps > one_internal_step:
        return False, active_intersection, entry_from_intersection, internal_steps, last_intersection

    next_last_intersection = last_intersection
    if internal_steps == one_internal_step:
        next_last_intersection = active_intersection

    return True, next_intersection, current_intersection, no_internal_steps, next_last_intersection


def _reconstruct_route(
    final_state: PlannerState,
    came_from: dict[PlannerState, PlannerState],
) -> list[int]:
    route_states = [final_state]
    while route_states[-1] in came_from:
        route_states.append(came_from[route_states[-1]])
    route_states.reverse()
    return [state[0] for state in route_states]


def destination_candidates(graph: nx.DiGraph, current_node: int) -> list[int]:
    return [node for node in graph.nodes() if node != current_node]


def select_destination(graph: nx.DiGraph, random_source, current_node: int) -> Optional[int]:
    candidates = destination_candidates(graph, current_node)
    if not candidates:
        return None
    return random_source.choice(candidates)


def heuristic_euclidean(graph: nx.DiGraph, source_node: int, target_node: int) -> float:
    source_pos = graph.nodes[source_node].get("pos", (0.0, 0.0))
    target_pos = graph.nodes[target_node].get("pos", (0.0, 0.0))
    dx = source_pos[0] - target_pos[0]
    dy = source_pos[1] - target_pos[1]
    return (dx * dx + dy * dy) ** 0.5


def find_constrained_path(
    graph: nx.DiGraph,
    heuristic: Callable[[int, int], float],
    source: int,
    target: int,
) -> list[int]:
    start_state: PlannerState = (source, None, None, NO_INTERNAL_STEPS, None)
    open_heap: list[tuple[float, float, PlannerState]] = []
    heapq.heappush(open_heap, (heuristic(source, target), START_COST, start_state))

    came_from: dict[PlannerState, PlannerState] = {}
    g_score: dict[PlannerState, float] = {start_state: START_COST}

    while open_heap:
        _, current_cost, state = heapq.heappop(open_heap)
        current_node, active_intersection, entry_from_intersection, internal_steps, last_intersection = state

        if current_cost > g_score.get(state, float("inf")):
            continue

        if current_node == target:
            return _reconstruct_route(state, came_from)

        for neighbor in graph.successors(current_node):
            (
                allowed,
                next_active,
                next_entry_from,
                next_internal_steps,
                next_last_intersection,
            ) = _is_transition_allowed(
                graph=graph,
                current_node=current_node,
                next_node=neighbor,
                active_intersection=active_intersection,
                entry_from_intersection=entry_from_intersection,
                internal_steps=internal_steps,
                last_intersection=last_intersection,
                no_internal_steps=NO_INTERNAL_STEPS,
                one_internal_step=ONE_INTERNAL_STEP,
                max_internal_steps=MAX_INTERNAL_STEPS,
            )
            if not allowed:
                continue

            edge_data = graph.get_edge_data(current_node, neighbor) or {}
            edge_cost = float(edge_data.get("weight", DEFAULT_EDGE_WEIGHT))
            tentative_cost = current_cost + edge_cost
            next_state: PlannerState = (
                neighbor,
                next_active,
                next_entry_from,
                next_internal_steps,
                next_last_intersection,
            )

            if tentative_cost >= g_score.get(next_state, float("inf")):
                continue

            came_from[next_state] = state
            g_score[next_state] = tentative_cost
            estimated_total = tentative_cost + heuristic(neighbor, target)
            heapq.heappush(open_heap, (estimated_total, tentative_cost, next_state))

    raise nx.NetworkXNoPath
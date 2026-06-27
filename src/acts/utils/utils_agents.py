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

import heapq
import networkx as nx
import math

def heuristic_euclidean(G: nx.DiGraph, current: int, goal: int) -> float:
    """Calcola la distanza euclidea tra due nodi nel grafo espanso."""
    pos_curr = G.nodes[current].get("pos", (0.0, 0.0))
    pos_goal = G.nodes[goal].get("pos", (0.0, 0.0))
    return math.hypot(pos_curr[0] - pos_goal[0], pos_curr[1] - pos_goal[1])

def find_constrained_path(G: nx.DiGraph, heuristic_fn, start: int, goal: int) -> list[int]:
    """
    Trova il percorso più breve usando A* con vincolo di non-consecutività 
    dei passi interni all'incrocio.
    """
    if start not in G or goal not in G:
        raise nx.NodeNotFound("Nodo di partenza o destinazione non trovato.")
    
    if start == goal:
        return [start]

    # Coda di priorità: (f_score, g_score, current_node, last_was_internal, path)
    # Lo stato è definito dalla coppia (node, last_was_internal)
    # last_was_internal: True se l'ultimo arco percorso era interno allo stesso incrocio
    queue = [(heuristic_fn(start, goal), 0.0, start, False, [start])]
    
    # Dizionario delle distanze minime per stato: (node, last_was_internal) -> g_score
    # Questo è fondamentale per permettere di ri-visitare lo stesso nodo con uno stato diverso
    shortest_paths: dict[tuple[int, bool], float] = {(start, False): 0.0}

    while queue:
        f_score, g_score, current, last_was_internal, path = heapq.heappop(queue)

        if current == goal:
            return path

        # Ottimizzazione: se abbiamo trovato un percorso migliore per questo stato, ignoriamo
        if g_score > shortest_paths.get((current, last_was_internal), float('inf')):
            continue

        curr_int = G.nodes[current].get("intersection")

        for neighbor in G.successors(current):
            neigh_int = G.nodes[neighbor].get("intersection")
            
            # Un arco è interno se entrambi i nodi appartengono allo stesso incrocio
            # e non sono nodi speciali (Gate)
            is_internal = (
                curr_int is not None and 
                neigh_int is not None and 
                curr_int == neigh_int and
                not G.nodes[current].get("is_gate", False) and
                not G.nodes[neighbor].get("is_gate", False)
            )

            # --- IL VINCOLO IMPERATIVO ---
            if last_was_internal and is_internal:
                continue

            # Calcolo costo
            weight = G.edges[current, neighbor].get("weight", 1.0)
            next_g_score = g_score + weight
            
            state_key = (neighbor, is_internal)

            # Se lo stato non è stato visitato o abbiamo trovato un cammino più breve
            if next_g_score < shortest_paths.get(state_key, float('inf')):
                shortest_paths[state_key] = next_g_score
                f_score_new = next_g_score + heuristic_fn(neighbor, goal)
                
                heapq.heappush(
                    queue, 
                    (f_score_new, next_g_score, neighbor, is_internal, path + [neighbor])
                )

    # Se arriviamo qui, non esiste un percorso che rispetti il vincolo
    raise nx.NetworkXNoPath(f"Nessun percorso valido tra {start} e {goal} con i vincoli imposti.")

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




def _is_vehicle_agent(agent):
    from acts.agents.vehicle import VehicleAgent
    return isinstance(agent, VehicleAgent) or agent.__class__.__name__ == "VehicleAgent"
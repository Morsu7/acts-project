from __future__ import annotations

from typing import Optional

import networkx as nx

from acts.utils.utils_agents import (
    find_constrained_path,
    heuristic_euclidean,
    select_destination,
)
from acts.agents.state import VehicleRuntimeState
from acts.agents.publishing_agent import PublishingAgent

class VehicleAgent(PublishingAgent):
    LOCK_TTL_SECONDS = 5
    STATE_QUEUED = "QUEUED"
    STATE_DRIVING = "DRIVING"

    def __init__(self, unique_id, model, replan_destination=True):
        super().__init__(unique_id, model, "traffic_channel")
        self.runtime = VehicleRuntimeState(status=self.STATE_QUEUED)
        self.replan_destination = replan_destination

    # Public API: used outside VehicleAgent (visualization, model).
    @property
    def path(self) -> list[int]:
        return self.runtime.path

    @property
    def destination(self) -> Optional[int]:
        return self.runtime.destination

    @property
    def state(self) -> str:
        return self.runtime.status

    @property
    def travel_timer(self) -> int:
        return self.runtime.travel_timer

    @property
    def edge_total_timer(self) -> int:
        return self.runtime.edge_total_timer

    @property
    def edge_completion_ratio(self) -> float:
        """Returns the vehicle's position along the current edge as a ratio from 0.0 to 1.0."""
        if self.state != self.STATE_DRIVING or self.edge_total_timer <= 0:
            return 0.0
        
        # Ticks spent driving on this edge
        ticks_driven = self.edge_total_timer - self.travel_timer
        
        # Return progression ratio clamped between 0 and 1
        return min(1.0, max(0.0, ticks_driven / self.edge_total_timer))

    # Public API: called by Mesa scheduler.
    def step(self):
        # Aggiornamento del veicolo per un singolo tick.
        self.runtime.lamport_clock += 1
        
        if self.state == self.STATE_QUEUED:
            # Eliminato il parametro current_node, usiamo direttamente self.pos internamente
            self._queue_step()
            
        elif self.state == self.STATE_DRIVING:
            self.runtime.travel_timer -= 1
            if self.runtime.travel_timer <= 0:
                # --- FIX: Safe Edge-to-Node Arrival Transition ---
                # 1. Unregister this vehicle from the current NetworkX edge list
                from_node, to_node = self.pos
                if "vehicles" in self.model.G[from_node][to_node]:
                    if self in self.model.G[from_node][to_node]["vehicles"]:
                        self.model.G[from_node][to_node]["vehicles"].remove(self)
                
                # 2. Safely land the agent onto its physical node back inside Mesa
                next_node = self.runtime.next_node_buffer
                self.model.grid.place_agent(self, next_node)
                # --------------------------------------------------

                self.runtime.path.pop(0)
                self.runtime.status = self.STATE_QUEUED
                self.runtime.edge_total_timer = 0
                self.runtime.sensor_registered = False
                self.runtime.sensor_target_intersection = None
                self.publish_event("ARRIVED_NODE", {"node": self.pos}, self.runtime.lamport_clock)

    def _plan_route(self) -> None:
        try:
            path = find_constrained_path(
                self.model.G,
                lambda current, goal: heuristic_euclidean(self.model.G, current, goal),
                self.pos,
                self.runtime.destination,
            )
            self.runtime.path = path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # Se fallisce, significa che la destinazione è irraggiungibile 
            # con il vincolo. Riprova a scegliere una destinazione diversa.
            self.runtime.destination = None 
            self.runtime.path = []

    def _queue_step(self) -> None:
        if self.runtime.destination == self.pos and self.replan_destination:
            # Already at destination: clear and pick a new one.
            self.runtime.destination = None
            self.runtime.path = []

        if not self.runtime.path:
            if self.runtime.destination is None:
                self.runtime.destination = select_destination(self.model.G, self.random, self.pos)
            if self.runtime.destination is None:
                return
            self._plan_route()
            return
        
        if len(self.runtime.path) <= 1:
            self.runtime.path = []
            return

        next_node = self.runtime.path[1]
        if not self.model.G.has_edge(self.pos, next_node):
            self._plan_route()
            return

        edge_data = self.model.G.get_edge_data(self.pos, next_node) or {}
        edge_state = edge_data.get("tl_state")
        if edge_state is not None and str(edge_state).upper() != "GREEN":
            return

        # --- UPDATED MOVEMENT MATH: Physical parameters determine timing ---
        # Internal edges pull 15.0m / 5.0m/tick (= 3 ticks)
        # External roads pull real scaled meters / tier-specific velocity
        length = edge_data.get("length", 15.0)
        max_speed = edge_data.get("max_speed", 5.0)
        
        effective_timer = max(1, round(length / max_speed))
        
        self.runtime.travel_timer = effective_timer
        self.runtime.edge_total_timer = self.runtime.travel_timer
        self.runtime.next_node_buffer = next_node
        # -------------------------------------------------------------------

        self.runtime.status = self.STATE_DRIVING
        
        if "vehicles" not in edge_data:
            self.model.G[self.pos][next_node]["vehicles"] = []
        self.model.G[self.pos][next_node]["vehicles"].append(self)
        
        start_node = self.pos
        self.model.grid.remove_agent(self)
        self.pos = (start_node, next_node) 
        # -------------------------------

        self.publish_event(
            "DEPARTING",
            {
                "from": start_node,
                "to": next_node,
                "duration": self.runtime.travel_timer,
            },
            self.runtime.lamport_clock,
        )
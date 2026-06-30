from __future__ import annotations

from typing import Optional

import networkx as nx

from acts.utils.utils_agents import (
    find_constrained_path,
    heuristic_euclidean,
    select_destination,
)
from acts.agents.state.vehicle_state import VehicleRuntimeState

from acts.agents.publishing_agent import PublishingAgent

class VehicleAgent(PublishingAgent):
    LOCK_TTL_SECONDS = 5
    TRAVEL_TIME_SCALE = 60
    MIN_TRAVEL_TICKS = 5
    STATE_QUEUED = "QUEUED"
    STATE_DRIVING = "DRIVING"

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model, "traffic_channel")
        self.runtime = VehicleRuntimeState(status=self.STATE_QUEUED)

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

    @property
    def current_or_target_node(self) -> Optional[tuple[int, int]]:
        """
        Restituisce l'id dell'arco (u, v) che la macchina sta attraversando 
        o che ha intenzione di attraversare al prossimo passo. 
        Restituisce None se non ci sono archi disponibili o pianificati.
        """
        # Se il veicolo sta guidando, l'arco è definito tra la posizione attuale 
        # (che Mesa aggiorna solo all'arrivo) e il nodo memorizzato nel buffer.
        if self.state == self.STATE_DRIVING and self.runtime.next_node_buffer is not None:
            return (self.pos, self.runtime.next_node_buffer)
        
        # Se il veicolo è in coda (QUEUED) e ha un percorso pianificato valido,
        # l'arco target è quello tra il nodo attuale e il prossimo nel path.
        if self.state == self.STATE_QUEUED and len(self.runtime.path) > 1:
            return (self.pos, self.runtime.path[1])
            
        return None

    # Public API: called by Mesa scheduler.
    def step(self):
        # Aggiornamento del veicolo per un singolo tick.
        self.runtime.lamport_clock += 1
        if self.state == self.STATE_QUEUED:
            self._queue_step(current_node=self.pos)
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

    def _plan_from(self, node_id: int) -> None:
        try:
            path = find_constrained_path(
                self.model.G,
                lambda current, goal: heuristic_euclidean(self.model.G, current, goal),
                node_id,
                self.runtime.destination,
            )
            self.runtime.path = path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # Se fallisce, significa che la destinazione è irraggiungibile 
            # con il vincolo. Riprova a scegliere una destinazione diversa.
            self.runtime.destination = None 
            self.runtime.path = []

    def _queue_step(self, current_node: int) -> None:
        if self.runtime.destination == current_node:
            # Already at destination: clear and pick a new one.
            self.runtime.destination = None
            self.runtime.path = []

        if not self.runtime.path:
            if self.runtime.destination is None:
                self.runtime.destination = select_destination(self.model.G, self.random, current_node)
                #print(f"Vehicle {self.unique_id} selected new destination: {self.runtime.destination}")
            if self.runtime.destination is None:
                return
            self._plan_from(current_node)
            return
        
        if len(self.runtime.path) <= 1:
            self.runtime.path = []
            return

        next_node = self.runtime.path[1]
        if not self.model.G.has_edge(current_node, next_node):
            self._plan_from(current_node)
            return

        edge_data = self.model.G.get_edge_data(current_node, next_node) or {}
        edge_state = edge_data.get("tl_state")
        if edge_state is not None and str(edge_state).upper() != "GREEN":
            return

        # --- TIMER DIAGNOSTIC PRINTING ---
        dist = edge_data.get("weight", 0.5)
        expected_timer = int(dist * self.TRAVEL_TIME_SCALE)
        effective_timer = max(expected_timer, self.MIN_TRAVEL_TICKS)
        
        print(
            f"[Car {self.unique_id}] Edge: {current_node} -> {next_node} | "
            f"Weight: {dist:.2f} | "
            f"Expected Ticks: {expected_timer} | "
            f"Effective Ticks (Applied): {effective_timer}"
            f"{' (Capped by MIN_TRAVEL_TICKS)' if expected_timer < self.MIN_TRAVEL_TICKS else ''}"
        )
        
        self.runtime.travel_timer = effective_timer
        self.runtime.edge_total_timer = self.runtime.travel_timer
        self.runtime.next_node_buffer = next_node
        # ---------------------------------

        # Rilascia il lock del nodo corrente prima di partire.
        key = f"lock_node_{current_node}"
        #release_lock_if_owner(self.redis_client, key=key, owner_id=self.unique_id)
        self.runtime.status = self.STATE_DRIVING

        # --- FIX: Safe Edge Tracking ---
        # 1. Remove agent from the old node room in Mesa's space
        self.model.grid.remove_agent(self)
        
        # 2. Track the agent inside the networkx edge data dictionary
        if "vehicles" not in edge_data:
            self.model.G[current_node][next_node]["vehicles"] = []
        self.model.G[current_node][next_node]["vehicles"].append(self)
        
        # 3. Keep a logical reference on the agent itself for its position
        self.pos = (current_node, next_node) 
        # -------------------------------

        self.publish_event(
            "DEPARTING",
            {
                "from": current_node,
                "to": next_node,
                "duration": self.runtime.travel_timer,
            },
            self.runtime.lamport_clock,
        )
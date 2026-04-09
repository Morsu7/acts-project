from __future__ import annotations

from typing import Optional

import networkx as nx

from mesa import Agent
from acts.utils.event_bus_publisher import EventBusPublisher
from acts.utils.utils_agents import (
    find_constrained_path,
    heuristic_euclidean,
    select_destination,
)
from acts.agents.state.vehicle_state import VehicleRuntimeState

from acts.utils.redis_utils import (
    create_redis_client,
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

    # Public API: called by Mesa scheduler.
    def step(self):
        # Aggiornamento del veicolo per un singolo tick.
        self.runtime.lamport_clock += 1
        if self.state == self.STATE_QUEUED:
            self._queue_step(current_node=self.pos)
        elif self.state == self.STATE_DRIVING:
            self.runtime.travel_timer -= 1
            if self.runtime.travel_timer <= 0:
                # Arrivo: sposta il veicolo e resetta lo stato di viaggio.
                self.model.grid.move_agent(self, self.runtime.next_node_buffer)
                self.runtime.path.pop(0)
                self.runtime.status = self.STATE_QUEUED
                self.runtime.edge_total_timer = 0
                self.runtime.sensor_registered = False
                self.runtime.sensor_target_intersection = None
                self.publisher.publish("ARRIVED_NODE", {"node": self.pos}, self.runtime.lamport_clock)

    def _plan_from(self, node_id: int) -> None:
        # Calcola il percorso vincolato e pubblica l'evento di pianificazione.
        try:
            path = find_constrained_path(
                self.model.G,
                lambda current, goal: heuristic_euclidean(self.model.G, current, goal),
                node_id,
                self.runtime.destination,
            )
            self.publisher.publish(
                "PLANNING_ASTAR",
                {
                    "dest": self.runtime.destination,
                    "steps": len(path),
                },
                self.runtime.lamport_clock,
            )
            self.runtime.path = path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            self.runtime.path = []

    def _queue_step(self, current_node: int) -> None:
        if self.runtime.destination == current_node:
            # Already at destination: clear and pick a new one.
            self.runtime.destination = None
            self.runtime.path = []

        if not self.runtime.path:
            if self.runtime.destination is None:
                self.runtime.destination = select_destination(self.model.G, self.random, current_node)
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

        dist = edge_data.get("weight", 0.5)
        timer = int(dist * self.TRAVEL_TIME_SCALE)
        self.runtime.travel_timer = max(timer, self.MIN_TRAVEL_TICKS)
        self.runtime.edge_total_timer = self.runtime.travel_timer
        self.runtime.next_node_buffer = next_node

        # Rilascia il lock del nodo corrente prima di partire.
        key = f"lock_node_{current_node}"
        release_lock_if_owner(self.redis_client, key=key, owner_id=self.unique_id)
        self.runtime.status = self.STATE_DRIVING

        self.publisher.publish(
            "DEPARTING",
            {
                "from": current_node,
                "to": next_node,
                "duration": self.runtime.travel_timer,
            },
            self.runtime.lamport_clock,
        )
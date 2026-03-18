from mesa import Agent

from acts.utils.redis_utils import (
    create_redis_client,
    publish_json,
    set_json,
)

class TrafficLightAgent(Agent):
    EVENT_CHANNEL = "traffic_channel"

    def __init__(self, unique_id, model, intersection_id, controlled_nodes, intersection_meta=None):
        super().__init__(unique_id, model)
        self.intersection_id = intersection_id
        self.controlled_nodes = list(controlled_nodes)
        self.state = "GREEN"
        self.lamport_clock = 0

        self.intersection_meta = intersection_meta or {}
        self.min_green_duration = max(1, int(self.intersection_meta.get("min_green_duration", 5)))

        configured_weights = self.intersection_meta.get("priority_weights", {})
        self.waiting_cars_weight = float(configured_weights.get("waiting_cars", 1.0))
        self.waiting_seconds_weight = float(configured_weights.get("waiting_seconds", 1.0))

        self.priority_nodes = self._build_priority_nodes()
        self.priority_rank = {node_id: index for index, node_id in enumerate(self.priority_nodes)}
        self.active_green_node = self.priority_nodes[0] if self.priority_nodes else None
        self.green_elapsed = 0
        self.waiting_seconds_by_node = {node_id: 0 for node_id in self.priority_nodes}
        
        self.incoming_external_by_node = {}

        for target_node in self.controlled_nodes:
            self.model.G.nodes[target_node]["intersection_owner"] = self.intersection_id
            incoming_external = []
            for source_node in model.G.predecessors(target_node):
                source_intersection = model.G.nodes[source_node].get("intersection", source_node)
                if source_intersection == self.intersection_id:
                    continue
                incoming_external.append(source_node)
            self.incoming_external_by_node[target_node] = sorted(incoming_external)

        self.redis = create_redis_client()
        if self.redis:
            self.redis.delete(f"sensor_{self.intersection_id}")
        self.update_redis()

    def step(self):
        self.lamport_clock += 1
        if self.active_green_node is None:
            return

        waiting_counts = self._collect_waiting_counts()
        self._update_waiting_seconds(waiting_counts)

        self.green_elapsed += 1
        if self.green_elapsed >= self.min_green_duration:
            next_green_node = self._select_highest_priority_node(waiting_counts)
            if next_green_node is not None and next_green_node != self.active_green_node:
                self.active_green_node = next_green_node
                self.green_elapsed = 0
                self.waiting_seconds_by_node[self.active_green_node] = 0

        self.update_redis()

    def _build_priority_nodes(self):
        configured_priority = self.intersection_meta.get("priority_nodes", [])
        controlled_set = set(self.controlled_nodes)

        ordered = []
        for node_id in configured_priority:
            if node_id in controlled_set and node_id not in ordered:
                ordered.append(node_id)

        for node_id in sorted(self.controlled_nodes):
            if node_id not in ordered:
                ordered.append(node_id)

        return ordered

    def _collect_waiting_counts(self):
        counts_by_target_node = {node_id: 0 for node_id in self.controlled_nodes}
        controlled_set = set(self.controlled_nodes)

        for agent in self.model.schedule.agents:
            if agent.__class__.__name__ != "VehicleAgent":
                continue

            if getattr(agent, "state", None) != "QUEUED":
                continue

            path = getattr(agent, "path", [])
            if not path or len(path) <= 1:
                continue

            current_node = getattr(agent, "pos", None)
            next_node = path[1]

            if current_node is None or not self.model.G.has_edge(current_node, next_node):
                continue

            if current_node not in controlled_set:
                continue

            counts_by_target_node[current_node] = counts_by_target_node.get(current_node, 0) + 1

        return counts_by_target_node

    def _update_waiting_seconds(self, waiting_counts):
        for node_id in self.priority_nodes:
            if node_id == self.active_green_node:
                self.waiting_seconds_by_node[node_id] = 0
                continue

            queue_count = int(waiting_counts.get(node_id, 0))
            if queue_count <= 0:
                self.waiting_seconds_by_node[node_id] = 0
                continue

            self.waiting_seconds_by_node[node_id] = self.waiting_seconds_by_node.get(node_id, 0) + queue_count

    def _compute_priority_score(self, node_id, waiting_counts):
        queue_count = int(waiting_counts.get(node_id, 0))
        waiting_seconds = self.waiting_seconds_by_node.get(node_id, 0)
        return (self.waiting_cars_weight * queue_count) + (self.waiting_seconds_weight * waiting_seconds)

    def _compute_priority_components(self, node_id, waiting_counts):
        queue_count = int(waiting_counts.get(node_id, 0))
        waiting_seconds = self.waiting_seconds_by_node.get(node_id, 0)
        waiting_cars_score = self.waiting_cars_weight * queue_count
        waiting_time_score = self.waiting_seconds_weight * waiting_seconds
        total_score = waiting_cars_score + waiting_time_score
        return queue_count, waiting_seconds, waiting_cars_score, waiting_time_score, total_score

    def _select_highest_priority_node(self, waiting_counts):
        if not self.priority_nodes:
            return None

        current_green = self.active_green_node
        if current_green not in self.priority_nodes:
            return self.priority_nodes[0]

        candidate_nodes = [node_id for node_id in self.priority_nodes if node_id != current_green]
        if not candidate_nodes:
            return current_green

        best_candidate = candidate_nodes[0]
        best_score = self._compute_priority_score(best_candidate, waiting_counts)

        for node_id in candidate_nodes[1:]:
            score = self._compute_priority_score(node_id, waiting_counts)
            if score > best_score:
                best_candidate = node_id
                best_score = score
                continue

            if score == best_score and self.priority_rank[node_id] < self.priority_rank[best_candidate]:
                best_candidate = node_id

        if best_score <= 0:
            current_index = self.priority_rank[current_green]
            next_index = (current_index + 1) % len(self.priority_nodes)
            return self.priority_nodes[next_index]

        return best_candidate

    def update_redis(self):
        waiting_counts = self._collect_waiting_counts()
        allowed_nodes = []
        if self.active_green_node is not None:
            allowed_nodes = self.incoming_external_by_node.get(self.active_green_node, [])

        component_scores = {}
        priority_scores = {}

        for node_id in self.controlled_nodes:
            (
                queue_count,
                waiting_seconds,
                waiting_cars_score,
                waiting_time_score,
                priority_score,
            ) = self._compute_priority_components(
                node_id,
                waiting_counts,
            )
            node_state = "GREEN" if node_id == self.active_green_node else "RED"
            self.model.G.nodes[node_id]["tl_state"] = node_state
            self.model.G.nodes[node_id]["tl_waiting_cars_raw"] = int(queue_count)
            self.model.G.nodes[node_id]["tl_waiting_seconds_raw"] = int(waiting_seconds)
            self.model.G.nodes[node_id]["tl_waiting_cars_score"] = float(waiting_cars_score)
            self.model.G.nodes[node_id]["tl_waiting_time_score"] = float(waiting_time_score)
            self.model.G.nodes[node_id]["tl_priority_score"] = float(priority_score)

            component_scores[node_id] = {
                "waiting_cars_raw": int(queue_count),
                "waiting_seconds_raw": int(waiting_seconds),
                "waiting_cars": float(waiting_cars_score),
                "waiting_time": float(waiting_time_score),
            }
            priority_scores[node_id] = float(priority_score)

        set_json(self.redis, f"tl_{self.intersection_id}_allowed", allowed_nodes)
        state_payload = {
            "intersection": self.intersection_id,
            "traffic_light_id": self.unique_id,
            "clock": self.lamport_clock,
            "state": self.state,
            "active_green_node": self.active_green_node,
            "priority_nodes": self.priority_nodes,
            "priority_weights": {
                "waiting_cars": self.waiting_cars_weight,
                "waiting_seconds": self.waiting_seconds_weight,
            },
            "min_green_duration": self.min_green_duration,
            "green_elapsed": self.green_elapsed,
            "waiting_seconds_by_node": self.waiting_seconds_by_node,
            "component_scores": component_scores,
            "priority_scores": priority_scores,
            "allowed_from": allowed_nodes,
            "controlled_nodes": self.controlled_nodes,
        }
        set_json(self.redis, f"tl_{self.intersection_id}_state", state_payload)

        msg = {
            "agent_id": f"TL_{self.intersection_id}",
            "clock": self.lamport_clock,
            "event": "PHASE_CHANGE",
            "data": {
                "intersection": self.intersection_id,
                "green_node": self.active_green_node,
                "allowed_from": allowed_nodes,
            },
        }
        publish_json(self.redis, self.EVENT_CHANNEL, msg)
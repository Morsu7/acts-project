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

        self.controlled_edges = self._build_controlled_edges()
        self.edge_groups = self._build_edge_groups()
        self.edge_to_group = {
            edge: group_id
            for group_id, grouped_edges in self.edge_groups.items()
            for edge in grouped_edges
        }
        self.priority_groups = self._build_priority_groups()
        self.priority_rank = {group_id: index for index, group_id in enumerate(self.priority_groups)}
        self.active_green_group = self.priority_groups[0] if self.priority_groups else None
        self.green_elapsed = 0
        self.waiting_seconds_by_edge = {edge: 0 for edge in self.controlled_edges}

        for target_node in self.controlled_nodes:
            self.model.G.nodes[target_node]["intersection_owner"] = self.intersection_id

        self.redis = create_redis_client()
        if self.redis:
            self.redis.delete(f"sensor_{self.intersection_id}")
        self.update_redis()

    def step(self):
        self.lamport_clock += 1
        if self.active_green_group is None:
            return

        waiting_counts = self._collect_waiting_counts()
        self._update_waiting_seconds(waiting_counts)

        self.green_elapsed += 1
        if self.green_elapsed >= self.min_green_duration:
            next_green_group = self._select_highest_priority_group(waiting_counts)
            if next_green_group is not None and next_green_group != self.active_green_group:
                self.active_green_group = next_green_group
                self.green_elapsed = 0
                for edge in self.edge_groups.get(self.active_green_group, []):
                    self.waiting_seconds_by_edge[edge] = 0

        self.update_redis()

    def _build_controlled_edges(self):
        controlled_set = set(self.controlled_nodes)
        edges = []

        for source_node, target_node in self.model.G.edges():
            if source_node not in controlled_set or target_node not in controlled_set:
                continue

            source_intersection = self.model.G.nodes[source_node].get("intersection", source_node)
            target_intersection = self.model.G.nodes[target_node].get("intersection", target_node)
            if source_intersection != self.intersection_id or target_intersection != self.intersection_id:
                continue

            edges.append((source_node, target_node))

        return sorted(edges)

    def _build_edge_groups(self):
        groups = {}
        configured_groups = self.intersection_meta.get("priority_edge_groups", [])
        controlled_set = set(self.controlled_edges)
        assigned_edges = set()

        if isinstance(configured_groups, list):
            for index, group in enumerate(configured_groups):
                if not isinstance(group, list):
                    continue

                parsed_group = []
                for edge in group:
                    if not isinstance(edge, (list, tuple)) or len(edge) != 2:
                        continue
                    edge_key = (int(edge[0]), int(edge[1]))
                    if edge_key in controlled_set and edge_key not in assigned_edges:
                        parsed_group.append(edge_key)
                        assigned_edges.add(edge_key)

                if parsed_group:
                    group_id = f"I{self.intersection_id}_G{index}"
                    groups[group_id] = sorted(parsed_group)

        next_group_id = len(groups)
        for edge in self.controlled_edges:
            if edge in assigned_edges:
                continue
            group_id = f"I{self.intersection_id}_G{next_group_id}"
            groups[group_id] = [edge]
            next_group_id += 1

        return groups

    def _build_priority_groups(self):
        ordered = []
        configured_nodes = self.intersection_meta.get("priority_nodes", [])

        for node_id in configured_nodes:
            try:
                candidate = int(node_id)
            except (TypeError, ValueError):
                continue
            if candidate in self.edge_groups and candidate not in ordered:
                ordered.append(candidate)

        for group_id in sorted(self.edge_groups.keys()):
            if group_id not in ordered:
                ordered.append(group_id)

        return ordered

    def _collect_waiting_counts(self):
        counts_by_edge = {edge: 0 for edge in self.controlled_edges}
        controlled_set = set(self.controlled_edges)

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

            edge = (current_node, next_node)
            if edge not in controlled_set:
                continue

            counts_by_edge[edge] = counts_by_edge.get(edge, 0) + 1

        return counts_by_edge

    def _update_waiting_seconds(self, waiting_counts):
        for edge in self.controlled_edges:
            edge_group = self.edge_to_group.get(edge)
            if edge_group == self.active_green_group:
                self.waiting_seconds_by_edge[edge] = 0
                continue

            queue_count = int(waiting_counts.get(edge, 0))
            if queue_count <= 0:
                self.waiting_seconds_by_edge[edge] = 0
                continue

            self.waiting_seconds_by_edge[edge] = self.waiting_seconds_by_edge.get(edge, 0) + queue_count

    def _compute_priority_score(self, edge, waiting_counts):
        queue_count = int(waiting_counts.get(edge, 0))
        waiting_seconds = self.waiting_seconds_by_edge.get(edge, 0)
        return (self.waiting_cars_weight * queue_count) + (self.waiting_seconds_weight * waiting_seconds)

    def _compute_priority_components(self, edge, waiting_counts):
        queue_count = int(waiting_counts.get(edge, 0))
        waiting_seconds = self.waiting_seconds_by_edge.get(edge, 0)
        waiting_cars_score = self.waiting_cars_weight * queue_count
        waiting_time_score = self.waiting_seconds_weight * waiting_seconds
        total_score = waiting_cars_score + waiting_time_score
        return queue_count, waiting_seconds, waiting_cars_score, waiting_time_score, total_score

    def _compute_group_priority_score(self, group_id, waiting_counts):
        group_score = 0.0
        for edge in self.edge_groups.get(group_id, []):
            group_score += self._compute_priority_score(edge, waiting_counts)
        return group_score

    def _select_highest_priority_group(self, waiting_counts):
        if not self.priority_groups:
            return None

        current_green = self.active_green_group
        if current_green not in self.priority_groups:
            return self.priority_groups[0]

        candidate_groups = [group_id for group_id in self.priority_groups if group_id != current_green]
        if not candidate_groups:
            return current_green

        best_candidate = candidate_groups[0]
        best_score = self._compute_group_priority_score(best_candidate, waiting_counts)

        for group_id in candidate_groups[1:]:
            score = self._compute_group_priority_score(group_id, waiting_counts)
            if score > best_score:
                best_candidate = group_id
                best_score = score
                continue

            if score == best_score and self.priority_rank[group_id] < self.priority_rank[best_candidate]:
                best_candidate = group_id

        if best_score <= 0:
            current_index = self.priority_rank[current_green]
            next_index = (current_index + 1) % len(self.priority_groups)
            return self.priority_groups[next_index]

        return best_candidate

    def _serialize_edge(self, edge):
        return f"{edge[0]}->{edge[1]}"

    def update_redis(self):
        waiting_counts = self._collect_waiting_counts()

        component_scores = {}
        priority_scores = {}
        group_scores = {}

        for group_id in self.priority_groups:
            group_scores[group_id] = float(self._compute_group_priority_score(group_id, waiting_counts))

        for edge in self.controlled_edges:
            (
                queue_count,
                waiting_seconds,
                waiting_cars_score,
                waiting_time_score,
                priority_score,
            ) = self._compute_priority_components(
                edge,
                waiting_counts,
            )
            group_id = self.edge_to_group.get(edge)
            edge_state = "GREEN" if group_id == self.active_green_group else "RED"
            source_node, target_node = edge
            self.model.G.edges[source_node, target_node]["tl_state"] = edge_state
            self.model.G.edges[source_node, target_node]["tl_constraint_group"] = group_id
            self.model.G.edges[source_node, target_node]["tl_group_score"] = float(group_scores.get(group_id, 0.0))
            self.model.G.edges[source_node, target_node]["tl_waiting_cars_raw"] = int(queue_count)
            self.model.G.edges[source_node, target_node]["tl_waiting_seconds_raw"] = int(waiting_seconds)
            self.model.G.edges[source_node, target_node]["tl_waiting_cars_score"] = float(waiting_cars_score)
            self.model.G.edges[source_node, target_node]["tl_waiting_time_score"] = float(waiting_time_score)
            self.model.G.edges[source_node, target_node]["tl_priority_score"] = float(priority_score)

            edge_key = self._serialize_edge(edge)
            component_scores[edge_key] = {
                "waiting_cars_raw": int(queue_count),
                "waiting_seconds_raw": int(waiting_seconds),
                "waiting_cars": float(waiting_cars_score),
                "waiting_time": float(waiting_time_score),
            }
            priority_scores[edge_key] = float(priority_score)

        active_green_group = str(self.active_green_group) if self.active_green_group is not None else None
        state_payload = {
            "intersection": self.intersection_id,
            "traffic_light_id": self.unique_id,
            "clock": self.lamport_clock,
            "state": self.state,
            "active_green_group": active_green_group,
            "priority_groups": [str(group_id) for group_id in self.priority_groups],
            "priority_weights": {
                "waiting_cars": self.waiting_cars_weight,
                "waiting_seconds": self.waiting_seconds_weight,
            },
            "min_green_duration": self.min_green_duration,
            "green_elapsed": self.green_elapsed,
            "waiting_seconds_by_edge": {
                self._serialize_edge(edge): int(value)
                for edge, value in self.waiting_seconds_by_edge.items()
            },
            "group_scores": {str(group_id): score for group_id, score in group_scores.items()},
            "component_scores": component_scores,
            "priority_scores": priority_scores,
            "controlled_edges": [self._serialize_edge(edge) for edge in self.controlled_edges],
            "controlled_nodes": self.controlled_nodes,
        }
        set_json(self.redis, f"tl_{self.intersection_id}_state", state_payload)

        msg = {
            "agent_id": f"TL_{self.intersection_id}",
            "clock": self.lamport_clock,
            "event": "PHASE_CHANGE",
            "data": {
                "intersection": self.intersection_id,
                "green_group": active_green_group,
            },
        }
        publish_json(self.redis, self.EVENT_CHANNEL, msg)
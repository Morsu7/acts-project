from __future__ import annotations

from typing import Any

from acts.utils.redis_utils import publish_json


class EventBusPublisher:
    def __init__(self, redis_client, channel: str, agent_id: int):
        self.redis_client = redis_client
        self.channel = channel
        self.agent_id = agent_id

    def publish(self, event: str, data: dict[str, Any], clock: int) -> None:
        message = {
            "agent_id": self.agent_id,
            "clock": clock,
            "event": event,
            "data": data,
        }
        publish_json(self.redis_client, self.channel, message)

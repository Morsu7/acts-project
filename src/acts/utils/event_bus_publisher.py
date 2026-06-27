from __future__ import annotations

from typing import Any

from acts.utils.redis_utils import publish_json
import json

class EventBusPublisher:
    def __init__(self, redis_client, channel: str, agent_id: int):
        self.redis_client = redis_client
        self.channel = channel
        self.agent_id = agent_id
        self.pubsub = self.redis_client.pubsub()
        self.pubsub.subscribe(self.channel)

    def publish(self, event: str, data: dict[str, Any], clock: int) -> None:
        message = {
            "agent_id": self.agent_id,
            "clock": clock,
            "event": event,
            "data": data,
        }
        publish_json(self.redis_client, self.channel, message)

    def read_messages(self):
        while True:
            message = self.pubsub.get_message()
            if message is None:
                break
            if message['type'] == 'message':
                yield json.loads(message['data'])
        

from acts.utils.redis_utils import create_redis_client
from acts.utils.event_bus_publisher import EventBusPublisher

from typing import Any

from mesa import Agent

class PublishingAgent(Agent):

    def __init__(self, unique_id, model, event_channel):
        if type(self) is PublishingAgent:
            raise TypeError("PublishingAgent is an abstract base class and cannot be instantiated directly")
            
        super().__init__(unique_id, model)
        self.redis_client = create_redis_client()
        self.publisher = EventBusPublisher(self.redis_client, event_channel, self.unique_id)

    def publish_event(self, event: str, data: dict[str, Any], clock: int) -> None:
        self.publisher.publish(event, data, clock)

    def get_messages(self):
        return self.publisher.read_messages()
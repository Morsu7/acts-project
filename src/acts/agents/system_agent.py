from acts.agents.publishing_agent import PublishingAgent
from acts.utils.event_bus_publisher import EventBusPublisher

class SystemAgent(PublishingAgent):

    def __init__(self, unique_id, model, event_channel):
        super().__init__(unique_id, model, event_channel)

        self.broadcast_publisher = EventBusPublisher(self.redis_client, "broadcast_channel", self.unique_id)

    def broadcast_message(self, event: str, data: dict, clock: int):
        self.broadcast_publisher.publish(event, data, clock)

    def get_broadcast_messages(self):
        return self.broadcast_publisher.read_messages()


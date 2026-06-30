from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .traffic_light_state import TrafficLightRuntimeState

def default_traffic_light():
    from .traffic_light_state import TrafficLightRuntimeState
    return TrafficLightRuntimeState()

@dataclass
class DirectionState:   # Each independent group of edges controlled by a traffic light has its own state
    runtime: 'TrafficLightRuntimeState' = field(default_factory=default_traffic_light)
    permissions: dict = field(default_factory=dict)     # Dictionary to store agents that have granted permission to turn green
    time_since_last_request: int = 0                    # Counter to track time since the last green request was sent
    time_since_last_signal: int = 0                     # Counter to track time since the last traffic signal was sent
    request_clock: int = 0                              # Lamport clock value when the last request was sent
    must_turn_yellow: bool = False                      # Flag to indicate if the light must turn yellow (before giving permission to another traffic light)

    def add_time_past(self, time: int):
        self.time_since_last_request += time
        self.time_since_last_signal += time
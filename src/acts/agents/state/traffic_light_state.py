from __future__ import annotations

from dataclasses import dataclass, field

class LightStatus:
    RED = "RED"
    GREEN = "GREEN"
    YELLOW = "YELLOW"

    def __str__(self):
        return self.value

@dataclass
class TrafficLightRuntimeState:
    queue_length : int = 0
    waiting_time : int = 0
    status : LightStatus = LightStatus.RED
    status_time : int = 0   # For how long the light has been in the current status
from __future__ import annotations

import json
import os
from typing import Any, Optional

import redis

def create_redis_client(host: Optional[str] = None, port: Optional[int] = None) -> Optional[redis.Redis]:
    redis_host = host or os.getenv("REDIS_HOST", "localhost")

    if port is not None:
        redis_port = int(port)
    else:
        redis_port = int(os.getenv("REDIS_PORT", "6379"))

    try:
        return redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    except (redis.RedisError, OSError, TypeError, ValueError):
        return None

def publish_json(redis_client: Optional[redis.Redis], channel: str, payload: Any) -> bool:
    if redis_client is None:
        return False

    try:
        redis_client.publish(channel, json.dumps(payload))
        return True
    except (redis.RedisError, TypeError, ValueError):
        return False
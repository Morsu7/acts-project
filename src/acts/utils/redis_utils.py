from __future__ import annotations

import json
from typing import Any, Optional

import redis


def create_redis_client(host: str = "localhost", port: int = 6379) -> Optional[redis.Redis]:
    try:
        return redis.Redis(host=host, port=port, decode_responses=True)
    except (redis.RedisError, OSError):
        return None


def get_json(redis_client: Optional[redis.Redis], key: str, default: Any = None) -> Any:
    if redis_client is None:
        return default

    try:
        raw_value = redis_client.get(key)
        if not raw_value:
            return default
        return json.loads(raw_value)
    except (redis.RedisError, TypeError, ValueError):
        return default


def set_json(redis_client: Optional[redis.Redis], key: str, payload: Any) -> bool:
    if redis_client is None:
        return False

    try:
        redis_client.set(key, json.dumps(payload))
        return True
    except (redis.RedisError, TypeError, ValueError):
        return False


def publish_json(redis_client: Optional[redis.Redis], channel: str, payload: Any) -> bool:
    if redis_client is None:
        return False

    try:
        redis_client.publish(channel, json.dumps(payload))
        return True
    except (redis.RedisError, TypeError, ValueError):
        return False


def hash_increment(redis_client: Optional[redis.Redis], key: str, field: str, amount: int) -> bool:
    if redis_client is None:
        return False

    try:
        redis_client.hincrby(key, field, amount)
        return True
    except (redis.RedisError, TypeError, ValueError):
        return False


def try_acquire_lock(
    redis_client: Optional[redis.Redis],
    key: str,
    owner_id: int,
    ttl_seconds: int,
) -> bool:
    if redis_client is None:
        return True

    try:
        acquired = redis_client.set(key, owner_id, nx=True, ex=ttl_seconds)
        return bool(acquired)
    except (redis.RedisError, TypeError, ValueError):
        return False


def release_lock_if_owner(redis_client: Optional[redis.Redis], key: str, owner_id: int) -> bool:
    if redis_client is None:
        return False

    try:
        current_owner = redis_client.get(key)
        if current_owner and int(current_owner) == owner_id:
            redis_client.delete(key)
            return True
        return False
    except (redis.RedisError, TypeError, ValueError):
        return False

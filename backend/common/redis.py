"""Redis client wrapper — async operations with fallback to in-memory store."""

import asyncio
import time
from typing import Any

from .config import settings

_redis = None
_fallback_store: dict[str, tuple[Any, float]] = {}  # {key: (value, expires_at)}


async def get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
            socket_keepalive=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
        await _redis.ping()
    except Exception:
        _redis = False
    return _redis


async def redis_get(key: str) -> str | None:
    r = await get_redis()
    if r:
        return await r.get(key)
    # Fallback
    entry = _fallback_store.get(key)
    if entry and entry[1] > time.monotonic():
        return entry[0]
    _fallback_store.pop(key, None)
    return None


async def redis_set(key: str, value: str, ttl: int = 300) -> None:
    r = await get_redis()
    if r:
        await r.set(key, value, ex=ttl)
        return
    _fallback_store[key] = (value, time.monotonic() + ttl)


async def redis_incr(key: str, ttl: int = 300) -> int:
    r = await get_redis()
    if r:
        val = await r.incr(key)
        await r.expire(key, ttl)
        return val
    entry = _fallback_store.get(key)
    current = (int(entry[0]) + 1) if entry else 1
    _fallback_store[key] = (str(current), time.monotonic() + ttl)
    return current


async def redis_delete(key: str) -> None:
    r = await get_redis()
    if r:
        await r.delete(key)
        return
    _fallback_store.pop(key, None)

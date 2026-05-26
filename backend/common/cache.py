"""Redis 缓存工具 — async get/set/delete + 命名空间 + 穿透保护。"""

import asyncio
import json
import time
from typing import Any

from common.redis import redis_get, redis_set, redis_delete

# ── Cache API ─────────────────────────────────────────────────────

async def cache_get(namespace: str, key: str) -> Any | None:
    """从缓存读取值，自动 JSON 反序列化。"""
    full_key = f"{namespace}{key}"
    raw = await redis_get(full_key)
    if raw is None:
        return None
    # 空值标记（穿透保护）
    if raw == "__CACHE_NULL__":
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def cache_set(namespace: str, key: str, value: Any, ttl: int = 300) -> None:
    """写入缓存，自动 JSON 序列化。"""
    full_key = f"{namespace}{key}"
    serialized = json.dumps(value, default=str) if not isinstance(value, str) else value
    await redis_set(full_key, serialized, ttl)


async def cache_set_null(namespace: str, key: str, ttl: int = 30) -> None:
    """缓存空值标记（穿透保护）。"""
    full_key = f"{namespace}{key}"
    await redis_set(full_key, "__CACHE_NULL__", ttl)


async def cache_delete(namespace: str, key: str) -> None:
    """删除单个缓存键。"""
    full_key = f"{namespace}{key}"
    await redis_delete(full_key)


async def cache_invalidate_pattern(prefix: str) -> None:
    """按前缀模糊匹配批量删除。

    Redis 不可用时静默跳过（内存存储不支持模式匹配）。
    """
    try:
        from common.redis import get_redis
        r = await get_redis()
        if r:
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor=cursor, match=f"{prefix}*", count=100)
                if keys:
                    await r.delete(*keys)
                if cursor == 0:
                    break
    except Exception:
        pass


# ── Cached decorator ──────────────────────────────────────────────

def cached(namespace: str, ttl: int = 300, null_ttl: int = 30):
    """异步函数结果缓存装饰器。

    Args:
        namespace: 缓存命名空间（如 "user_profile:"）
        ttl: 正常结果过期时间(秒)
        null_ttl: 空结果(None)过期时间(秒) — 穿透保护

    Example:
        @cached("user_profile:", ttl=3600)
        async def get_profile(user_id: str) -> dict: ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            cache_key = ":".join(str(a) for a in args)
            if kwargs:
                cache_key += ":" + ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))

            result = await cache_get(namespace, cache_key)
            if result is not None:
                return result

            try:
                result = await func(*args, **kwargs)
                if result is None:
                    await cache_set_null(namespace, cache_key, null_ttl)
                else:
                    await cache_set(namespace, cache_key, result, ttl)
                return result
            except Exception:
                raise

        return wrapper
    return decorator

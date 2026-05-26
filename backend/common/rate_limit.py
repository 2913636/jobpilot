"""API 限流中间件 — 基于 Redis 滑动窗口，按 IP 或用户 ID 限流。"""

import asyncio
import time
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from common.redis import redis_get, redis_set, redis_incr


class RateLimiter:
    """滑动窗口限流器。

    Usage:
        limiter = RateLimiter(window=60, max_requests=30)
        app.add_middleware(RateLimitMiddleware, limiter=limiter)
    """

    def __init__(self, window: int = 60, max_requests: int = 30):
        self.window = window
        self.max_requests = max_requests

    async def is_allowed(self, key: str) -> bool:
        now = int(time.time())
        window_key = f"ratelimit:{key}:{now // self.window}"
        count = await redis_incr(window_key, ttl=self.window + 1)
        return count <= self.max_requests


class RateLimitMiddleware:
    """FastAPI 中间件：按客户端 IP 限流。"""

    def __init__(self, app: FastAPI, limiter: RateLimiter):
        self.app = app
        self.limiter = limiter

    async def __call__(self, request: Request, call_next):
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.client.host if request.client else "127.0.0.1"
        )
        if request.url.path in ("/health", "/metrics"):
            return await call_next(request)

        allowed = await self.limiter.is_allowed(client_ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": True,
                    "code": "RATE_LIMITED",
                    "message": f"Rate limit exceeded. Max {self.limiter.max_requests} requests per {self.limiter.window}s.",
                },
            )
        return await call_next(request)


def setup_rate_limit(app: FastAPI, window: int = 60, max_requests: int = 100) -> None:
    limiter = RateLimiter(window=window, max_requests=max_requests)
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

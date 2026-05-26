"""幂等性中间件 — Idempotency-Key header，24h 内重复请求返回相同结果。"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from common.redis import redis_get, redis_set

IDEMPOTENCY_TTL = 86400  # 24h
HEADER = "Idempotency-Key"


class IdempotencyMiddleware:
    """FastAPI 中间件：检测 Idempotency-Key header。

    同一 key 在 24h 内的重复 POST/PATCH/PUT 请求返回缓存的 201/200 响应。
    不适用于 GET 请求。
    """

    def __init__(self, app: FastAPI):
        self.app = app

    async def __call__(self, request: Request, call_next):
        if request.method in ("GET", "DELETE", "OPTIONS", "HEAD"):
            return await call_next(request)

        idem_key = request.headers.get(HEADER)
        if not idem_key:
            return await call_next(request)

        cache_key = f"idempotency:{idem_key}"
        cached = await redis_get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            return JSONResponse(
                status_code=cached_data["status"],
                content=cached_data["body"],
            )

        response = await call_next(request)

        # 只缓存成功响应（2xx）
        if 200 <= response.status_code < 300:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            await redis_set(cache_key, json.dumps({
                "status": response.status_code,
                "body": json.loads(body.decode()) if body else {},
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }), IDEMPOTENCY_TTL)

            return JSONResponse(
                status_code=response.status_code,
                content=json.loads(body.decode()) if body else {},
            )

        return response


def setup_idempotency(app: FastAPI) -> None:
    app.add_middleware(IdempotencyMiddleware)

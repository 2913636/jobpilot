"""Kafka 事件中间件 — 在所有后端服务中注入用户行为追踪。

通过 FastAPI middleware 拦截 API 请求，将用户操作事件发送到 Kafka。
"""

import asyncio
import json
import time
from typing import Any

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class UserEventMiddleware(BaseHTTPMiddleware):
    """FastAPI 中间件：将每个 API 请求记录为用户行为事件并发送到 Kafka。"""

    def __init__(self, app: FastAPI, kafka_producer=None, topic: str = "user-events"):
        super().__init__(app)
        self.topic = topic
        self._producer = kafka_producer

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000

        # 跳过健康检查和静态文件
        if request.url.path in ("/health", "/", "/metrics"):
            return response

        # 异步发送事件（不阻塞请求）
        asyncio.create_task(self._send_event(request, response, duration_ms))
        return response

    async def _send_event(self, request: Request, response: Response, duration_ms: float):
        event = {
            "event_type": f"api.{request.method.lower()}",
            "source": request.url.path,
            "payload": {
                "method": request.method,
                "path": request.url.path,
                "query_string": str(request.query_params),
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "user_agent": request.headers.get("user-agent", ""),
                "ip": request.client.host if request.client else "",
            },
            "user_id": getattr(request.state, "user_id", None),
        }

        # 尝试发送到 Kafka
        try:
            await self._send_to_kafka(event)
        except Exception:
            # 降级：写本地日志
            pass

        # 同时保存到 PG
        try:
            await self._save_to_db(event)
        except Exception:
            pass

    async def _send_to_kafka(self, event: dict):
        if self._producer is None:
            return
        try:
            import aiokafka
            if isinstance(self._producer, aiokafka.AIOKafkaProducer):
                await self._producer.send_and_wait(
                    self.topic,
                    json.dumps(event, default=str).encode(),
                )
        except ImportError:
            pass

    async def _save_to_db(self, event: dict):
        """保存事件到 PostgreSQL。"""
        from sqlalchemy import text
        from common.db import async_session_factory

        async with async_session_factory() as db:
            await db.execute(
                text(
                    "INSERT INTO user_events (user_id, event_type, source, payload) "
                    "VALUES (:uid, :etype, :src, :payload)"
                ),
                {
                    "uid": event.get("user_id"),
                    "etype": event["event_type"],
                    "src": event["source"],
                    "payload": json.dumps(event["payload"], default=str),
                },
            )
            await db.commit()


def setup_event_middleware(app: FastAPI, kafka_producer=None):
    """为 FastAPI 应用注册事件追踪中间件。"""
    app.add_middleware(UserEventMiddleware, kafka_producer=kafka_producer)

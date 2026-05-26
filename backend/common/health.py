"""增强健康检查 — /health/livez (存活) 和 /health/readyz (就绪)。

Usage:
    from common.health import setup_health_endpoints, HealthStatus
    status = HealthStatus()
    setup_health_endpoints(app, status)
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Response


@dataclass
class HealthStatus:
    """追踪每个依赖的健康状态。"""
    db_ok: bool = True
    redis_ok: bool = True
    es_ok: bool = True
    milvus_ok: bool = True
    neo4j_ok: bool = True
    nats_ok: bool = True
    ready: bool = False

    def failing_components(self) -> list[str]:
        components: list[str] = []
        if not self.db_ok: components.append("postgres")
        if not self.redis_ok: components.append("redis")
        if not self.es_ok: components.append("elasticsearch")
        if not self.milvus_ok: components.append("milvus")
        if not self.neo4j_ok: components.append("neo4j")
        if not self.nats_ok: components.append("nats")
        return components

    def is_healthy(self) -> bool:
        return len(self.failing_components()) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "ok" if self.is_healthy() else "degraded",
            "ready": self.ready,
            "components": {
                "postgres": "ok" if self.db_ok else "unreachable",
                "redis": "ok" if self.redis_ok else "unreachable",
                "elasticsearch": "ok" if self.es_ok else "unreachable",
                "milvus": "ok" if self.milvus_ok else "unreachable",
                "neo4j": "ok" if self.neo4j_ok else "unreachable",
                "nats": "ok" if self.nats_ok else "unreachable",
            },
            "failing": self.failing_components(),
        }


_status_instance: HealthStatus | None = None


def get_health_status() -> HealthStatus:
    global _status_instance
    if _status_instance is None:
        _status_instance = HealthStatus()
    return _status_instance


def setup_health_endpoints(app: FastAPI, status: HealthStatus | None = None) -> None:
    """注册 /health/livez 和 /health/readyz 端点。"""
    if status is None:
        status = get_health_status()
    global _status_instance
    _status_instance = status

    @app.get("/health/livez", include_in_schema=False)
    async def livez():
        """存活探针：进程是否还在运行。始终返回 200。"""
        return {"status": "alive"}

    @app.get("/health/readyz", include_in_schema=False)
    async def readyz():
        """就绪探针：依赖是否可用。全部健康返回 200，否则 503。"""
        s = get_health_status()
        if s.is_healthy() and s.ready:
            return s.to_dict()
        return Response(
            content=__import__("json").dumps(s.to_dict()),
            status_code=503,
            media_type="application/json",
        )

    # 保持旧的 /health 兼容
    @app.get("/health", include_in_schema=False)
    async def health():
        s = get_health_status()
        code = 200 if s.is_healthy() else 503
        return Response(
            content=__import__("json").dumps(s.to_dict()),
            status_code=code,
            media_type="application/json",
        )

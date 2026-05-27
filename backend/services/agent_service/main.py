"""Agent Service — 工作流编排、事件追踪、模型管理、系统监控。"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth import get_current_user
from common.db import engine, get_db

from .models import Base
from .monitoring.metrics import setup_metrics
from .event_middleware import setup_event_middleware
from .service import AgentService
from common.cors import setup_cors
from common.exceptions import setup_exception_handlers

app = FastAPI(
    title="Agent Service",
    description="""Temporal 工作流编排、用户行为追踪、模型再训练、系统健康监控。

## Curl Examples
```bash
# Trigger application workflow
curl -X POST :8006/workflows/application -H 'Authorization: Bearer $TOKEN' \\
  -H 'Content-Type: application/json' -d '{"job_id":"..."}'

# Trigger daily scan
curl -X POST :8006/workflows/daily-scan -H 'Authorization: Bearer $TOKEN'

# Health probe
curl -X POST :8006/monitoring/probe -H 'Authorization: Bearer $TOKEN'
```
""",
    version="1.0.0",
    root_path="/api/agents",
)

setup_metrics(app)
setup_event_middleware(app)
setup_cors(app)
setup_exception_handlers(app)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health", tags=["System"], include_in_schema=False)
async def health():
    return {"status": "ok", "service": "agent-service"}


# ── 工作流 ──────────────────────────────────────────────────────

@app.post("/workflows/daily-scan", tags=["Workflows"], summary="触发每日扫描")
async def trigger_daily_scan(
    params: dict | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AgentService(db)
    return await svc.trigger_daily_scan(params)


@app.post("/workflows/application", tags=["Workflows"], summary="触发申请流程")
async def trigger_application(
    params: dict[str, Any],
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AgentService(db)
    return await svc.trigger_application_workflow({**params, "user_id": user["sub"]})


@app.post("/workflows/backup", tags=["Workflows"], summary="触发备份工作流")
async def trigger_backup(
    params: dict | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手动触发数据库备份。Temporal Cron 会在每周日 03:00 UTC 自动执行。"""
    svc = AgentService(db)
    return await svc.trigger_backup_workflow(params)


# ── 事件追踪 ────────────────────────────────────────────────────

@app.get("/events", tags=["Events"], summary="查询事件")
async def get_events(
    event_type: str | None = Query(None),
    limit: int = Query(100, le=500),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AgentService(db)
    events = await svc.get_events(uuid.UUID(user["sub"]), event_type, limit)
    return [{"id": str(e.id), "event_type": e.event_type, "source": e.source,
             "created_at": e.created_at.isoformat()} for e in events]


# ── 模型管理 ────────────────────────────────────────────────────

@app.post("/models/retrain-check", tags=["Models"], summary="触发模型再训练检查")
async def check_retraining(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AgentService(db)
    result = await svc.check_retraining(uuid.UUID(user["sub"]))
    if result is None:
        return {"triggered": False, "message": "编辑次数不足 200 条，未触发训练"}
    return {"triggered": True, **result}


@app.get("/models", tags=["Models"], summary="模型注册表")
async def list_models(
    user: dict[str, Any] = Depends(get_current_user),
    model_name: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    svc = AgentService(db)
    models = await svc.get_model_registry(model_name)
    return [{"id": str(m.id), "model_name": m.model_name, "version": m.version,
             "status": m.status, "created_at": m.created_at.isoformat()} for m in models]


# ── 分析 ────────────────────────────────────────────────────────

@app.post("/analytics/skill-trends", tags=["Analytics"], summary="运行技能分析")
async def run_skill_analysis(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AgentService(db)
    return await svc.run_skill_analysis()


@app.get("/analytics/skill-trends", tags=["Analytics"], summary="技能热度")
async def get_skill_trends(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AgentService(db)
    return [{"skill": t.skill_name, "frequency": t.frequency, "period": t.period}
            for t in await svc.get_skill_trends()]


# ── 监控 ────────────────────────────────────────────────────────

@app.post("/monitoring/probe", tags=["Monitoring"], summary="全服务健康探测")
async def probe_services_endpoint(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AgentService(db)
    return await svc.probe_all_services()


@app.get("/monitoring/health-history", tags=["Monitoring"], summary="健康历史")
async def health_history(
    service: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = AgentService(db)
    return [{"service": h.service, "status": h.status, "latency_ms": h.latency_ms,
             "checked_at": h.checked_at.isoformat()}
            for h in await svc.get_health_history(service, limit)]

"""Agent Service — 工作流编排、事件追踪、模型再训练、健康监控。"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .analytics import AnalyticsProcessor, run_company_trend_analysis, run_skill_trend_analysis
from .models import AgentSession, HealthCheck, ModelRegistry, SkillTrend, UserEvent
from .monitoring.metrics import probe_services
from .retraining import RetrainingTrigger


class AgentService:
    """Agent 编排服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.analytics = AnalyticsProcessor()
        self.retraining = RetrainingTrigger(db)

    # ── 会话管理 ──────────────────────────────────────────────

    async def create_session(self, user_id: uuid.UUID, session_type: str,
                             workflow_id: str | None = None) -> AgentSession:
        session = AgentSession(user_id=user_id, session_type=session_type,
                               workflow_id=workflow_id)
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get_session(self, session_id: uuid.UUID) -> AgentSession | None:
        result = await self.db.execute(select(AgentSession).where(AgentSession.id == session_id))
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[AgentSession]:
        result = await self.db.execute(
            select(AgentSession).where(AgentSession.user_id == user_id)
            .order_by(AgentSession.created_at.desc())
        )
        return list(result.scalars().all())

    # ── 事件追踪 ──────────────────────────────────────────────

    async def track_event(self, event: dict[str, Any]):
        """记录用户行为事件并转发到流处理器。"""
        evt = UserEvent(
            user_id=uuid.UUID(event["user_id"]) if event.get("user_id") else None,
            event_type=event["event_type"],
            source=event.get("source", "backend"),
            payload=event.get("payload"),
        )
        self.db.add(evt)
        await self.db.commit()
        await self.analytics.process_event(event)

    async def get_events(self, user_id: uuid.UUID | None = None,
                         event_type: str | None = None,
                         limit: int = 100) -> list[UserEvent]:
        stmt = select(UserEvent)
        if user_id:
            stmt = stmt.where(UserEvent.user_id == user_id)
        if event_type:
            stmt = stmt.where(UserEvent.event_type == event_type)
        stmt = stmt.order_by(UserEvent.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Temporal 工作流触发 ──────────────────────────────────

    async def trigger_daily_scan(self, params: dict | None = None) -> dict:
        """触发每日职位扫描工作流。"""
        try:
            import temporalio.client
            client = await temporalio.client.Client.connect(
                f"{__import__('os').getenv('TEMPORAL_HOST', 'temporal')}:7233"
            )
            handle = await client.start_workflow(
                "DailyScanWorkflow", params or {},
                id=f"daily-scan-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
                task_queue="jobpilot-task-queue",
            )
            return {"workflow_id": handle.id, "status": "started"}
        except ImportError:
            return {"workflow_id": f"mock-{uuid.uuid4().hex[:8]}", "status": "mock"}

    async def trigger_application_workflow(self, params: dict) -> dict:
        """触发完整申请流程工作流。"""
        try:
            import temporalio.client
            client = await temporalio.client.Client.connect(
                f"{__import__('os').getenv('TEMPORAL_HOST', 'temporal')}:7233"
            )
            handle = await client.start_workflow(
                "ApplicationWorkflow", params,
                id=f"app-{params.get('user_id', 'unknown')}-{uuid.uuid4().hex[:8]}",
                task_queue="jobpilot-task-queue",
            )
            return {"workflow_id": handle.id, "status": "started"}
        except ImportError:
            return {"workflow_id": f"mock-{uuid.uuid4().hex[:8]}", "status": "mock"}

    # ── 模型再训练 ────────────────────────────────────────────

    async def check_retraining(self, user_id: uuid.UUID) -> dict | None:
        return await self.retraining.check_and_trigger(str(user_id))

    async def get_model_registry(self, model_name: str | None = None) -> list[ModelRegistry]:
        stmt = select(ModelRegistry)
        if model_name:
            stmt = stmt.where(ModelRegistry.model_name == model_name)
        stmt = stmt.order_by(ModelRegistry.created_at.desc()).limit(50)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── 分析作业 ──────────────────────────────────────────────

    async def run_skill_analysis(self) -> dict:
        return await run_skill_trend_analysis(self.db)

    async def run_company_analysis(self) -> dict:
        return await run_company_trend_analysis(self.db)

    async def get_skill_trends(self, limit: int = 20) -> list[SkillTrend]:
        result = await self.db.execute(
            select(SkillTrend).order_by(SkillTrend.frequency.desc()).limit(limit)
        )
        return list(result.scalars().all())

    # ── 健康监控 ──────────────────────────────────────────────

    async def probe_all_services(self) -> list[dict]:
        return await probe_services(self.db)

    async def get_health_history(self, service: str | None = None,
                                  limit: int = 50) -> list[HealthCheck]:
        stmt = select(HealthCheck)
        if service:
            stmt = stmt.where(HealthCheck.service == service)
        stmt = stmt.order_by(HealthCheck.checked_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

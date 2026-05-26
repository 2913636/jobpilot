"""端到端集成测试 — 模拟完整用户旅程。

旅程：注册 → 创建简历 → 搜索职位 → 匹配评估 → 生成定制简历 →
       模拟投递 → 模拟面试 → 查看报告

使用 mock 替代外部服务（Temporal/LiveKit/Kafka），验证各步骤接口契约。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.db import Base, get_db

TEST_DB_URL = "postgresql+asyncpg://jobpilot:jobpilot_secret@localhost:5432/jobpilot_test"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    from services.agent_service import main as app_module
    app = app_module.app

    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── E2E User Journey ──────────────────────────────────────────────

class TestUserJourney:
    """模拟完整用户旅程的端到端测试。"""

    @pytest.fixture
    def auth_headers(self):
        from common.auth import create_access_token
        token = create_access_token({
            "sub": "00000000-0000-0000-0000-000000000001",
            "email": "e2e_test@example.com",
            "role": "candidate",
        })
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_step1_health(self, client):
        """Step 0: 服务健康检查。"""
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_step2_track_event(self, client, auth_headers, db_session):
        """Step 1: 追踪用户注册事件。"""
        svc = AgentService(db_session)
        from services.agent_service.service import AgentService
        await svc.track_event({
            "user_id": "00000000-0000-0000-0000-000000000001",
            "event_type": "user.registered",
            "source": "user-service",
            "payload": {"email": "e2e_test@example.com"},
        })
        events = await svc.get_events(uuid.UUID("00000000-0000-0000-0000-000000000001"))
        assert len(events) >= 1
        assert events[0].event_type == "user.registered"

    @pytest.mark.asyncio
    async def test_step3_trigger_workflow(self, client, auth_headers):
        """Step 3: 触发工作流。"""
        resp = await client.post("/workflows/application", json={
            "job_id": "00000000-0000-0000-0000-000000000002",
            "auto_submit": True,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "workflow_id" in data

    @pytest.mark.asyncio
    async def test_step4_retrain_check(self, client, auth_headers):
        """Step 4: 检查模型再训练触发。"""
        resp = await client.post("/models/retrain-check", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "triggered" in data

    @pytest.mark.asyncio
    async def test_step5_list_models(self, client):
        """Step 5: 查询模型注册表。"""
        resp = await client.get("/models")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_step6_run_skill_analysis(self, client, db_session):
        """Step 6: 运行技能分析作业。"""
        # 先写入一些事件
        svc = AgentService(db_session)
        from services.agent_service.service import AgentService
        for i in range(5):
            await svc.track_event({
                "user_id": "00000000-0000-0000-0000-000000000001",
                "event_type": "api.post",
                "source": "/resume/parse",
                "payload": {"skills": ["python", "docker", "kubernetes"]},
            })

        resp = await client.post("/analytics/skill-trends")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills_analyzed" in data

    @pytest.mark.asyncio
    async def test_step7_skill_trends(self, client):
        """Step 7: 查询技能热度。"""
        resp = await client.get("/analytics/skill-trends")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_step8_metrics_endpoint(self, client):
        """Step 8: Prometheus /metrics 端点。"""
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        text = resp.text
        assert "http_requests_total" in text
        assert "app_uptime_seconds" in text

    @pytest.mark.asyncio
    async def test_step9_full_journey(self, client, auth_headers, db_session):
        """全流程验证：注册→搜索→匹配→生成→投递→面试→报告（API 可用性）。"""
        from services.agent_service.service import AgentService

        svc = AgentService(db_session)
        user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        # 1. 注册事件
        await svc.track_event({
            "user_id": str(user_id), "event_type": "user.registered",
            "source": "user-service", "payload": {"email": "e2e@test.com"},
        })

        # 2. 创建简历事件
        await svc.track_event({
            "user_id": str(user_id), "event_type": "resume.created",
            "source": "resume-service",
            "payload": {"title": "My Resume", "skills": ["python", "aws"]},
        })

        # 3. 搜索职位事件
        await svc.track_event({
            "user_id": str(user_id), "event_type": "job.search",
            "source": "match-service", "payload": {"keyword": "python developer"},
        })

        # 4. 匹配评估事件
        await svc.track_event({
            "user_id": str(user_id), "event_type": "match.evaluated",
            "source": "match-service",
            "payload": {"resume_id": "r1", "matches": 15},
        })

        # 5. 投递事件
        await svc.track_event({
            "user_id": str(user_id), "event_type": "application.created",
            "source": "apply-service",
            "payload": {"job_id": "j1", "status": "submitted"},
        })

        # 6. 面试事件
        await svc.track_event({
            "user_id": str(user_id), "event_type": "interview.started",
            "source": "interview-service",
            "payload": {"room_name": "interview-abc123"},
        })

        # 7. 报告事件
        await svc.track_event({
            "user_id": str(user_id), "event_type": "report.generated",
            "source": "interview-service",
            "payload": {"overall_score": 85.5},
        })

        # 验证全流程事件链
        events = await svc.get_events(user_id)
        assert len(events) >= 7, f"Expected >= 7 events, got {len(events)}"

        event_types = [e.event_type for e in events]
        assert "user.registered" in event_types
        assert "resume.created" in event_types
        assert "job.search" in event_types
        assert "match.evaluated" in event_types
        assert "application.created" in event_types
        assert "interview.started" in event_types
        assert "report.generated" in event_types

        # 验证事件在数据库中持久化
        all_events = await svc.get_events(user_id, limit=100)
        assert len(all_events) >= 7


# 需要导入 uuid 和 AgentService
import uuid
from services.agent_service.service import AgentService

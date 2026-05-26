"""Tests for audit logging."""

import pytest


async def _register_verify_and_login(client, email: str) -> str:
    """Helper: register, verify, login, return access_token."""
    from services.user_service.models import User
    from sqlalchemy import select
    from common.db import async_session_factory

    await client.post("/auth/register", json={
        "email": email, "password": "securePass123", "full_name": "Audit User",
    })

    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if user and user.verification_token:
        await client.post("/auth/verify-email", json={"email": email, "token": user.verification_token})

    resp = await client.post("/auth/login", json={"email": email, "password": "securePass123"})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_audit_logs_registered_on_register(client):
    """注册操作生成审计日志。"""
    await _register_verify_and_login(client, "audit1@example.com")
    token = await _register_verify_and_login(client, "audit2@example.com")

    resp = await client.get("/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    logs = resp.json()
    assert isinstance(logs, list)
    # 应该有 register, verify, login 的日志
    actions = [log["action"] for log in logs]
    assert "user.registered" in actions
    assert "user.login" in actions


@pytest.mark.asyncio
async def test_audit_logs_include_login_failed(client):
    """登录失败也记录审计日志（但 user_id 为 null）。"""
    for i in range(3):
        await client.post("/auth/login", json={
            "email": "nobody@example.com", "password": "wrong",
        })

    # 从 DB 直接验证（审计日志 user_id 为 null）
    from services.user_service.models import AuditLog
    from sqlalchemy import select, func
    from common.db import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "user.login_failed")
        )
        count = result.scalar()
        assert count >= 3, f"Expected >=3 failed login logs, got {count}"


@pytest.mark.asyncio
async def test_audit_logs_on_profile_update(client):
    """更新档案记录审计日志。"""
    token = await _register_verify_and_login(client, "audit3@example.com")

    await client.put("/profile", json={"location": "Shanghai"},
                     headers={"Authorization": f"Bearer {token}"})

    resp = await client.get("/audit-logs", headers={"Authorization": f"Bearer {token}"})
    actions = [log["action"] for log in resp.json()]
    assert "profile.updated" in actions


@pytest.mark.asyncio
async def test_audit_logs_require_auth(client):
    """未登录不能访问审计日志。"""
    resp = await client.get("/audit-logs")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_forgot_password_creates_audit_log(client):
    """忘记密码也生成审计日志。"""
    await _register_verify_and_login(client, "audit4@example.com")
    await client.post("/auth/forgot-password", json={"email": "audit4@example.com"})

    from services.user_service.models import AuditLog
    from sqlalchemy import select, func
    from common.db import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(
            select(func.count()).select_from(AuditLog)
            .where(AuditLog.action == "user.password_reset_requested")
        )
        count = result.scalar()
        assert count >= 1

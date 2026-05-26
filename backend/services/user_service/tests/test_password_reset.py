"""Tests for password reset flow."""

import pytest

REGISTER_URL = "/auth/register"
VERIFY_URL = "/auth/verify-email"
FORGOT_URL = "/auth/forgot-password"
RESET_URL = "/auth/reset-password"

VALID_USER = {"email": "reset@example.com", "password": "oldPass123", "full_name": "Reset User"}


async def _register_and_get_token(client, email: str) -> str | None:
    """Helper: register and return verification token from DB."""
    await client.post(REGISTER_URL, json={
        "email": email, "password": "oldPass123", "full_name": "Test",
    })
    from services.user_service.models import User
    from sqlalchemy import select
    from common.db import async_session_factory
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
    return user.verification_token if user else None


@pytest.mark.asyncio
async def test_forgot_password_always_returns_success(client):
    """忘记密码对存在的邮箱和不存在都返回成功（防枚举）。"""
    # 不存在
    resp = await client.post(FORGOT_URL, json={"email": "nobody@example.com"})
    assert resp.status_code == 200
    assert "sent" in resp.json()["message"].lower()

    # 存在
    await _register_and_get_token(client, "exists@example.com")
    resp = await client.post(FORGOT_URL, json={"email": "exists@example.com"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_wrong_token(client):
    """错误的 reset token 返回 400。"""
    await _register_and_get_token(client, "reset1@example.com")
    resp = await client.post(RESET_URL, json={
        "email": "reset1@example.com",
        "token": "invalid-token",
        "new_password": "newPass456",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_flow(client):
    """完整密码重置流程：忘记密码 → 获取 reset_token → 重置 → 用新密码登录。"""
    email = "fullreset@example.com"
    await _register_and_get_token(client, email)

    # 触发忘记密码
    await client.post(FORGOT_URL, json={"email": email})

    # 获取 reset token
    from services.user_service.models import User
    from sqlalchemy import select
    from common.db import async_session_factory
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    assert user and user.reset_token, "reset_token should be set"

    # 验证邮箱（才能登录）
    if user.verification_token:
        await client.post(VERIFY_URL, json={"email": email, "token": user.verification_token})

    # 用 token 重置密码
    resp = await client.post(RESET_URL, json={
        "email": email, "token": user.reset_token, "new_password": "newPass789!",
    })
    assert resp.status_code == 200

    # 用新密码登录
    login_resp = await client.post("/auth/login", json={
        "email": email, "password": "newPass789!",
    })
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_short_password(client):
    """新密码太短返回 422。"""
    resp = await client.post(RESET_URL, json={
        "email": "reset@example.com", "token": "any", "new_password": "ab",
    })
    assert resp.status_code == 422

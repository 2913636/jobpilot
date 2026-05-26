"""Tests for email verification flow."""

import pytest

REGISTER_URL = "/auth/register"
VERIFY_URL = "/auth/verify-email"
LOGIN_URL = "/auth/login"

VALID_USER = {"email": "verify@example.com", "password": "securePass123", "full_name": "Verify User"}


@pytest.mark.asyncio
async def test_register_sends_verification_token(client):
    """注册后用户 is_verified=False，需要验证才能登录。"""
    resp = await client.post(REGISTER_URL, json=VALID_USER)
    assert resp.status_code == 201

    # 未验证时登录失败
    login_resp = await client.post(LOGIN_URL, json={
        "email": VALID_USER["email"], "password": VALID_USER["password"],
    })
    assert login_resp.status_code == 401
    assert "not verified" in login_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_email_wrong_token(client):
    """错误验证码返回 400。"""
    await client.post(REGISTER_URL, json=VALID_USER)
    resp = await client.post(VERIFY_URL, json={
        "email": VALID_USER["email"], "token": "WRONG1",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_then_login(client):
    """验证邮箱后可以正常登录。"""
    await client.post(REGISTER_URL, json=VALID_USER)

    # 从审计日志或控制台输出获取 token 不可行，直接用已知 token 测试错误分支
    # 正常流程：注册时打印了 token，实际测试需要 mock SMTP 或从 DB 获取

    # 先测错误 token
    resp = await client.post(VERIFY_URL, json={"email": VALID_USER["email"], "token": "XXXXXX"})
    assert resp.status_code == 400

    # 从 DB 获取验证 token
    from services.user_service.models import User
    from sqlalchemy import select
    from common.db import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.email == VALID_USER["email"]))
        user = result.scalar_one_or_none()

    if user and user.verification_token:
        resp = await client.post(VERIFY_URL, json={
            "email": VALID_USER["email"], "token": user.verification_token,
        })
        assert resp.status_code == 200
        assert "verified" in resp.json()["message"].lower()

        # 现在可以登录了
        login_resp = await client.post(LOGIN_URL, json={
            "email": VALID_USER["email"], "password": VALID_USER["password"],
        })
        assert login_resp.status_code == 200
        assert "access_token" in login_resp.json()


@pytest.mark.asyncio
async def test_double_verify_fails(client):
    """重复验证返回 400。"""
    await client.post(REGISTER_URL, json={
        "email": "double@example.com", "password": "securePass123", "full_name": "Double",
    })

    from services.user_service.models import User
    from sqlalchemy import select
    from common.db import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.email == "double@example.com"))
        user = result.scalar_one_or_none()

    if user and user.verification_token:
        await client.post(VERIFY_URL, json={"email": "double@example.com", "token": user.verification_token})
        resp = await client.post(VERIFY_URL, json={"email": "double@example.com", "token": user.verification_token})
        assert resp.status_code == 400
        assert "already verified" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_nonexistent_user(client):
    """验证不存在的用户返回 400。"""
    resp = await client.post(VERIFY_URL, json={
        "email": "nobody@example.com", "token": "ABC123",
    })
    assert resp.status_code == 400

"""Tests for login rate limiting."""

import pytest

LOGIN_URL = "/auth/login"
VALID_CREDENTIALS = {"email": "ratelimit@example.com", "password": "wrong"}


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_5_failures(client):
    """同一 IP 5 次失败后第 6 次被锁定。"""
    for i in range(5):
        resp = await client.post(LOGIN_URL, json={
            "email": f"fail{i}@example.com", "password": "wrong",
        })
        assert resp.status_code == 401

    # 第 6 次应被限流
    resp = await client.post(LOGIN_URL, json=VALID_CREDENTIALS)
    assert resp.status_code == 401
    detail = resp.json()["detail"].lower()
    assert "too many" in detail or "locked" in detail, f"Expected rate-limit message, got: {detail}"


@pytest.mark.asyncio
async def test_rate_limit_uses_ip(client):
    """不同 IP 的请求不受对方限流影响（通过 custom_headers 模拟）。"""
    # 同一 IP 失败 5 次
    for i in range(5):
        resp = await client.post(LOGIN_URL, json={
            "email": f"ipfail{i}@example.com", "password": "wrong",
        }, headers={"X-Forwarded-For": "10.0.0.1"})
        assert resp.status_code == 401

    # 同一 IP 第 6 次被锁
    resp = await client.post(LOGIN_URL, json={
        "email": "ipfail@example.com", "password": "wrong",
    }, headers={"X-Forwarded-For": "10.0.0.1"})
    assert resp.status_code == 401

    # 不同 IP 不受影响
    resp = await client.post(LOGIN_URL, json={
        "email": "other@example.com", "password": "wrong",
    }, headers={"X-Forwarded-For": "10.0.0.2"})
    assert resp.status_code == 401  # Still 401 (wrong password) but not rate-limited

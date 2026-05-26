"""Tests for POST /auth/register and POST /auth/login (updated for email verification)."""

import pytest

REGISTER_URL = "/auth/register"
LOGIN_URL = "/auth/login"
VERIFY_URL = "/auth/verify-email"

VALID_USER = {"email": "test@example.com", "password": "securePass123", "full_name": "Test User"}


async def _get_verification_token(email: str) -> str | None:
    from services.user_service.models import User
    from sqlalchemy import select
    from common.db import async_session_factory
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
    return user.verification_token if user else None


@pytest.mark.asyncio
async def test_register_success(client):
    """Registering a new user returns 201 with token and user info."""
    resp = await client.post(REGISTER_URL, json=VALID_USER)
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == VALID_USER["email"]
    assert data["user"]["full_name"] == VALID_USER["full_name"]


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    """Registering the same email twice returns 409."""
    await client.post(REGISTER_URL, json=VALID_USER)
    resp = await client.post(REGISTER_URL, json=VALID_USER)
    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_short_password(client):
    """Password shorter than 6 characters returns 422."""
    resp = await client.post(REGISTER_URL, json={
        "email": "short@example.com", "password": "ab", "full_name": "Short PW",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email(client):
    """Invalid email format returns 422."""
    resp = await client.post(REGISTER_URL, json={
        "email": "not-an-email", "password": "securePass123", "full_name": "Bad Email",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_fails_before_verification(client):
    """Login before email verification returns 401."""
    await client.post(REGISTER_URL, json=VALID_USER)
    resp = await client.post(LOGIN_URL, json={
        "email": VALID_USER["email"], "password": VALID_USER["password"],
    })
    assert resp.status_code == 401
    assert "not verified" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_success_after_verification(client):
    """Login with correct credentials + verified email returns 200."""
    await client.post(REGISTER_URL, json=VALID_USER)
    token = await _get_verification_token(VALID_USER["email"])
    if token:
        await client.post(VERIFY_URL, json={"email": VALID_USER["email"], "token": token})

    resp = await client.post(LOGIN_URL, json={
        "email": VALID_USER["email"], "password": VALID_USER["password"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == VALID_USER["email"]


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    """Login with bad password returns 401."""
    await client.post(REGISTER_URL, json=VALID_USER)
    tok = await _get_verification_token(VALID_USER["email"])
    if tok:
        await client.post(VERIFY_URL, json={"email": VALID_USER["email"], "token": tok})

    resp = await client.post(LOGIN_URL, json={
        "email": VALID_USER["email"], "password": "wrong-password",
    })
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    """Login with an unregistered email returns 401."""
    resp = await client.post(LOGIN_URL, json={
        "email": "nobody@example.com", "password": "anything",
    })
    assert resp.status_code == 401

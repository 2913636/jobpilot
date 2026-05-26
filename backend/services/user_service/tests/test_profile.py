"""Tests for GET /profile and PUT /profile."""

import pytest


PROFILE_URL = "/profile"


async def _register_and_get_token(client, email="profile@example.com"):
    """Helper: register a user and return the access token + user_id."""
    resp = await client.post("/auth/register", json={
        "email": email,
        "password": "securePass123",
        "full_name": "Profile User",
    })
    assert resp.status_code == 201
    data = resp.json()
    return data["access_token"], data["user"]["id"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_profile_empty(client):
    """New user profile returns defaults with empty fields."""
    token, _ = await _register_and_get_token(client)
    resp = await client.get(PROFILE_URL, headers=_auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "profile@example.com"
    assert data["full_name"] == "Profile User"
    assert data["skills"] is None
    assert data["experience"] is None
    assert data["education"] is None


@pytest.mark.asyncio
async def test_get_profile_no_auth(client):
    """Request without token returns 401."""
    resp = await client.get(PROFILE_URL)
    assert resp.status_code == 403  # FastAPI HTTPBearer returns 403 for missing header


@pytest.mark.asyncio
async def test_get_profile_bad_token(client):
    """Malformed token returns 401."""
    resp = await client.get(PROFILE_URL, headers=_auth_header("not.a.valid.token"))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_profile_skills(client):
    """PUT /profile updates skills with normalization."""
    token, _ = await _register_and_get_token(client)
    resp = await client.put(PROFILE_URL, headers=_auth_header(token), json={
        "skills": ["Python", "  DOCKER  ", "kubernetes", "RandomTool"],
        "location": "Shanghai",
    })
    assert resp.status_code == 200
    data = resp.json()
    # "RandomTool" is not in the taxonomy, so it's dropped
    # "Python" -> "python", "DOCKER" -> "docker", "kubernetes" -> "kubernetes"
    skills = data["skills"]
    assert "python" in skills
    assert "docker" in skills
    assert "kubernetes" in skills
    assert "randomtool" not in skills
    assert data["location"] == "Shanghai"


@pytest.mark.asyncio
async def test_update_profile_experience(client):
    """PUT /profile stores structured experience entries."""
    token, _ = await _register_and_get_token(client)
    resp = await client.put(PROFILE_URL, headers=_auth_header(token), json={
        "experience": [
            {
                "company": "Acme Corp",
                "title": "Senior Engineer",
                "start_date": "2020-01",
                "end_date": "2023-06",
                "description": "Built microservices with Python and Docker",
                "current": False,
            },
            {
                "company": "Startup Inc",
                "title": "CTO",
                "start_date": "2023-07",
                "description": "Leading engineering team",
                "current": True,
            },
        ]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["experience"]) == 2
    assert data["experience"][0]["company"] == "Acme Corp"
    assert data["experience"][1]["current"] is True

    # Skills should be auto-extracted from experience descriptions
    skills = data["skills"] or []
    assert "python" in skills
    assert "docker" in skills


@pytest.mark.asyncio
async def test_update_profile_education(client):
    """PUT /profile stores education entries."""
    token, _ = await _register_and_get_token(client)
    resp = await client.put(PROFILE_URL, headers=_auth_header(token), json={
        "education": [
            {
                "school": "MIT",
                "degree": "BSc",
                "field_of_study": "Computer Science",
                "start_date": "2016-09",
                "end_date": "2020-06",
                "gpa": "3.8",
            }
        ]
    })
    assert resp.status_code == 200
    assert len(resp.json()["education"]) == 1


@pytest.mark.asyncio
async def test_update_profile_summary_extracts_skills(client):
    """PUT /profile with summary text auto-extracts known skill names."""
    token, _ = await _register_and_get_token(client)
    resp = await client.put(PROFILE_URL, headers=_auth_header(token), json={
        "summary": "Experienced engineer skilled in Python, AWS, and Terraform.",
    })
    assert resp.status_code == 200
    data = resp.json()
    skills = data["skills"] or []
    assert "python" in skills
    assert "aws" in skills
    assert "terraform" in skills
    assert data["summary"] is not None


@pytest.mark.asyncio
async def test_update_profile_partial(client):
    """PUT /profile with partial data only updates supplied fields."""
    token, _ = await _register_and_get_token(client)
    # First set some fields
    await client.put(PROFILE_URL, headers=_auth_header(token), json={
        "location": "Beijing",
        "phone": "123456",
    })
    # Then update only one field
    resp = await client.put(PROFILE_URL, headers=_auth_header(token), json={
        "phone": "789012",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["phone"] == "789012"
    assert data["location"] == "Beijing"  # unchanged

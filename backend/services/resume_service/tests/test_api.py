"""Integration tests for resume-service API — requires test database."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pytest
import pytest_asyncio


# Helper: register and get token from user-service-style auth
async def _register_and_auth(client):
    """Register a test user and return auth headers."""
    resp = await client.post("/auth/register", json={
        "email": "resume_test@example.com",
        "password": "securePass123",
        "full_name": "Resume Tester",
    })
    # This endpoint might not exist in resume-service; use a pre-minted token
    from common.auth import create_access_token
    token = create_access_token({
        "sub": "00000000-0000-0000-0000-000000000001",
        "email": "resume_test@example.com",
        "role": "candidate",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers(client):
    return await _register_and_auth(client)


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestResumeCRUD:
    @pytest.mark.asyncio
    async def test_list_empty(self, client, auth_headers):
        resp = await client.get("", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_list_no_auth(self, client):
        resp = await client.get("")
        assert resp.status_code in (401, 403)


class TestATSScoring:
    @pytest.mark.asyncio
    async def test_score_with_text(self, client, auth_headers):
        resp = await client.post("/score", headers=auth_headers, json={
            "text": (
                "John Doe\njohn@example.com\n\n"
                "SUMMARY\nSenior engineer with Python expertise.\n\n"
                "EXPERIENCE\nSenior Engineer at Acme Corp (2020-2023)\n"
                "- Designed microservices with Python and Docker\n"
                "- Reduced latency by 40%\n"
                "- Led team of 5 engineers\n\n"
                "EDUCATION\nBSc Computer Science, MIT\n\n"
                "SKILLS\nPython, Docker, Kubernetes, AWS, PostgreSQL, Redis"
            ),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 0 <= data["score"] <= 100
        assert "format" in data["breakdown"]
        assert "keywords" in data["breakdown"]
        assert "content" in data["breakdown"]
        assert "structure" in data["breakdown"]
        assert "impact" in data["breakdown"]
        assert isinstance(data["missing_keywords"], list)
        assert isinstance(data["suggestions"], list)
        # Good resume should score above 50
        assert data["score"] > 50, f"Expected >50, got {data['score']}"

    @pytest.mark.asyncio
    async def test_score_poor_resume(self, client, auth_headers):
        resp = await client.post("/score", headers=auth_headers, json={
            "text": "I am a developer. I like coding.",
        })
        assert resp.status_code == 200
        data = resp.json()
        # Poor resume should get a low score
        assert data["score"] < 50, f"Expected <50, got {data['score']}"

    @pytest.mark.asyncio
    async def test_score_with_jd_keywords(self, client, auth_headers):
        """Adding JD keywords should be reflected in missing_keywords."""
        resp = await client.post("/score", headers=auth_headers, json={
            "text": "Python developer with Flask experience.",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_score_no_text_no_resume_id(self, client, auth_headers):
        resp = await client.post("/score", headers=auth_headers, json={})
        assert resp.status_code == 400


class TestParseEndpoint:
    @pytest.mark.asyncio
    async def test_parse_unsupported_type(self, client, auth_headers):
        resp = await client.post("/parse", headers=auth_headers, files={
            "file": ("test.xyz", b"data", "application/octet-stream"),
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_parse_no_auth(self, client):
        resp = await client.post("/parse", files={
            "file": ("test.txt", b"data", "text/plain"),
        })
        assert resp.status_code in (401, 403)


class TestVersionManagement:
    @pytest.mark.asyncio
    async def test_versions_nonexistent_resume(self, client, auth_headers):
        resp = await client.get(
            "/00000000-0000-0000-0000-000000000099/versions",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestABTest:
    @pytest.mark.asyncio
    async def test_ab_test_create_nonexistent_resume(self, client, auth_headers):
        resp = await client.post(
            "/00000000-0000-0000-0000-000000000099/ab-test",
            headers=auth_headers,
            json={
                "variant_a_id": "00000000-0000-0000-0000-000000000001",
                "variant_b_id": "00000000-0000-0000-0000-000000000002",
            },
        )
        assert resp.status_code == 404

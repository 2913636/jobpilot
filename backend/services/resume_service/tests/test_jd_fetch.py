"""Tests for fetching generation inputs from sibling services."""

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from services.resume_service.service import fetch_jd_text, fetch_user_profile


class _FakeJobResponse:
    status_code = 200

    def json(self):
        return {
            "title": "Senior Backend Engineer",
            "company": "Acme",
            "description": "Build Python APIs and own PostgreSQL reliability.",
            "skills": ["Python", "FastAPI", "PostgreSQL"],
        }


class _FakeClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, timeout: float):
        return _FakeJobResponse()


@pytest.mark.asyncio
async def test_fetch_jd_text_formats_match_service_response(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    text = await fetch_jd_text(uuid.UUID("00000000-0000-0000-0000-000000000001"))

    assert "Senior Backend Engineer at Acme" in text
    assert "Build Python APIs" in text
    assert "Required skills: Python, FastAPI, PostgreSQL" in text


class _FakeProfileResponse:
    status_code = 200

    def json(self):
        return {
            "full_name": "Jane Candidate",
            "email": "jane@example.com",
            "skills": ["Python", "React"],
            "experience": [],
            "education": [],
        }


class _FakeProfileClient(_FakeClient):
    async def get(self, url: str, timeout: float):
        return _FakeProfileResponse()


@pytest.mark.asyncio
async def test_fetch_user_profile_uses_user_service_response(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _FakeProfileClient)

    profile = await fetch_user_profile(uuid.UUID("00000000-0000-0000-0000-000000000001"))

    assert profile["full_name"] == "Jane Candidate"
    assert profile["skills"] == ["Python", "React"]

"""Tests for fetching job descriptions from match-service."""

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from services.resume_service.service import fetch_jd_text


class _FakeResponse:
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
        return _FakeResponse()


@pytest.mark.asyncio
async def test_fetch_jd_text_formats_match_service_response(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    text = await fetch_jd_text(uuid.UUID("00000000-0000-0000-0000-000000000001"))

    assert "Senior Backend Engineer at Acme" in text
    assert "Build Python APIs" in text
    assert "Required skills: Python, FastAPI, PostgreSQL" in text


"""测试数据工厂 — 快速生成测试对象，避免硬编码。"""

import uuid
from datetime import datetime, timezone
from typing import Any

# ── User factory ──────────────────────────────────────────────────

def make_user(**overrides) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "email": f"test-{uuid.uuid4().hex[:8]}@example.com",
        "password_hash": "$2b$12$LJ3m4ys3GZfnYMz8kVsKaOSmBKWVFfHn5dXPqTk6oNFeIx3FEy9Rm",
        "full_name": "Test User",
        "role": "candidate",
        "is_active": True,
        "is_verified": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        **overrides,
    }


# ── Profile factory ───────────────────────────────────────────────

def make_profile(**overrides) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "phone": "+86 13800138000",
        "location": "Shanghai",
        "summary": "Experienced engineer with Python and AWS expertise.",
        "linkedin_url": "https://linkedin.com/in/testuser",
        "github_url": "https://github.com/testuser",
        "skills": ["python", "docker", "kubernetes", "aws"],
        "experience": [
            {
                "company": "Acme Corp",
                "title": "Senior Engineer",
                "start_date": "2020-01",
                "end_date": None,
                "description": "Built microservices",
                "current": True,
                "highlights": ["Reduced latency 40%"],
            }
        ],
        "education": [
            {
                "school": "MIT",
                "degree": "BSc",
                "field_of_study": "Computer Science",
                "start_date": "2016-09",
                "end_date": "2020-06",
            }
        ],
        **overrides,
    }


# ── Resume factory ────────────────────────────────────────────────

def make_resume(**overrides) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "title": "My Resume",
        "content": {
            "full_name": "Test User",
            "email": "test@example.com",
            "phone": "+86 13800138000",
            "skills": ["python", "docker"],
            "experience": [],
            "education": [],
        },
        "source_type": "upload",
        "status": "draft",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        **overrides,
    }


# ── Job factory ───────────────────────────────────────────────────

def make_job(**overrides) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "title": "Senior Software Engineer",
        "company": "Acme Corp",
        "description": "Build scalable microservices with Python and AWS.",
        "location": "Shanghai",
        "remote": False,
        "salary_min": 300000.0,
        "salary_max": 500000.0,
        "salary_currency": "CNY",
        "skills": ["python", "docker", "kubernetes", "aws"],
        "experience_level": "senior",
        "source": "boss",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        **overrides,
    }


# ── Application factory ───────────────────────────────────────────

def make_application(**overrides) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "job_id": uuid.uuid4(),
        "resume_id": uuid.uuid4(),
        "company": "Acme Corp",
        "title": "Software Engineer",
        "status": "draft",
        "notes": "",
        "timeline": [{"status": "draft", "timestamp": datetime.now(timezone.utc).isoformat(), "note": "Created"}],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        **overrides,
    }


# ── Interview factory ─────────────────────────────────────────────

def make_interview_session(**overrides) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "job_id": uuid.uuid4(),
        "room_name": f"interview-{uuid.uuid4().hex[:12]}",
        "status": "waiting",
        "transcript": [],
        "emotions": [],
        "created_at": datetime.now(timezone.utc),
        **overrides,
    }

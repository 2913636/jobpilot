"""Resume service — business logic for parsing, generation, scoring, and version management."""

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ABTest, Resume, ResumeVersion
from .parser import ResumeParser
from .generator import ResumeGenerator
from .scorer import ATSScorer
from .schemas import (
    ABTestRequest,
    ABTestResponse,
    ABTestResultUpdate,
    ATSScoreRequest,
    ATSScoreResponse,
    GenerateRequest,
    GenerateResponse,
    ParseResponse,
    ResumeContent,
    ResumeDetailResponse,
    ResumeListItem,
    ResumeVersionResponse,
)


class ResumeService:
    """Core resume CRUD and list operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: uuid.UUID, title: str, content: dict,
                     source_type: str = "upload", file_url: str | None = None,
                     job_id: uuid.UUID | None = None) -> Resume:
        resume = Resume(
            user_id=user_id, title=title, content=content,
            source_type=source_type, file_url=file_url, job_id=job_id,
        )
        self.db.add(resume)
        await self.db.flush()

        # Create initial version
        v1 = ResumeVersion(resume_id=resume.id, version_number=1, content=content)
        self.db.add(v1)
        await self.db.commit()
        await self.db.refresh(resume)
        return resume

    async def get(self, resume_id: uuid.UUID) -> Resume | None:
        result = await self.db.execute(
            select(Resume).where(Resume.id == resume_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[Resume]:
        result = await self.db.execute(
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(Resume.updated_at.desc())
        )
        return list(result.scalars().all())

    async def update_content(self, resume_id: uuid.UUID, content: dict) -> Resume | None:
        resume = await self.get(resume_id)
        if not resume:
            return None
        resume.content = content
        resume.updated_at = datetime.utcnow()
        await self.db.flush()

        # Create new version
        latest = await self.db.execute(
            select(func.max(ResumeVersion.version_number))
            .where(ResumeVersion.resume_id == resume_id)
        )
        next_ver = (latest.scalar() or 0) + 1
        v = ResumeVersion(
            resume_id=resume_id, version_number=next_ver,
            content=content, changes="Content updated",
        )
        self.db.add(v)
        await self.db.commit()
        await self.db.refresh(resume)
        return resume

    async def update_status(self, resume_id: uuid.UUID, status: str) -> Resume | None:
        resume = await self.get(resume_id)
        if not resume:
            return None
        resume.status = status
        await self.db.commit()
        await self.db.refresh(resume)
        return resume

    async def get_versions(self, resume_id: uuid.UUID) -> list[ResumeVersion]:
        result = await self.db.execute(
            select(ResumeVersion)
            .where(ResumeVersion.resume_id == resume_id)
            .order_by(ResumeVersion.version_number.desc())
        )
        return list(result.scalars().all())


class ParseService:
    """Resume file parsing service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.parser = ResumeParser()

    async def parse(self, user_id: uuid.UUID, filename: str, data: bytes) -> ParseResponse:
        content, raw_text, confidence = await self.parser.parse(filename, data)

        # Save as a resume record
        svc = ResumeService(self.db)
        resume = await svc.create(
            user_id=user_id,
            title=content.full_name or filename.rsplit(".", 1)[0],
            content=content.model_dump(),
            source_type="upload",
        )

        return ParseResponse(resume_id=resume.id, content=content, raw_text=raw_text, confidence=confidence)


class GenerateService:
    """Resume generation from JD + user profile."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.generator = ResumeGenerator()

    async def generate(self, user_id: uuid.UUID, request: GenerateRequest,
                       jd_text: str, profile: dict[str, Any]) -> GenerateResponse:
        content, jd_keywords = await self.generator.generate(
            jd_text=jd_text, profile=profile, title=request.title,
        )
        svc = ResumeService(self.db)
        resume = await svc.create(
            user_id=user_id, title=request.title,
            content=content.model_dump(), source_type="generated",
            job_id=request.job_id,
        )

        # Quick match score based on keyword overlap
        profile_skills = set(s.lower() for s in profile.get("skills", []))
        jd_skills = set(k.lower() for k in jd_keywords)
        match = len(profile_skills & jd_skills) / max(1, len(jd_skills)) * 100

        return GenerateResponse(
            resume_id=resume.id, content=content,
            jd_keywords=jd_keywords, match_score=round(match, 1),
        )


class ScoreService:
    """ATS scoring service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.scorer = ATSScorer()

    async def score(self, request: ATSScoreRequest) -> ATSScoreResponse:
        text = request.text
        jd_keywords: list[str] = []

        if not text and request.resume_id:
            svc = ResumeService(self.db)
            resume = await svc.get(request.resume_id)
            if resume:
                content = resume.content if isinstance(resume.content, dict) else {}
                text = self._content_to_text(content)
                # If resume was generated from a job, use that for keywords
                if resume.job_id:
                    jd_keywords = content.get("skills", [])

        if not text:
            raise ValueError("No text available for scoring")

        result = self.scorer.score(text, jd_keywords)

        # Save score to resume if we have an ID
        if request.resume_id:
            resume = await ResumeService(self.db).get(request.resume_id)
            if resume:
                resume.ats_score = result["score"]
                await self.db.commit()
                # Record score history
                history_svc = ScoreHistoryService(self.db)
                await history_svc.record_score(
                    request.resume_id, result["score"],
                    breakdown=result["breakdown"],
                    missing_keywords=result["missing_keywords"],
                    suggestions=result["suggestions"],
                )

        return ATSScoreResponse(
            score=result["score"],
            breakdown=result["breakdown"],
            missing_keywords=result["missing_keywords"],
            suggestions=result["suggestions"],
        )

    def _content_to_text(self, content: dict) -> str:
        parts: list[str] = []
        parts.append(content.get("full_name", ""))
        parts.append(content.get("summary", ""))
        for exp in content.get("experience", []):
            parts.append(f"{exp.get('title', '')} at {exp.get('company', '')}: {exp.get('description', '')}")
            parts.extend(exp.get("highlights", []))
        for edu in content.get("education", []):
            parts.append(f"{edu.get('degree', '')} from {edu.get('school', '')}")
        parts.append(", ".join(content.get("skills", [])))
        return "\n".join(p for p in parts if p)


class ABTestService:
    """A/B testing for resume variants."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, resume_id: uuid.UUID, request: ABTestRequest) -> ABTest:
        test = ABTest(
            resume_id=resume_id,
            variant_a_id=request.variant_a_id,
            variant_b_id=request.variant_b_id,
            metric=request.metric,
        )
        self.db.add(test)
        await self.db.commit()
        await self.db.refresh(test)
        return test

    async def update_results(self, resume_id: uuid.UUID, test_id: uuid.UUID,
                             data: ABTestResultUpdate) -> ABTest | None:
        result = await self.db.execute(
            select(ABTest).where(ABTest.id == test_id, ABTest.resume_id == resume_id)
        )
        test = result.scalar_one_or_none()
        if not test:
            return None
        test.results = data.results
        test.status = "completed"
        await self.db.commit()
        await self.db.refresh(test)
        return test

    async def list_by_resume(self, resume_id: uuid.UUID) -> list[ABTest]:
        result = await self.db.execute(
            select(ABTest).where(ABTest.resume_id == resume_id)
        )
        return list(result.scalars().all())


# ── Helper for fetching JD text (stub for match-service integration) ──

async def fetch_jd_text(job_id: uuid.UUID) -> str:
    """Fetch job description text from match-service.

    In production this calls POST http://match-service:8000/internal/jobs/{job_id}
    or publishes a NATS request.  Stub returns placeholder.
    """
    # TODO: Replace with actual HTTP/NATS call to match-service
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://match-service:8000/internal/jobs/{job_id}",
                timeout=5.0,
            )
            if resp.status_code == 200:
                return resp.json().get("description", "")
    except Exception:
        pass
    return f"Job description for job_id={job_id} (placeholder — connect to match-service)"


async def fetch_user_profile(profile_id: uuid.UUID) -> dict[str, Any]:
    """Fetch user profile from user-service.

    In production this calls GET http://user-service:8000/internal/profiles/{profile_id}.
    """
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://user-service:8000/internal/profiles/{profile_id}",
                timeout=5.0,
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {
        "full_name": "Candidate",
        "email": "candidate@example.com",
        "skills": ["python", "javascript", "react"],
        "experience": [],
        "education": [],
    }


class ImportService:
    """LinkedIn / GitHub 导入服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def import_from_url(self, user_id: uuid.UUID, url: str) -> dict[str, Any]:
        from urllib.parse import urlparse
        from .importers import import_linkedin, import_github

        domain = urlparse(url).netloc.lower()

        if "linkedin.com" in domain:
            content = await import_linkedin(url)
            source = "linkedin"
        elif "github.com" in domain:
            content = await import_github(url)
            source = "github"
        else:
            raise ValueError("Unsupported URL. Only LinkedIn and GitHub public profiles are supported.")

        svc = ResumeService(self.db)
        resume = await svc.create(
            user_id=user_id,
            title=f"{content.full_name or 'Imported'} - {source.title()}",
            content=content.model_dump(),
            source_type="upload",
        )
        return {"resume_id": resume.id, "content": content, "source": source}


class TemplateService:
    """简历模板管理。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_templates(self, category: str | None = None) -> list[dict[str, Any]]:
        from .models import ResumeTemplate
        from sqlalchemy import select

        stmt = select(ResumeTemplate).where(ResumeTemplate.is_active == True)
        if category:
            stmt = stmt.where(ResumeTemplate.category == category)
        stmt = stmt.order_by(ResumeTemplate.usage_count.desc())

        result = await self.db.execute(stmt)
        templates = result.scalars().all()
        return [{
            "id": t.id, "name": t.name, "description": t.description,
            "category": t.category, "layout": t.layout,
            "preview_url": t.preview_url, "usage_count": t.usage_count,
            "created_at": t.created_at,
        } for t in templates]

    async def use_template(self, resume_id: uuid.UUID, template_id: uuid.UUID) -> bool:
        from .models import ResumeTemplate
        from sqlalchemy import select, update

        result = await self.db.execute(
            select(ResumeTemplate).where(ResumeTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            raise ValueError("Template not found")

        template.usage_count = (template.usage_count or 0) + 1
        await self.db.commit()
        return True

    async def seed_default_templates(self) -> None:
        """初始化默认模板（首次运行时调用）。"""
        from .models import ResumeTemplate

        existing = await self.db.execute(
            __import__("sqlalchemy").select(__import__("sqlalchemy").func.count())
            .select_from(ResumeTemplate)
        )
        if existing.scalar() > 0:
            return

        defaults = [
            {"name": "Classic Professional", "category": "general",
             "description": "Traditional single-column layout, ideal for corporate roles.",
             "layout": {"sections": ["summary", "experience", "education", "skills"], "columns": 1}},
            {"name": "Modern Tech", "category": "tech",
             "description": "Clean two-column layout with skills sidebar, optimized for tech roles.",
             "layout": {"sections": ["summary", "skills", "experience", "projects", "education"], "columns": 2}},
            {"name": "Creative Portfolio", "category": "creative",
             "description": "Visual layout with project showcase section.",
             "layout": {"sections": ["summary", "experience", "projects", "education", "skills"], "columns": 1}},
            {"name": "Executive", "category": "executive",
             "description": "Professional layout emphasizing leadership and achievements.",
             "layout": {"sections": ["summary", "achievements", "experience", "education", "skills"], "columns": 1}},
        ]
        for tmpl in defaults:
            self.db.add(ResumeTemplate(**tmpl, is_active=True))
        await self.db.commit()


class ScoreHistoryService:
    """ATS 评分历史管理。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_score(self, resume_id: uuid.UUID, score: float,
                           breakdown: dict | None = None,
                           missing_keywords: list[str] | None = None,
                           suggestions: list[str] | None = None) -> None:
        from .models import ATSScoreRecord

        record = ATSScoreRecord(
            resume_id=resume_id, score=score, breakdown=breakdown,
            missing_keywords=missing_keywords, suggestions=suggestions,
        )
        self.db.add(record)
        await self.db.commit()

    async def get_history(self, resume_id: uuid.UUID) -> dict[str, Any]:
        from .models import ATSScoreRecord
        from sqlalchemy import select

        result = await self.db.execute(
            select(ATSScoreRecord)
            .where(ATSScoreRecord.resume_id == resume_id)
            .order_by(ATSScoreRecord.created_at.asc())
        )
        records = result.scalars().all()

        if not records:
            return {"resume_id": resume_id, "history": [], "latest_score": None,
                    "avg_score": None, "trend": "stable"}

        scores = [r.score for r in records]
        avg = sum(scores) / len(scores)
        latest = scores[-1]

        # 趋势判断：比较最近 3 次与之前的变化
        if len(scores) >= 2:
            recent = scores[-min(3, len(scores)):]
            if len(recent) >= 2 and recent[-1] > recent[0] + 2:
                trend = "improving"
            elif len(recent) >= 2 and recent[-1] < recent[0] - 2:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "resume_id": resume_id,
            "history": [{
                "id": r.id, "score": r.score,
                "breakdown": r.breakdown,
                "missing_keywords": r.missing_keywords,
                "suggestions": r.suggestions,
                "created_at": r.created_at,
            } for r in records],
            "latest_score": latest,
            "avg_score": round(avg, 1),
            "trend": trend,
        }

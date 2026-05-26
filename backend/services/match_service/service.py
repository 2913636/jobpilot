"""Match Service — 职位搜索、匹配、对比、职业路径、薪资预测的业务逻辑层。"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import CrawlTask, Job, MatchResult
from .search import JobSearchService
from .matcher import MatchEngine
from .comparator import JobComparator
from .career import CareerPathService
from .salary import SalaryPredictor


class MatchService:
    """职位搜索 + 匹配评估的统一入口。"""

    def __init__(self, db: AsyncSession, es_client=None, milvus=None, neo4j_driver=None):
        self.db = db
        self.search_svc = JobSearchService(es_client) if es_client else None
        self.matcher = MatchEngine(milvus) if milvus else None
        self.comparator = JobComparator(db)
        self.career_svc = CareerPathService(neo4j_driver) if neo4j_driver else None
        self.salary_svc = SalaryPredictor()

    # ── 职位 CRUD ─────────────────────────────────────────────

    async def create_job(self, data: dict[str, Any]) -> Job:
        job = Job(**data)
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        if self.search_svc:
            try:
                await self.search_svc.index_job({
                    "id": str(job.id), "title": job.title, "company": job.company,
                    "description": job.description, "location": job.location,
                    "remote": job.remote, "salary_min": job.salary_min,
                    "salary_max": job.salary_max, "skills": job.skills or [],
                    "experience_level": job.experience_level, "source": job.source,
                    "is_active": job.is_active, "created_at": str(job.created_at),
                })
            except Exception:
                pass
        return job

    async def get_job(self, job_id: uuid.UUID) -> Job | None:
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def get_jobs_by_ids(self, job_ids: list[uuid.UUID]) -> list[Job]:
        result = await self.db.execute(select(Job).where(Job.id.in_(job_ids)))
        return list(result.scalars().all())

    async def list_jobs(self, page: int = 1, page_size: int = 20) -> tuple[list[Job], int]:
        all_jobs = await self.db.execute(select(Job).where(Job.is_active == True))
        total = len(list(all_jobs.scalars().all()))
        result = await self.db.execute(
            select(Job).where(Job.is_active == True)
            .offset((page - 1) * page_size).limit(page_size)
            .order_by(Job.created_at.desc())
        )
        return list(result.scalars().all()), total

    # ── 搜索 ─────────────────────────────────────────────────

    async def search(self, params: dict[str, Any]) -> dict[str, Any]:
        if not self.search_svc:
            jobs, total = await self.list_jobs(params.get("page", 1), params.get("page_size", 20))
            return {"items": [self._job_dict(j) for j in jobs], "total": total,
                    "page": params.get("page", 1), "page_size": params.get("page_size", 20)}
        return await self.search_svc.search(**params)

    # ── 匹配 ─────────────────────────────────────────────────

    async def evaluate_match(self, resume_text: str, top_k: int = 20) -> dict[str, Any]:
        if not self.matcher:
            return {"items": [], "total_candidates": 0, "elapsed_ms": 0}
        results = await self.matcher.evaluate(resume_text, top_k)
        items: list[dict] = []
        for r in results:
            job_id = r.get("job_id")
            job = None
            if job_id:
                try:
                    job = await self.get_job(uuid.UUID(str(job_id)))
                except Exception:
                    pass
            items.append({
                "job": self._job_dict(job) if job else {"id": job_id, "title": r.get("title", ""), "company": r.get("company", "")},
                "score": r.get("score", 0), "vector_score": r.get("vector_score"),
                "rerank_score": r.get("rerank_score"),
                "matched_skills": r.get("matched_skills", []),
                "skill_gaps": r.get("skill_gaps", []),
            })
        return {"items": items, "total_candidates": len(results), "elapsed_ms": 0}

    async def save_match(self, resume_id: uuid.UUID, job_id: uuid.UUID,
                          score: float, matched: list[str], gaps: list[str]) -> MatchResult:
        mr = MatchResult(resume_id=resume_id, job_id=job_id, score=score,
                         matched_skills=matched, skill_gaps=gaps)
        self.db.add(mr)
        await self.db.commit()
        await self.db.refresh(mr)
        return mr

    # ── 对比 ─────────────────────────────────────────────────

    async def compare_jobs(self, job_ids: list[uuid.UUID]) -> dict[str, Any]:
        jobs = await self.get_jobs_by_ids(job_ids)
        return await self.comparator.compare([self._job_dict(j) for j in jobs])

    # ── 职业路径 ─────────────────────────────────────────────

    async def find_career_path(self, from_skills: list[str], target_role: str) -> dict[str, Any]:
        if self.career_svc:
            return await self.career_svc.find_path(from_skills, target_role)
        return CareerPathService(None)._fallback_path(from_skills, target_role)

    # ── 薪资预测 ────────────────────────────────────────────

    async def predict_salary(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self.salary_svc.predict(params)

    # ── 爬虫 ────────────────────────────────────────────────

    async def create_crawl_task(self, source: str, keyword: str,
                                 location: str = "") -> CrawlTask:
        task = CrawlTask(source=source, keyword=keyword, location=location)
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_crawl_task(self, task_id: uuid.UUID) -> CrawlTask | None:
        result = await self.db.execute(select(CrawlTask).where(CrawlTask.id == task_id))
        return result.scalar_one_or_none()

    # ── 工具 ─────────────────────────────────────────────────

    def _job_dict(self, job: Job) -> dict[str, Any]:
        return {
            "id": job.id, "title": job.title, "company": job.company,
            "description": job.description, "location": job.location,
            "remote": job.remote, "salary_min": job.salary_min,
            "salary_max": job.salary_max, "salary_currency": job.salary_currency,
            "skills": job.skills or [], "experience_level": job.experience_level,
            "education_level": job.education_level, "employment_type": job.employment_type,
            "source": job.source, "source_url": job.source_url,
            "is_active": job.is_active, "created_at": job.created_at,
        }

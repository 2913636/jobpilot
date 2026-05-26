"""Match Service — 职位搜索、匹配评估、对比、职业路径、薪资预测、爬虫调度。"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth import get_current_user
from common.db import engine, get_db
from common.es import get_es_client
from common.milvus import get_milvus_client
from common.neo4j import get_neo4j_driver

from .models import Base
from .schemas import (
    CareerPathRequest,
    CareerPathResponse,
    CareerStep,
    CrawlRequest,
    CrawlTaskResponse,
    ErrorResponse,
    JobCompareRequest,
    JobCompareResponse,
    CompareDimension,
    JobListResponse,
    JobResponse,
    JobSearchRequest,
    MatchEvaluateRequest,
    MatchEvaluateResponse,
    MatchItem,
    SalaryPredictRequest,
    SalaryPredictResponse,
)
from .service import MatchService
from common.cors import setup_cors
from common.exceptions import setup_exception_handlers

app = FastAPI(
    title="Match Service",
    title="Match Service",
    description="""职位搜索、智能匹配、多维度对比、职业路径规划、薪资预测。

## Curl Examples
```bash
# Search jobs
curl ':8003/jobs/search?q=python&location=Shanghai'

# Match evaluation
curl -X POST :8003/match/evaluate -H 'Content-Type: application/json' \\
  -d '{"resume_text": "Python developer...", "top_k": 10}'
```
""",
    version="1.0.0",
    root_path="/api/matches",
    responses={401: {"model": ErrorResponse}, 422: {"description": "Validation error"}},
)


setup_cors(app)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 初始化 ES 索引
    try:
        es = await get_es_client()
        from .search import JobSearchService
        await JobSearchService(es).ensure_index()
    except Exception:
        pass


@app.get("/health", tags=["System"], include_in_schema=False)
async def health():
    return {"status": "ok", "service": "match-service"}


# ── 职位搜索 ─────────────────────────────────────────────────────

@app.get("/jobs/search", response_model=JobListResponse, tags=["Search"],
         summary="搜索职位")
async def search_jobs(
    user: dict[str, Any] = Depends(get_current_user),
    q: str = Query("", description="搜索关键词"),
    location: str | None = Query(None),
    remote: bool | None = Query(None),
    experience_level: str | None = Query(None),
    salary_min: float | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """从 Elasticsearch 全文搜索职位，支持多种过滤条件和分页。"""
    es = await get_es_client()
    svc = MatchService(db, es_client=es)
    result = await svc.search({
        "q": q, "location": location, "remote": remote,
        "experience_level": experience_level, "salary_min": salary_min,
        "page": page, "page_size": page_size,
    })
    # 将 ES 结果映射为 JobResponse
    items = []
    for item in result.get("items", []):
        items.append(JobResponse(
            id=item.get("id"), title=item.get("title", ""),
            company=item.get("company", ""), description=item.get("description", ""),
            location=item.get("location"), remote=item.get("remote", False),
            salary_min=item.get("salary_min"), salary_max=item.get("salary_max"),
            salary_currency=item.get("salary_currency"),
            skills=item.get("skills", []),
            experience_level=item.get("experience_level"),
            education_level=item.get("education_level"),
            employment_type=item.get("employment_type"),
            source=item.get("source", ""), source_url=item.get("source_url"),
            is_active=item.get("is_active", True),
            created_at=item.get("created_at"),
        ))
    return JobListResponse(
        items=items, total=result.get("total", 0),
        page=result.get("page", page), page_size=result.get("page_size", page_size),
    )


# ── 匹配评估 ────────────────────────────────────────────────────

@app.post("/match/evaluate", response_model=MatchEvaluateResponse, tags=["Match"],
          summary="评估简历-职位匹配度")
async def evaluate_match(
    body: MatchEvaluateRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MatchEvaluateResponse:
    """使用向量检索 + 交叉编码器计算简历与职位库的匹配度。

    流程：text → sentence-embedding → Milvus top-50 → cross-encoder rerank → top-k
    """
    resume_text = body.resume_text
    if not resume_text and body.user_id:
        # 从 user-service 获取 profile
        resume_text = f"User profile for {body.user_id}"

    if not resume_text:
        raise HTTPException(status_code=400, detail="需要 resume_text 或 user_id")

    milvus = get_milvus_client()
    svc = MatchService(db, milvus=milvus)
    result = await svc.evaluate_match(resume_text, body.top_k)

    items = []
    for r in result.get("items", []):
        job_data = r.get("job", {})
        items.append(MatchItem(
            job=JobResponse(
                id=job_data.get("id", uuid.uuid4()),
                title=job_data.get("title", ""), company=job_data.get("company", ""),
                description=job_data.get("description", ""),
                location=job_data.get("location"), remote=job_data.get("remote", False),
                salary_min=job_data.get("salary_min"), salary_max=job_data.get("salary_max"),
                salary_currency=job_data.get("salary_currency"),
                skills=job_data.get("skills", []),
                experience_level=job_data.get("experience_level"),
                education_level=job_data.get("education_level"),
                employment_type=job_data.get("employment_type"),
                source=job_data.get("source", ""), source_url=job_data.get("source_url"),
                is_active=job_data.get("is_active", True),
                created_at=job_data.get("created_at"),
            ),
            score=r.get("score", 0), vector_score=r.get("vector_score"),
            rerank_score=r.get("rerank_score"),
            matched_skills=r.get("matched_skills", []),
            skill_gaps=r.get("skill_gaps", []),
        ))
    return MatchEvaluateResponse(
        items=items, total_candidates=result.get("total_candidates", 0),
        elapsed_ms=result.get("elapsed_ms", 0),
    )


# ── 岗位对比 ────────────────────────────────────────────────────

@app.post("/match/compare", response_model=JobCompareResponse, tags=["Compare"],
          summary="多岗位多维度对比")
async def compare_jobs(
    body: JobCompareRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobCompareResponse:
    """对比多个岗位，从技能成长、薪资、WLB、前景、地点五个维度分析。

    返回 Markdown 报告 + 结构化雷达图数据。
    """
    svc = MatchService(db)
    result = await svc.compare_jobs(body.job_ids)
    return JobCompareResponse(
        report_markdown=result["report_markdown"],
        dimensions=[CompareDimension(**d) for d in result["dimensions"]],
        radar_data=result["radar_data"],
        job_names=result["job_names"],
    )


# ── 职业路径 ────────────────────────────────────────────────────

@app.get("/career/path", response_model=CareerPathResponse, tags=["Career"],
         summary="职业路径模拟")
async def career_path(
    user: dict[str, Any] = Depends(get_current_user),
    from_skills: list[str] = Query(..., description="当前技能列表"),
    target_role: str = Query(..., description="目标角色"),
) -> CareerPathResponse:
    """基于 Neo4j 技能图谱，计算从当前技能到目标角色的最短学习路径。"""
    driver = get_neo4j_driver()
    svc = MatchService(None, neo4j_driver=driver)
    result = await svc.find_career_path(from_skills, target_role)
    return CareerPathResponse(
        path=[CareerStep(**s) for s in result["path"]],
        total_months=result["total_months"],
        alternative_roles=result.get("alternative_roles", []),
    )


# ── 薪资预测 ────────────────────────────────────────────────────

@app.get("/salary/predict", response_model=SalaryPredictResponse, tags=["Salary"],
         summary="市场薪资预测")
async def predict_salary(
    user: dict[str, Any] = Depends(get_current_user),
    title: str = Query(..., description="职位名称"),
    location: str = Query("Beijing"),
    experience_years: float = Query(..., ge=0, le=40),
    education_level: str = Query("bachelor"),
    skills: list[str] = Query(default_factory=list),
    company_size: str | None = Query(None),
    industry: str | None = Query(None),
) -> SalaryPredictResponse:
    """基于 XGBoost 模型预测职位的市场薪资范围。"""
    svc = MatchService(None)
    result = await svc.predict_salary({
        "title": title, "location": location, "experience_years": experience_years,
        "education_level": education_level, "skills": skills,
        "company_size": company_size, "industry": industry,
    })
    return SalaryPredictResponse(**result)


# ── 爬虫触发 ────────────────────────────────────────────────────

@app.post("/crawl", response_model=CrawlTaskResponse, status_code=status.HTTP_201_CREATED,
          tags=["Crawl"], summary="触发职位爬虫")
async def trigger_crawl(
    body: CrawlRequest,
    background_tasks: BackgroundTasks,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CrawlTaskResponse:
    """异步触发职位爬虫任务（Boss直聘 / LinkedIn）。

    爬虫在后台线程中运行，结果通过 Pipeline 写入 ES 和 PG。
    """
    svc = MatchService(db)
    task = await svc.create_crawl_task(body.source, body.keyword, body.location)

    # 后台运行爬虫
    background_tasks.add_task(_run_crawler, task.id, body.source, body.keyword,
                               body.location, body.max_pages)

    return CrawlTaskResponse.model_validate(task)


async def _run_crawler(task_id: uuid.UUID, source: str, keyword: str,
                        location: str, max_pages: int):
    """后台执行 Scrapy 爬虫。"""
    from sqlalchemy import update as sql_update
    from common.db import async_session_factory
    from .models import CrawlTask
    from datetime import datetime

    async with async_session_factory() as db:
        try:
            await db.execute(
                sql_update(CrawlTask).where(CrawlTask.id == task_id)
                .values(status="running")
            )
            await db.commit()

            from scrapy.crawler import CrawlerProcess
            from scrapy.utils.project import get_project_settings

            settings = get_project_settings()
            spider_name = "boss" if source == "boss" else "linkedin"

            process = CrawlerProcess(settings)
            process.crawl(spider_name, keyword=keyword, location=location, max_pages=max_pages)
            process.start()

            await db.execute(
                sql_update(CrawlTask).where(CrawlTask.id == task_id)
                .values(status="done", finished_at=datetime.utcnow())
            )
            await db.commit()

        except Exception as e:
            await db.execute(
                sql_update(CrawlTask).where(CrawlTask.id == task_id)
                .values(status="failed", error_msg=str(e), finished_at=datetime.utcnow())
            )
            await db.commit()

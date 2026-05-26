"""Resume Service — Parsing, Generation, Scoring, and Version Management."""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth import get_current_user
from common.db import engine, get_db

from .models import Base
from .schemas import (
    ABTestRequest,
    ABTestResponse,
    ABTestResultUpdate,
    ATSScoreRequest,
    ATSScoreResponse,
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
    ParseResponse,
    ResumeDetailResponse,
    ResumeListItem,
    ResumeVersionResponse,
)
from .service import (
    ABTestService,
    GenerateService,
    ParseService,
    ResumeService,
    ScoreService,
    fetch_jd_text,
    fetch_user_profile,
)
from common.cors import setup_cors
from common.exceptions import setup_exception_handlers

app = FastAPI(
    title="Resume Service",
    description="""Resume parsing, AI generation, ATS scoring, and version management.

## Curl Examples
```bash
# Parse resume
curl -X POST :8002/parse -H 'Authorization: Bearer $TOKEN' -F 'file=@resume.pdf'

# ATS Score
curl -X POST :8002/score -H 'Authorization: Bearer $TOKEN' -H 'Content-Type: application/json' \\
  -d '{"text": "Python developer with 5 years experience..."}'
```
""",
    version="1.0.0",
    root_path="/api/resumes",
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        422: {"description": "Validation error"},
    },
)


setup_cors(app)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health", tags=["System"], include_in_schema=False)
async def health():
    return {"status": "ok", "service": "resume-service"}


@app.get("/", tags=["System"], include_in_schema=False)
async def root():
    return {"service": "resume-service", "version": "1.0.0"}


# ── List Resumes ──────────────────────────────────────────────────

@app.get(
    "",
    response_model=list[ResumeListItem],
    tags=["Resumes"],
    summary="List user resumes",
)
async def list_resumes(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResumeListItem]:
    """Return all resumes belonging to the authenticated user, newest first."""
    svc = ResumeService(db)
    resumes = await svc.list_by_user(uuid.UUID(user["sub"]))
    return [ResumeListItem.model_validate(r) for r in resumes]


@app.get(
    "/{resume_id}",
    response_model=ResumeDetailResponse,
    tags=["Resumes"],
    summary="Get resume detail",
    responses={404: {"model": ErrorResponse, "description": "Resume not found"}},
)
async def get_resume(
    resume_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeDetailResponse:
    """Return full resume detail including versions and A/B tests."""
    svc = ResumeService(db)
    resume = await svc.get(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return ResumeDetailResponse.model_validate(resume)


# ── Parse ─────────────────────────────────────────────────────────

@app.post(
    "/parse",
    response_model=ParseResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Parse"],
    summary="Parse a resume file",
    responses={400: {"model": ErrorResponse, "description": "Unsupported file type"}},
)
async def parse_resume(
    file: UploadFile = File(..., description="Resume file (PDF, DOCX, TXT)"),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ParseResponse:
    """Upload and parse a resume file.

    Extracts text, segments sections, identifies entities (name, email, phone),
    and returns structured JSON.  Supports PDF, DOCX, and TXT formats.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".pdf", ".docx", ".doc", ".txt", ".md"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    svc = ParseService(db)
    return await svc.parse(uuid.UUID(user["sub"]), file.filename, data)


# ── Generate ──────────────────────────────────────────────────────

@app.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Generate"],
    summary="Generate a tailored resume",
)
async def generate_resume(
    body: GenerateRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    """Generate a tailored resume from a user profile and job description.

    Pipeline: JD analysis → experience selection → STAR rewriting → assembly.
    Calls user-service and match-service internally for profile and JD data.
    """
    jd_text = await fetch_jd_text(body.job_id)
    profile = await fetch_user_profile(body.profile_id)

    svc = GenerateService(db)
    return await svc.generate(uuid.UUID(user["sub"]), body, jd_text, profile)


# ── ATS Score ─────────────────────────────────────────────────────

@app.post(
    "/score",
    response_model=ATSScoreResponse,
    tags=["Score"],
    summary="Score resume for ATS compatibility",
)
async def score_resume(
    body: ATSScoreRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ATSScoreResponse:
    """Evaluate a resume against 35 ATS rules and return a 0-100 score.

    Categories: format, keywords, content, structure, impact.
    Also returns missing JD keywords and actionable improvement suggestions.
    """
    svc = ScoreService(db)
    try:
        return await svc.score(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Versions ──────────────────────────────────────────────────────

@app.get(
    "/{resume_id}/versions",
    response_model=list[ResumeVersionResponse],
    tags=["Versions"],
    summary="List resume versions",
)
async def list_versions(
    resume_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResumeVersionResponse]:
    """Return all versions of a resume, newest first."""
    svc = ResumeService(db)
    resume = await svc.get(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    versions = await svc.get_versions(resume_id)
    return [ResumeVersionResponse.model_validate(v) for v in versions]


# ── A/B Test ──────────────────────────────────────────────────────

@app.post(
    "/{resume_id}/ab-test",
    response_model=ABTestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["A/B Test"],
    summary="Create an A/B test",
)
async def create_ab_test(
    resume_id: uuid.UUID,
    body: ABTestRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ABTestResponse:
    """Start an A/B test comparing two resume versions."""
    svc = ResumeService(db)
    resume = await svc.get(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    ab_svc = ABTestService(db)
    test = await ab_svc.create(resume_id, body)
    return ABTestResponse.model_validate(test)


@app.put(
    "/{resume_id}/ab-test/{test_id}",
    response_model=ABTestResponse,
    tags=["A/B Test"],
    summary="Update A/B test results",
)
async def update_ab_test(
    resume_id: uuid.UUID,
    test_id: uuid.UUID,
    body: ABTestResultUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ABTestResponse:
    """Report A/B test results and mark the test as completed."""
    ab_svc = ABTestService(db)
    test = await ab_svc.update_results(resume_id, test_id, body)
    if not test:
        raise HTTPException(status_code=404, detail="A/B test not found")
    return ABTestResponse.model_validate(test)


# ── Import ────────────────────────────────────────────────────────

from .schemas import ImportRequest, ImportResponse, TemplateResponse, ScoreHistoryResponse, ScoreTrendResponse
from .service import ImportService, TemplateService, ScoreHistoryService


@app.post("/import/linkedin", response_model=ImportResponse, tags=["Import"],
          summary="Import from LinkedIn")
async def import_linkedin_endpoint(
    body: ImportRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImportResponse:
    svc = ImportService(db)
    try:
        result = await svc.import_from_url(uuid.UUID(user["sub"]), body.url)
        return ImportResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/import/github", response_model=ImportResponse, tags=["Import"],
          summary="Import from GitHub")
async def import_github_endpoint(
    body: ImportRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImportResponse:
    svc = ImportService(db)
    try:
        result = await svc.import_from_url(uuid.UUID(user["sub"]), body.url)
        return ImportResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Templates ─────────────────────────────────────────────────────

@app.get("/templates", response_model=list[TemplateResponse], tags=["Templates"],
         summary="List resume templates")
async def list_templates(
    category: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TemplateResponse]:
    svc = TemplateService(db)
    templates = await svc.list_templates(category)
    return [TemplateResponse(**t) for t in templates]


@app.post("/templates/seed", tags=["Templates"], summary="Seed default templates")
async def seed_templates(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = TemplateService(db)
    await svc.seed_default_templates()
    return {"message": "Default templates seeded"}


# ── Score History ─────────────────────────────────────────────────

@app.get("/score/history", response_model=ScoreTrendResponse, tags=["Score"],
         summary="ATS score history")
async def score_history(
    resume_id: uuid.UUID = Query(...),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScoreTrendResponse:
    svc = ScoreHistoryService(db)
    result = await svc.get_history(resume_id)
    return ScoreTrendResponse(
        resume_id=result["resume_id"],
        history=[ScoreHistoryResponse(**h) for h in result["history"]],
        latest_score=result["latest_score"],
        avg_score=result["avg_score"],
        trend=result["trend"],
    )

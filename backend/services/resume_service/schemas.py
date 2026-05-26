from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Structured Resume Content ─────────────────────────────────────

class ExperienceEntry(BaseModel):
    company: str = Field(..., description="Company name")
    title: str = Field(..., description="Job title")
    start_date: str = Field(..., description="Start date (YYYY-MM)")
    end_date: str | None = Field(None, description="End date, null if current")
    description: str | None = Field(None, description="Role description")
    highlights: list[str] = Field(default_factory=list, description="Quantified achievements (STAR)")
    current: bool = False


class EducationEntry(BaseModel):
    school: str
    degree: str
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    gpa: str | None = None


class ProjectEntry(BaseModel):
    name: str
    description: str | None = None
    url: str | None = None
    highlights: list[str] = Field(default_factory=list)


class ResumeContent(BaseModel):
    """Canonical structured resume representation."""
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


# ── Parse ─────────────────────────────────────────────────────────

class ParseRequest(BaseModel):
    """Resume parsing request — the file is passed as multipart form data."""


class ParseResponse(BaseModel):
    resume_id: UUID = Field(..., description="ID of the created resume record")
    content: ResumeContent = Field(..., description="Parsed structured content")
    raw_text: str = Field(..., description="Extracted raw text for inspection")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Entity extraction confidence")


# ── Generate ──────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    """Request to generate a tailored resume from a user profile."""
    profile_id: UUID = Field(..., description="Source user profile ID")
    job_id: UUID = Field(..., description="Target job ID")
    title: str = Field("Generated Resume", min_length=1, max_length=255)


class GenerateResponse(BaseModel):
    resume_id: UUID
    content: ResumeContent
    jd_keywords: list[str] = Field(default_factory=list, description="Extracted JD keywords")
    match_score: float = Field(0.0, description="Profile-to-JD match score")


# ── ATS Score ─────────────────────────────────────────────────────

class ATSScoreRequest(BaseModel):
    resume_id: UUID = Field(..., description="Resume ID to score, or pass text directly")
    text: str | None = Field(None, description="Raw resume text (takes precedence over resume_id)")


class ATSScoreResponse(BaseModel):
    score: float = Field(..., ge=0.0, le=100.0, description="Overall ATS score (0-100)")
    breakdown: dict[str, float] = Field(
        ..., description="Category scores: format, keywords, content, structure, impact"
    )
    missing_keywords: list[str] = Field(..., description="Keywords found in JD but missing in resume")
    suggestions: list[str] = Field(..., description="Actionable improvement suggestions")


# ── Version Management ────────────────────────────────────────────

class ResumeVersionResponse(BaseModel):
    id: UUID
    resume_id: UUID
    version_number: int
    content: dict[str, Any]
    changes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeListItem(BaseModel):
    id: UUID
    title: str
    source_type: str
    status: str
    ats_score: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeDetailResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    content: dict[str, Any]
    source_type: str
    status: str
    ats_score: float | None
    job_id: UUID | None
    file_url: str | None
    created_at: datetime
    updated_at: datetime
    versions: list[ResumeVersionResponse] = Field(default_factory=list)
    ab_tests: list["ABTestResponse"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ABTestRequest(BaseModel):
    variant_a_id: UUID = Field(..., description="First resume version ID")
    variant_b_id: UUID = Field(..., description="Second resume version ID")
    metric: str = Field("response_rate", description="Metric to compare")


class ABTestResponse(BaseModel):
    id: UUID
    resume_id: UUID
    variant_a_id: UUID
    variant_b_id: UUID
    metric: str
    results: dict[str, Any] | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ABTestResultUpdate(BaseModel):
    results: dict[str, Any] = Field(..., description="A/B test outcome data")


# ── Import ────────────────────────────────────────────────────────

class ImportRequest(BaseModel):
    url: str = Field(..., description="LinkedIn/GitHub 公开页面 URL")


class ImportResponse(BaseModel):
    resume_id: UUID
    content: ResumeContent
    source: str = Field(..., description="linkedin / github")


# ── Templates ─────────────────────────────────────────────────────

class TemplateResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    category: str
    layout: dict[str, Any]
    preview_url: str | None
    usage_count: int
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Score History ─────────────────────────────────────────────────

class ScoreHistoryResponse(BaseModel):
    id: UUID
    score: float
    breakdown: dict[str, float] | None
    missing_keywords: list[str] | None
    suggestions: list[str] | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ScoreTrendResponse(BaseModel):
    resume_id: UUID
    history: list[ScoreHistoryResponse]
    latest_score: float | None
    avg_score: float | None
    trend: str = Field("stable", description="improving / declining / stable")


# ── Error ────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str

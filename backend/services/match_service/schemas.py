from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class JobResponse(BaseModel):
    id: UUID
    title: str
    company: str
    description: str
    location: str | None
    remote: bool
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    skills: list[str] | None
    experience_level: str | None
    education_level: str | None
    employment_type: str | None
    source: str
    source_url: str | None
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    items: list[JobResponse]
    total: int
    page: int
    page_size: int


class JobSearchRequest(BaseModel):
    q: str = Field("", description="搜索关键词")
    location: str | None = None
    remote: bool | None = None
    experience_level: str | None = None
    salary_min: float | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class MatchEvaluateRequest(BaseModel):
    resume_text: str | None = Field(None, description="简历文本")
    user_id: UUID | None = Field(None, description="从用户档案提取")
    top_k: int = Field(20, ge=1, le=100)


class MatchItem(BaseModel):
    job: JobResponse
    score: float
    vector_score: float | None = None
    rerank_score: float | None = None
    matched_skills: list[str] = Field(default_factory=list)
    skill_gaps: list[str] = Field(default_factory=list)


class MatchEvaluateResponse(BaseModel):
    items: list[MatchItem]
    total_candidates: int
    elapsed_ms: float


class JobCompareRequest(BaseModel):
    job_ids: list[UUID] = Field(..., min_length=2, max_length=5)


class CompareDimension(BaseModel):
    name: str
    scores: dict[str, float]
    analysis: str = ""


class JobCompareResponse(BaseModel):
    report_markdown: str
    dimensions: list[CompareDimension]
    radar_data: dict[str, list[float]]
    job_names: list[str]


class CareerPathRequest(BaseModel):
    from_skills: list[str] = Field(..., min_length=1)
    target_role: str = Field(..., min_length=1)


class CareerStep(BaseModel):
    step: int
    action: str
    skills_to_acquire: list[str] = Field(default_factory=list)
    estimated_months: int = 0
    resources: list[str] = Field(default_factory=list)


class CareerPathResponse(BaseModel):
    path: list[CareerStep]
    total_months: int
    alternative_roles: list[str] = Field(default_factory=list)


class SalaryPredictRequest(BaseModel):
    title: str
    location: str = "Beijing"
    experience_years: float = Field(..., ge=0, le=40)
    education_level: str = "bachelor"
    skills: list[str] = Field(default_factory=list)
    company_size: str | None = None
    industry: str | None = None


class SalaryPredictResponse(BaseModel):
    predicted_min: float
    predicted_max: float
    predicted_median: float
    currency: str = "CNY"
    confidence: float
    factors: dict[str, float] = Field(default_factory=dict)


class CrawlRequest(BaseModel):
    source: str = "boss"
    keyword: str
    location: str = ""
    max_pages: int = Field(3, ge=1, le=20)


class CrawlTaskResponse(BaseModel):
    id: UUID
    source: str
    keyword: str
    location: str | None
    status: str
    jobs_found: int
    created_at: datetime
    finished_at: datetime | None
    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    detail: str

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── 面试会话 ──────────────────────────────────────────────────────

class StartInterviewRequest(BaseModel):
    user_id: UUID | None = None
    job_id: UUID | None = None
    application_id: UUID | None = None


class StartInterviewResponse(BaseModel):
    session_id: UUID
    room_name: str
    livekit_token: str
    livekit_url: str = "ws://localhost:7880"


class TranscriptEntry(BaseModel):
    speaker: str = Field(..., description="user / interviewer")
    text: str
    timestamp: str


class EmotionFrame(BaseModel):
    timestamp: str
    smile_ratio: float = Field(0.0, ge=0, le=1)
    eye_contact: float = Field(0.0, ge=0, le=1)
    head_stability: float = Field(0.0, ge=0, le=1)
    confidence_score: float = Field(0.0, ge=0, le=100)


class VoiceMetrics(BaseModel):
    timestamp: str
    speech_rate: float = Field(..., description="语速（词/分钟）")
    pause_count: int = 0
    filler_words: list[str] = Field(default_factory=list)
    volume: float = 0.0


class InterviewSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    job_id: UUID | None
    room_name: str
    status: str
    transcript: list[dict[str, Any]] | None
    emotions: list[dict[str, Any]] | None
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── 面试报告 ──────────────────────────────────────────────────────

class ReportResponse(BaseModel):
    id: UUID
    session_id: UUID
    overall_score: float
    scores: dict[str, float]
    strengths: list[str] | None
    weaknesses: list[str] | None
    recommendations: list[dict[str, Any]] | None
    detailed_feedback: str | None
    question_results: list[dict[str, Any]] | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── 题库 ──────────────────────────────────────────────────────────

class QuestionCreate(BaseModel):
    title: str
    content: str
    category: str = "general"
    difficulty: str = "medium"
    tags: list[str] = Field(default_factory=list)
    answer_guide: str | None = None


class QuestionResponse(BaseModel):
    id: UUID
    author_id: UUID
    title: str
    content: str
    category: str
    difficulty: str
    tags: list[str] | None
    answer_guide: str | None
    upvotes: int
    downvotes: int
    created_at: datetime
    model_config = {"from_attributes": True}


class VoteRequest(BaseModel):
    vote_type: str = Field(..., description="up 或 down")


class QuestionListResponse(BaseModel):
    items: list[QuestionResponse]
    total: int
    page: int
    page_size: int


# ── 错误 ──────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── 申请 ──────────────────────────────────────────────────────────

class ApplicationCreate(BaseModel):
    job_id: UUID | None = None
    resume_id: UUID | None = None
    company: str | None = Field(None, description="公司名")
    title: str | None = Field(None, description="职位名")
    notes: str = ""
    source_url: str | None = None


class ApplicationUpdate(BaseModel):
    status: str | None = Field(None, description="新状态（需符合状态机规则）")
    notes: str | None = None
    company: str | None = None
    title: str | None = None


class TimelineEntry(BaseModel):
    status: str
    timestamp: str
    note: str = ""


class ApplicationResponse(BaseModel):
    id: UUID
    user_id: UUID
    job_id: UUID
    resume_id: UUID | None
    company: str | None
    title: str | None
    status: str
    notes: str
    timeline: list[dict[str, Any]] | None
    source_url: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ApplicationListResponse(BaseModel):
    items: list[ApplicationResponse]
    total: int
    page: int
    page_size: int


class StatusTransition(BaseModel):
    """状态转换结果。"""
    success: bool
    from_status: str
    to_status: str
    allowed: bool
    message: str = ""


# ── 智能填表 ──────────────────────────────────────────────────────

class FillFormRequest(BaseModel):
    url: str = Field(..., description="目标表单页面 URL")
    user_id: UUID = Field(..., description="用户 ID（用于获取档案）")
    page_html: str | None = Field(None, description="页面 HTML（如果已抓取）")


class FieldMapping(BaseModel):
    form_field: str = Field(..., description="目标表单字段名（如 input[name='email']）")
    profile_key: str = Field(..., description="用户档案键（如 email, full_name）")
    suggested_value: str = Field(..., description="建议填入的值")
    confidence: float = Field(0.0, ge=0, le=1, description="匹配置信度")
    field_type: str = "text"


class FillFormResponse(BaseModel):
    url: str
    domain: str
    mappings: list[FieldMapping]
    template_id: UUID | None = None


# ── 沟通记录 ──────────────────────────────────────────────────────

class ChatSyncRequest(BaseModel):
    platform: str = Field(..., description="招聘平台名（boss/linkedin/lagou/...）")
    application_id: UUID | None = None
    direction: str = Field("in", description="消息方向（in/out）")
    sender_name: str | None = None
    content: str = Field(..., description="消息内容")
    raw_payload: dict[str, Any] | None = None


class CommunicationResponse(BaseModel):
    id: UUID
    application_id: UUID | None
    user_id: UUID
    platform: str
    direction: str
    sender_name: str | None
    content: str
    synced_at: datetime
    model_config = {"from_attributes": True}


# ── WebSocket 指令 ────────────────────────────────────────────────

class WSFillCommand(BaseModel):
    """WebSocket 发送给浏览器扩展的填充指令。"""
    command: str = "fill_form"
    url: str
    fields: list[FieldMapping]


# ── 错误 ──────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str

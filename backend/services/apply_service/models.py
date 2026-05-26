"""Apply Service 数据模型 — 申请、沟通记录、表单模板。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from common.db import Base


# ── 状态机定义 ────────────────────────────────────────────────────

VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"submitted"},
    "submitted": {"screening", "withdrawn"},
    "screening": {"interview", "rejected"},
    "interview": {"offer", "rejected", "second_interview"},
    "second_interview": {"offer", "rejected"},
    "offer": {"accepted", "declined"},
    "accepted": {"onboarding"},
    "onboarding": {"hired"},
    "hired": set(),
    "rejected": set(),
    "withdrawn": set(),
    "declined": set(),
}

ALL_STATUSES = list(VALID_TRANSITIONS.keys())


class Application(Base):
    """职位申请表 — 含状态机和全生命周期追踪。"""
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    timeline: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Communication(Base):
    """沟通记录 — 来自浏览器扩展同步的聊天消息。"""
    __tablename__ = "communications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), default="browser")  # boss/linkedin/lagou/...
    direction: Mapped[str] = mapped_column(String(10), default="in")  # in/out
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FormTemplate(Base):
    """智能填表模板缓存 — 缓存目标网站的字段映射。"""
    __tablename__ = "form_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url_pattern: Mapped[str | None] = mapped_column(String(500), nullable=True)
    field_mappings: Mapped[dict] = mapped_column(JSONB, default=dict)
    usage_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

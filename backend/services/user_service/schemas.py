from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ── Auth ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Registration payload."""
    email: EmailStr = Field(..., description="User email address", examples=["user@example.com"])
    password: str = Field(
        ..., min_length=6, max_length=128,
        description="Password (6-128 characters)",
        examples=["securePass123"],
    )
    full_name: str = Field(
        ..., min_length=1, max_length=255,
        description="User's full name",
        examples=["Zhang Wei"],
    )


class LoginRequest(BaseModel):
    """Login payload."""
    email: EmailStr = Field(..., description="Registered email address", examples=["user@example.com"])
    password: str = Field(..., description="Account password", examples=["securePass123"])


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type (always 'bearer')")


class UserSummary(BaseModel):
    """Public user summary embedded in auth responses."""
    id: UUID
    email: str
    full_name: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """Full auth response: token + user info."""
    access_token: str
    token_type: str = "bearer"
    user: UserSummary


# ── Profile ───────────────────────────────────────────────────────

class ExperienceEntry(BaseModel):
    """A single work experience entry."""
    company: str = Field(..., description="Company name")
    title: str = Field(..., description="Job title")
    start_date: str = Field(..., description="Start date (YYYY-MM)")
    end_date: str | None = Field(None, description="End date (YYYY-MM), null if current")
    description: str | None = Field(None, description="Role description")
    current: bool = Field(False, description="Whether this is the current position")


class EducationEntry(BaseModel):
    """A single education entry."""
    school: str = Field(..., description="Institution name")
    degree: str = Field(..., description="Degree earned")
    field_of_study: str | None = Field(None, description="Major / field of study")
    start_date: str | None = Field(None, description="Start date (YYYY-MM)")
    end_date: str | None = Field(None, description="End date (YYYY-MM)")
    gpa: str | None = Field(None, description="GPA or grade")


class ProfileUpdateRequest(BaseModel):
    """Payload for updating the user profile. All fields optional — only
    supplied fields are updated (partial update / PATCH semantics)."""
    phone: str | None = Field(None, description="Phone number")
    location: str | None = Field(None, description="City / region")
    summary: str | None = Field(None, description="Professional summary or bio")
    linkedin_url: str | None = Field(None, description="LinkedIn profile URL")
    github_url: str | None = Field(None, description="GitHub profile URL")
    skills: list[str] | None = Field(None, description="List of skills (replaces existing)")
    experience: list[ExperienceEntry] | None = Field(None, description="Work experience entries")
    education: list[EducationEntry] | None = Field(None, description="Education entries")


class ProfileResponse(BaseModel):
    """Full user profile response."""
    id: UUID = Field(..., description="Profile ID")
    user_id: UUID = Field(..., description="Owning user ID")
    email: str = Field(..., description="User email")
    full_name: str = Field(..., description="User full name")
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    skills: list[str] | None = None
    experience: list[dict[str, Any]] | None = None
    education: list[dict[str, Any]] | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Verification ──────────────────────────────────────────────────

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    token: str = Field(..., min_length=1, description="邮箱验证码")


# ── Password Reset ────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="注册邮箱")


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    token: str = Field(..., description="重置密码 token")
    new_password: str = Field(..., min_length=6, max_length=128)


# ── Audit ─────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: UUID
    action: str
    ip_address: str | None
    details: dict | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Error ────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str = Field(..., description="Human-readable error message")

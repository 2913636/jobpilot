"""User Service — 认证、档案、验证、密码重置、限流、审计。"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.auth import create_access_token
from common.config import settings
from common.redis import redis_get, redis_incr, redis_delete

from .models import AuditLog, User, UserProfile
from .schemas import (
    AuthResponse,
    LoginRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    UserSummary,
)

# ── Password helpers ──────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def _generate_token() -> str:
    return secrets.token_urlsafe(32)


# ── Mock SMTP ─────────────────────────────────────────────────────

def _send_verification_email(email: str, token: str) -> None:
    """发送邮箱验证码（Mock SMTP，由环境变量 SMTP_ENABLED 控制）。

    在真实环境中会调用 SMTP 服务器发送邮件。
    """
    if settings.smtp_enabled:
        import os
        import logging
        logging.getLogger("user-service").info(
            f"[SMTP MOCK] To: {email} | Verification token: {token}"
        )
    # 始终打印到控制台以便调试
    print(f"[SMTP MOCK] To: {email} | Verification token: {token}")


def _send_reset_email(email: str, token: str) -> None:
    """发送密码重置链接（Mock SMTP）。"""
    reset_url = f"http://localhost:3000/reset-password?email={email}&token={token}"
    if settings.smtp_enabled:
        import logging
        logging.getLogger("user-service").info(
            f"[SMTP MOCK] To: {email} | Reset URL: {reset_url}"
        )
    print(f"[SMTP MOCK] To: {email} | Reset URL: {reset_url}")


# ── Rate Limiter ──────────────────────────────────────────────────

async def _check_rate_limit(ip: str) -> None:
    """检查登录频率限制: 同一 IP 5 分钟内失败 5 次锁定 15 分钟。"""
    fail_key = f"login_fail:{ip}"
    lock_key = f"login_lock:{ip}"

    locked = await redis_get(lock_key)
    if locked:
        raise ValueError("Too many login attempts. Please try again in 15 minutes.")

    failures = await redis_incr(fail_key, ttl=300)
    if failures >= 5:
        await redis_delete(fail_key)
        await redis_get(lock_key) is None and await redis_incr(lock_key, ttl=900)
        raise ValueError("Account locked for 15 minutes due to too many failed attempts.")


async def _reset_rate_limit(ip: str) -> None:
    await redis_delete(f"login_fail:{ip}")
    await redis_delete(f"login_lock:{ip}")


# ── Audit Logger ──────────────────────────────────────────────────

async def _audit_log(
    db: AsyncSession, action: str, user_id: uuid.UUID | None = None,
    ip_address: str | None = None, user_agent: str | None = None,
    details: dict | None = None,
) -> None:
    log_entry = AuditLog(
        user_id=user_id, action=action,
        ip_address=ip_address, user_agent=user_agent, details=details,
    )
    db.add(log_entry)
    await db.commit()


# ── Skill extraction helpers ──────────────────────────────────────

_KNOWN_SKILLS = {
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
    "react", "vue", "angular", "node.js", "django", "flask", "fastapi",
    "spring", "docker", "kubernetes", "aws", "gcp", "azure", "terraform",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "kafka",
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "pandas", "spark", "hadoop",
    "git", "ci/cd", "jenkins", "github actions", "linux",
    "agile", "scrum", "project management", "team leadership",
}

def _extract_skills_from_text(text: str) -> list[str]:
    lower = text.lower()
    found: list[str] = []
    for skill in sorted(_KNOWN_SKILLS, key=len, reverse=True):
        if skill in lower:
            found.append(skill)
            lower = lower.replace(skill, "", 1)
    return sorted(found)

def _normalize_skills(raw_skills: list[str] | None) -> list[str] | None:
    if raw_skills is None:
        return None
    normalized: set[str] = set()
    for s in raw_skills:
        key = s.strip().lower()
        if key in _KNOWN_SKILLS:
            normalized.add(key)
    return sorted(normalized)


# ── Services ──────────────────────────────────────────────────────

class AuthService:
    """用户认证：注册（含邮箱验证）、登录（含限流）、密码重置。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Register ──────────────────────────────────────────────

    async def register(self, data: RegisterRequest, ip: str = "") -> AuthResponse:
        existing = await self.db.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise ValueError("Email already registered")

        verify_token = _generate_token()[:6].upper()  # 6 chars for easy entry
        user = User(
            email=data.email,
            password_hash=_hash_password(data.password),
            full_name=data.full_name,
            is_verified=False,
            verification_token=verify_token,
            verification_token_expires=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        self.db.add(user)
        await self.db.flush()

        profile = UserProfile(user_id=user.id)
        self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(user)

        # 发送验证邮件（mock SMTP）
        _send_verification_email(user.email, verify_token)

        await _audit_log(self.db, "user.registered", user.id, ip,
                         details={"email": user.email})

        token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})
        return AuthResponse(access_token=token, user=UserSummary.model_validate(user))

    async def verify_email(self, email: str, token: str) -> bool:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")
        if user.is_verified:
            raise ValueError("Email already verified")
        if user.verification_token != token:
            raise ValueError("Invalid verification token")
        if user.verification_token_expires and user.verification_token_expires < datetime.now(timezone.utc):
            raise ValueError("Verification token expired")

        user.is_verified = True
        user.verification_token = None
        user.verification_token_expires = None
        await self.db.commit()

        await _audit_log(self.db, "user.verified", user.id,
                         details={"email": email})
        return True

    # ── Login ─────────────────────────────────────────────────

    async def login(self, data: LoginRequest, ip: str = "") -> AuthResponse:
        await _check_rate_limit(ip)

        result = await self.db.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()

        if not user or not _verify_password(data.password, user.password_hash):
            await _audit_log(self.db, "user.login_failed", None, ip,
                           details={"email": data.email})
            raise ValueError("Invalid email or password")

        if not user.is_verified:
            raise ValueError("Email not verified. Please check your inbox.")

        await _reset_rate_limit(ip)

        token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})
        await _audit_log(self.db, "user.login", user.id, ip,
                        details={"email": user.email})

        return AuthResponse(access_token=token, user=UserSummary.model_validate(user))

    # ── Password Reset ────────────────────────────────────────

    async def forgot_password(self, email: str) -> bool:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            # 不暴露用户是否存在，静默返回成功
            return True

        reset_token = _generate_token()
        user.reset_token = reset_token
        user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await self.db.commit()

        _send_reset_email(email, reset_token)

        await _audit_log(self.db, "user.password_reset_requested", user.id,
                         details={"email": email})
        return True

    async def reset_password(self, email: str, token: str, new_password: str,
                             ip: str = "") -> bool:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("Invalid request")
        if user.reset_token != token:
            raise ValueError("Invalid reset token")
        if user.reset_token_expires and user.reset_token_expires < datetime.now(timezone.utc):
            raise ValueError("Reset token expired")

        user.password_hash = _hash_password(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        await self.db.commit()

        await _audit_log(self.db, "user.password_reset", user.id, ip,
                         details={"email": email})
        return True


class ProfileService:
    """用户档案管理。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile(self, user_id: uuid.UUID) -> ProfileResponse:
        result = await self.db.execute(
            select(User).where(User.id == user_id).options(selectinload(User.profile))
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        profile = user.profile
        return ProfileResponse(
            id=profile.id if profile else uuid.uuid4(),
            user_id=user.id, email=user.email, full_name=user.full_name,
            phone=profile.phone if profile else None,
            location=profile.location if profile else None,
            summary=profile.summary if profile else None,
            linkedin_url=profile.linkedin_url if profile else None,
            github_url=profile.github_url if profile else None,
            skills=profile.skills if profile else None,
            experience=profile.experience if profile else None,
            education=profile.education if profile else None,
            updated_at=profile.updated_at if profile else None,
        )

    async def update_profile(
        self, user_id: uuid.UUID, data: ProfileUpdateRequest,
        ip: str = "", user_agent: str = "",
    ) -> ProfileResponse:
        result = await self.db.execute(
            select(User).where(User.id == user_id).options(selectinload(User.profile))
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        profile = user.profile
        if not profile:
            profile = UserProfile(user_id=user.id)
            self.db.add(profile)

        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            if field in ("experience", "education"):
                setattr(profile, field, [e.model_dump() for e in value] if value else None)
            elif field == "skills":
                setattr(profile, "skills", _normalize_skills(value))
            else:
                setattr(profile, field, value)

        if "summary" in update_fields and data.summary:
            text_skills = _extract_skills_from_text(data.summary)
            existing = profile.skills or []
            merged = sorted(set(existing) | set(text_skills))
            profile.skills = merged

        await self.db.commit()
        await self.db.refresh(profile)

        await _audit_log(self.db, "profile.updated", user_id, ip, user_agent,
                         details={"fields": list(update_fields.keys())})

        return ProfileResponse(
            id=profile.id, user_id=user.id, email=user.email, full_name=user.full_name,
            phone=profile.phone, location=profile.location, summary=profile.summary,
            linkedin_url=profile.linkedin_url, github_url=profile.github_url,
            skills=profile.skills, experience=profile.experience,
            education=profile.education, updated_at=profile.updated_at,
        )

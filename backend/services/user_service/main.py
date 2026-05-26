"""User Service — Auth, Profile, Verification, Password Reset, Audit."""

import sys
import uuid as _uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth import get_current_user
from common.cors import setup_cors
from common.exceptions import setup_exception_handlers
from common.db import engine, get_db
from common.logging import setup_logging, setup_trace_middleware
from common.tracing import setup_tracing
from common.metrics import business_counter

from .models import AuditLog, Base
from .schemas import (
    AuditLogResponse, AuthResponse, ErrorResponse, ForgotPasswordRequest,
    LoginRequest, ProfileResponse, ProfileUpdateRequest, RegisterRequest,
    ResetPasswordRequest, VerifyEmailRequest,
)
from .service import AuthService, ProfileService

app = FastAPI(
    title="User Service",
    description="""Auth, email verification, password reset, rate-limited login, audit.

## Curl Examples
```bash
# Register
curl -X POST http://localhost:8001/auth/register \\
  -H 'Content-Type: application/json' \\
  -d '{"email":"user@example.com","password":"securePass123","full_name":"Zhang Wei"}'

# Login
curl -X POST http://localhost:8001/auth/login \\
  -H 'Content-Type: application/json' \\
  -d '{"email":"user@example.com","password":"securePass123"}'
```
""",
    version="2.0.0",
    root_path="/api/users",
    responses={401: {"model": ErrorResponse}, 422: {"description": "Validation error"}},
)


setup_logging("user-service")
setup_trace_middleware(app)
setup_tracing("user-service")
setup_cors(app)
setup_exception_handlers(app)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health", tags=["System"], include_in_schema=False)
async def health():
    return {"status": "ok", "service": "user-service"}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


# ── Auth: Register + Verify ─────────────────────────────────────

@app.post("/auth/register", response_model=AuthResponse,
          status_code=status.HTTP_201_CREATED, tags=["Auth"],
          summary="Register (check email for verification code)",
          responses={409: {"model": ErrorResponse}})
async def register(
    body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    svc = AuthService(db)
    try:
        result = await svc.register(body, ip=_client_ip(request))
        business_counter("user_registrations_total")
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/auth/verify-email", tags=["Auth"], summary="Verify email with token")
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    try:
        await svc.verify_email(body.email, body.token)
        return {"message": "Email verified successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Auth: Login (rate-limited) ──────────────────────────────────

@app.post("/auth/login", response_model=AuthResponse, tags=["Auth"],
          summary="Login (rate-limited)", responses={401: {"model": ErrorResponse}})
async def login(
    body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    svc = AuthService(db)
    try:
        return await svc.login(body, ip=_client_ip(request))
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ── Auth: Password Reset ────────────────────────────────────────

@app.post("/auth/forgot-password", tags=["Auth"], summary="Send password reset email")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    await svc.forgot_password(body.email)
    return {"message": "If the email is registered, a reset link has been sent."}


@app.post("/auth/reset-password", tags=["Auth"], summary="Reset password with token")
async def reset_password(
    body: ResetPasswordRequest, request: Request, db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    try:
        await svc.reset_password(body.email, body.token, body.new_password,
                                 ip=_client_ip(request))
        return {"message": "Password reset successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Profile ─────────────────────────────────────────────────────

@app.get("/profile", response_model=ProfileResponse, tags=["Profile"],
         summary="Get profile")
async def get_profile(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    svc = ProfileService(db)
    try:
        return await svc.get_profile(user["sub"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.put("/profile", response_model=ProfileResponse, tags=["Profile"],
         summary="Update profile")
async def update_profile(
    body: ProfileUpdateRequest, request: Request,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    svc = ProfileService(db)
    try:
        return await svc.update_profile(
            user["sub"], body,
            ip=_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Audit ───────────────────────────────────────────────────────

@app.get("/audit-logs", response_model=list[AuditLogResponse], tags=["Audit"],
         summary="Get audit logs")
async def get_audit_logs(
    limit: int = Query(50, le=200),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogResponse]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == _uuid.UUID(user["sub"]))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return [AuditLogResponse.model_validate(log) for log in result.scalars().all()]

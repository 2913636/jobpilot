"""统一异常处理中间件 — 捕获所有未处理异常，返回标准 JSON 错误响应。"""

import logging
import traceback

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("jobpilot")


class AppError(Exception):
    """应用级异常基类，携带 HTTP 状态码和错误码。"""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR", http_status: int = 500):
        self.message = message
        self.code = code
        self.http_status = http_status
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, code="NOT_FOUND", http_status=404)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, code="VALIDATION_ERROR", http_status=400)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, code="UNAUTHORIZED", http_status=401)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict"):
        super().__init__(message, code="CONFLICT", http_status=409)


class ServiceUnavailableError(AppError):
    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(message, code="SERVICE_UNAVAILABLE", http_status=503)


class RateLimitError(AppError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, code="RATE_LIMITED", http_status=429)


def _error_response(request: Request, exc: Exception, status_code: int, code: str) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=status_code,
        content={
            "error": True,
            "code": code,
            "message": str(exc) if str(exc) else "An unexpected error occurred",
            "trace_id": trace_id,
        },
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器到 FastAPI 应用。"""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return _error_response(request, exc, exc.http_status, exc.code)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        msg = str(exc)
        if "not found" in msg.lower():
            return _error_response(request, exc, 404, "NOT_FOUND")
        if any(kw in msg.lower() for kw in ("invalid", "wrong", "expired", "already")):
            return _error_response(request, exc, 400, "BAD_REQUEST")
        if "rate" in msg.lower() or "locked" in msg.lower() or "too many" in msg.lower():
            return _error_response(request, exc, 429, "RATE_LIMITED")
        return _error_response(request, exc, 400, "BAD_REQUEST")

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return _error_response(request, exc, 404, "NOT_FOUND")

    @app.exception_handler(Exception)
    async def generic_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled exception",
            exc_info=exc,
            extra={"extra_fields": {"path": str(request.url), "method": request.method}},
        )
        # 生产环境不泄露 traceback
        return _error_response(request, exc, 500, "INTERNAL_ERROR")

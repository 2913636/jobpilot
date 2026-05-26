"""统一 JSON 日志 — 包含 trace_id，通过中间件注入上下文。

用法:
    import logging
    logger = logging.getLogger("jobpilot")
    logger.info("User registered", extra={"user_id": "...", "action": "register"})

输出格式:
    {"timestamp": "...", "level": "INFO", "logger": "jobpilot", "trace_id": "...",
     "message": "User registered", "user_id": "...", "action": "register"}
"""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, Response

# 上下文变量 — 每个请求独立
_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_request_path: ContextVar[str] = ContextVar("request_path", default="")
_service_name: ContextVar[str] = ContextVar("service_name", default="unknown")


def get_trace_id() -> str:
    return _trace_id.get() or ""


def set_trace_id(trace_id: str) -> None:
    _trace_id.set(trace_id)


class JSONFormatter(logging.Formatter):
    """JSON 格式日志输出器。"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": _trace_id.get() or record.__dict__.get("trace_id", ""),
            "service": _service_name.get(),
            "path": _request_path.get(),
            "message": record.getMessage(),
            "module": f"{record.module}:{record.lineno}",
        }

        # 合并 extra 中的自定义字段
        extra_fields = record.__dict__.get("extra_fields", {})
        log_entry.update(extra_fields)

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str, ensure_ascii=False)


def setup_logging(service_name: str = "unknown") -> None:
    """初始化 JSON 日志格式。
    在每个微服务的 main.py 启动时调用一次。
    """
    _service_name.set(service_name)

    root_logger = logging.getLogger()
    # 清除已有 handlers
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # 安静化第三方库
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "elastic_transport", "aiokafka"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("jobpilot").info("Logging initialized", extra={
        "extra_fields": {"event": "logging_setup", "service": service_name},
    })


class TraceMiddleware:
    """FastAPI 中间件：自动生成 trace_id，注入请求上下文。"""

    async def __call__(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or request.headers.get("traceparent", "")
        if trace_id and "-" in trace_id:
            trace_id = trace_id.split("-")[1][:16]  # W3C traceparent 格式
        if not trace_id:
            trace_id = uuid.uuid4().hex[:16]

        _trace_id.set(trace_id)
        _request_path.set(request.url.path)

        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response


def setup_trace_middleware(app: FastAPI) -> None:
    """注册 trace_id 注入中间件。"""
    app.add_middleware(TraceMiddleware)

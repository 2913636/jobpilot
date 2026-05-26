"""CORS 中间件配置 — 允许前端域名跨域访问。"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGINS = [
    os.getenv("CORS_ORIGIN", "http://localhost:3000"),
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    os.getenv("PRODUCTION_DOMAIN", "https://jobpilot.example.com"),
]


def setup_cors(app: FastAPI) -> None:
    """在所有微服务中注册统一的 CORS 配置。"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization", "Content-Type", "X-Requested-With",
            "X-Forwarded-For", "User-Agent",
        ],
        expose_headers=["X-Request-Id"],
    )

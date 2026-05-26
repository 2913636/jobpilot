"""API 版本化 — 为所有路由添加 /api/v1 前缀。

提供 versioned_router() 工厂函数，自动添加版本前缀。
旧路径保留向后兼容，30 天过渡期。
"""

from fastapi import APIRouter, FastAPI


def versioned_router(prefix: str = "", tags: list[str] | None = None) -> APIRouter:
    """创建带 /api/v1 前缀的 APIRouter。

    Usage:
        router = versioned_router("/users", tags=["Users"])
        router_v2 = versioned_router("/v2/users", tags=["Users v2"])
    """
    return APIRouter(prefix=f"/api/v1{prefix}", tags=tags or [])


def setup_legacy_routes(app: FastAPI, prefix: str, router_v1: APIRouter) -> None:
    """为旧路径（无 /v1）创建向后兼容路由。

    将 /api/users/* 映射到 /api/v1/users/*，并添加 deprecation 警告。
    30 天过渡期后移除。
    """
    for route in router_v1.routes:
        legacy_path = route.path.replace("/api/v1", "/api", 1)
        if legacy_path != route.path:
            app.add_api_route(
                path=legacy_path,
                endpoint=route.endpoint,
                methods=route.methods,
                response_model=route.response_model,
                tags=route.tags + ["deprecated"] if route.tags else ["deprecated"],
                deprecated=True,
                include_in_schema=False,
            )

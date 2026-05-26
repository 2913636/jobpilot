"""Apply Service — 申请管理、智能填表、沟通同步、看板统计。"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth import get_current_user
from common.db import engine, get_db

from .models import Base
from .schemas import (
    ApplicationCreate,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationUpdate,
    ChatSyncRequest,
    CommunicationResponse,
    ErrorResponse,
    FillFormRequest,
    FillFormResponse,
    FieldMapping,
    StatusTransition,
)
from .service import ApplyService
from common.cors import setup_cors
from common.exceptions import setup_exception_handlers

app = FastAPI(
    title="Apply Service",
    description="""职位申请管理、智能填表、沟通记录同步、全生命周期看板。

## Curl Examples
```bash
# Create application
curl -X POST :8004/ -H 'Authorization: Bearer $TOKEN' -H 'Content-Type: application/json' \\
  -d '{"job_id":"...","company":"Acme Corp","title":"SDE"}'

# Update status
curl -X PATCH :8004/{id} -H 'Authorization: Bearer $TOKEN' -H 'Content-Type: application/json' \\
  -d '{"status":"submitted"}'
```
""",
    version="1.0.0",
    root_path="/api/applications",
    responses={401: {"model": ErrorResponse}, 422: {"description": "Validation error"}},
)


setup_cors(app)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health", tags=["System"], include_in_schema=False)
async def health():
    return {"status": "ok", "service": "apply-service"}


# ── 申请 CRUD ────────────────────────────────────────────────────

@app.get("", response_model=ApplicationListResponse, tags=["Applications"],
         summary="获取申请列表")
async def list_applications(
    status: str | None = Query(None, description="按状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationListResponse:
    """获取当前用户的所有申请，支持按状态筛选和分页。"""
    svc = ApplyService(db)
    items, total = await svc.list_by_user(uuid.UUID(user["sub"]), status, page, page_size)
    return ApplicationListResponse(
        items=[ApplicationResponse.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size,
    )


@app.post("", response_model=ApplicationResponse, tags=["Applications"],
          status_code=status.HTTP_201_CREATED, summary="创建申请")
async def create_application(
    body: ApplicationCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """创建一条新的职位申请记录，初始状态为 draft。"""
    svc = ApplyService(db)
    app = await svc.create(uuid.UUID(user["sub"]), body.model_dump())
    return ApplicationResponse.model_validate(app)


@app.get("/stats", tags=["Applications"], summary="申请状态统计")
async def application_stats(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """返回各状态的申请数量，供看板视图使用。"""
    svc = ApplyService(db)
    return await svc.get_stats(uuid.UUID(user["sub"]))


@app.get("/{app_id}", response_model=ApplicationResponse, tags=["Applications"],
         summary="获取申请详情")
async def get_application(
    app_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    svc = ApplyService(db)
    app = await svc.get(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="申请不存在")
    return ApplicationResponse.model_validate(app)


@app.patch("/{app_id}", response_model=ApplicationResponse, tags=["Applications"],
           summary="更新申请状态")
async def update_application(
    app_id: uuid.UUID,
    body: ApplicationUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """更新申请状态（需符合状态机规则）或备注。"""
    svc = ApplyService(db)
    try:
        app = await svc.update(app_id, body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not app:
        raise HTTPException(status_code=404, detail="申请不存在")
    return ApplicationResponse.model_validate(app)


@app.post("/{app_id}/transitions", response_model=StatusTransition, tags=["Applications"],
          summary="验证状态转换")
async def check_transition(
    app_id: uuid.UUID,
    from_status: str = Query(...),
    to_status: str = Query(...),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatusTransition:
    """检查从当前状态到目标状态是否合法。"""
    svc = ApplyService(db)
    allowed = svc.validate_transition(from_status, to_status)
    return StatusTransition(
        success=allowed, from_status=from_status, to_status=to_status,
        allowed=allowed,
        message="合法转换" if allowed else f"不允许: {from_status} -> {to_status}",
    )


# ── 智能填表 ──────────────────────────────────────────────────────

@app.post("/fill-form", response_model=FillFormResponse, tags=["Smart Fill"],
          summary="智能表单填充分析")
async def fill_form(
    body: FillFormRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FillFormResponse:
    """分析目标 URL 的表单字段，返回与用户档案的映射建议。

    可用于浏览器扩展自动填表。
    """
    # 从 user-service 获取完整档案（这里用简化的 profile）
    profile = {
        "email": user.get("email", ""),
        "full_name": "",
        "phone": "",
        "summary": "",
        "skills": [],
        "experience": [],
        "education": [],
        "linkedin_url": "",
        "github_url": "",
    }

    svc = ApplyService(db)
    result = await svc.fill_form(body.url, profile, body.page_html)
    return FillFormResponse(
        url=result["url"], domain=result["domain"],
        mappings=[FieldMapping(**m) for m in result["mappings"]],
        template_id=result.get("template_id"),
    )


# ── 沟通记录同步 ──────────────────────────────────────────────────

@app.post("/crm/sync-chat", response_model=CommunicationResponse,
          status_code=status.HTTP_201_CREATED, tags=["CRM"],
          summary="同步沟通记录")
async def sync_chat(
    body: ChatSyncRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommunicationResponse:
    """从浏览器扩展同步招聘平台的聊天消息。"""
    svc = ApplyService(db)
    comm = await svc.sync_chat(uuid.UUID(user["sub"]), body.model_dump())
    return CommunicationResponse.model_validate(comm)


@app.get("/crm/chats", response_model=list[CommunicationResponse], tags=["CRM"],
         summary="获取沟通记录")
async def list_chats(
    application_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CommunicationResponse]:
    """获取指定申请的沟通记录列表。"""
    svc = ApplyService(db)
    items, total = await svc.list_chats(uuid.UUID(user["sub"]), application_id, page)
    return [CommunicationResponse.model_validate(c) for c in items]

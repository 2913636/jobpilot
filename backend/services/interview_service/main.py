"""Interview Service — AI 面试、多模态分析、题库社区。"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth import get_current_user
from common.db import engine, get_db

from .models import Base
from .schemas import (
    EmotionFrame, ErrorResponse, QuestionCreate, QuestionListResponse,
    QuestionResponse, ReportResponse, StartInterviewRequest,
    StartInterviewResponse, VoteRequest,
)
from .service import InterviewService
from common.cors import setup_cors
from common.exceptions import setup_exception_handlers

app = FastAPI(
    title="Interview Service",
    description="""AI 模拟面试、多模态行为分析、题库社区。

## Curl Examples
```bash
# Start interview
curl -X POST :8005/start -H 'Authorization: Bearer $TOKEN' -H 'Content-Type: application/json' -d '{}'

# Submit answer
curl -X POST :8005/{session_id}/answer -H 'Authorization: Bearer $TOKEN' \\
  -H 'Content-Type: application/json' -d '{"text":"My answer..."}'
```
""",
    version="1.0.0",
    root_path="/api/interviews",
)


setup_cors(app)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health", tags=["System"], include_in_schema=False)
async def health():
    return {"status": "ok", "service": "interview-service"}


# ── 会话 ────────────────────────────────────────────────────────

@app.post("/start", response_model=StartInterviewResponse, tags=["Interview"],
          summary="开始面试")
async def start_interview(
    body: StartInterviewRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StartInterviewResponse:
    svc = InterviewService(db)
    result = await svc.start_session(uuid.UUID(user["sub"]), body.job_id, body.application_id)
    return StartInterviewResponse(**result)


@app.get("/{session_id}", tags=["Interview"], summary="获取会话")
async def get_session(
    session_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = InterviewService(db)
    s = await svc.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "id": str(s.id), "room_name": s.room_name, "status": s.status,
        "transcript": s.transcript, "emotions": s.emotions,
        "started_at": s.started_at and s.started_at.isoformat(),
        "ended_at": s.ended_at and s.ended_at.isoformat(),
    }


@app.post("/{session_id}/answer", tags=["Interview"], summary="提交回答")
async def submit_answer(
    session_id: uuid.UUID, body: dict[str, str],
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = InterviewService(db)
    return await svc.handle_answer(session_id, body.get("text", ""))


@app.post("/{session_id}/emotion", tags=["Interview"], summary="面部分析")
async def upload_emotion(
    session_id: uuid.UUID, body: dict[str, Any],
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = InterviewService(db)
    return await svc.process_emotion_frame(session_id, body.get("landmarks", []))


# ── 报告 ────────────────────────────────────────────────────────

@app.post("/{session_id}/report", response_model=ReportResponse, tags=["Report"],
          summary="生成报告")
async def generate_report(
    session_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    svc = InterviewService(db)
    try:
        await svc.generate_report(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    report = await svc.get_report(session_id)
    return ReportResponse.model_validate(report)


# ── 题库 ────────────────────────────────────────────────────────

@app.post("/questions", response_model=QuestionResponse, tags=["Question Bank"],
          status_code=status.HTTP_201_CREATED, summary="创建题目")
async def create_question(
    body: QuestionCreate, user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuestionResponse:
    svc = InterviewService(db)
    q = await svc.question_bank.create(uuid.UUID(user["sub"]), body.model_dump())
    return QuestionResponse.model_validate(q)


@app.get("/questions", response_model=QuestionListResponse, tags=["Question Bank"],
         summary="搜索题库")
async def search_questions(
    keyword: str = Query(""), category: str | None = Query(None),
    difficulty: str | None = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuestionListResponse:
    svc = InterviewService(db)
    items, total = await svc.question_bank.search(keyword, category, difficulty, page, page_size)
    return QuestionListResponse(
        items=[QuestionResponse.model_validate(q) for q in items],
        total=total, page=page, page_size=page_size,
    )


@app.post("/questions/{question_id}/vote", tags=["Question Bank"], summary="投票")
async def vote_question(
    question_id: uuid.UUID, body: VoteRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = InterviewService(db)
    try:
        return await svc.question_bank.vote(question_id, uuid.UUID(user["sub"]), body.vote_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/questions/{question_id}/duplicates", tags=["Question Bank"],
         summary="检查重复")
async def check_duplicates(question_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from .models import Question
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    svc = InterviewService(db)
    return await svc.question_bank.check_duplicate(q.title, q.content)


# ── WebSocket ───────────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def ws_emotion(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            landmarks = data.get("landmarks", [])
            if landmarks:
                from .analyzer import EmotionAnalyzer
                result = EmotionAnalyzer().analyze_frame(landmarks)
                await websocket.send_json({"type": "emotion_result", "data": result})
    except WebSocketDisconnect:
        pass

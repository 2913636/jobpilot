"""Interview Service — 面试会话、AI 对话、多模态分析、题库。"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .analyzer import EmotionAnalyzer, ReportGenerator, VoiceAnalyzer
from .interviewer import AIInterviewer
from .livekit import LiveKitService
from .models import InterviewReport, InterviewSession, Question
from .question_bank import QuestionBankService


class InterviewService:
    """面试会话管理 + AI 对话引擎。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.livekit = LiveKitService()
        self.analyzer = EmotionAnalyzer()
        self.voice_analyzer = VoiceAnalyzer()
        self.report_generator = ReportGenerator()
        self.question_bank = QuestionBankService(db)

    # ── 会话管理 ──────────────────────────────────────────────

    async def start_session(self, user_id: uuid.UUID, job_id: uuid.UUID | None = None,
                            application_id: uuid.UUID | None = None) -> dict[str, Any]:
        room_name = self.livekit.create_room_name()
        token = self.livekit.generate_token(room_name, "candidate")

        session = InterviewSession(
            user_id=user_id, job_id=job_id, application_id=application_id,
            room_name=room_name, status="waiting",
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        return {
            "session_id": session.id, "room_name": room_name,
            "livekit_token": token, "livekit_url": self.livekit.url,
        }

    async def get_session(self, session_id: uuid.UUID) -> InterviewSession | None:
        result = await self.db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
        return result.scalar_one_or_none()

    async def update_session(self, session_id: uuid.UUID, **kwargs) -> InterviewSession | None:
        session = await self.get_session(session_id)
        if not session:
            return None
        for k, v in kwargs.items():
            setattr(session, k, v)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    # ── AI 面试对话 ──────────────────────────────────────────

    _interviewers: dict[str, AIInterviewer] = {}

    async def get_interviewer(self, session_id: str) -> AIInterviewer:
        if session_id not in self._interviewers:
            self._interviewers[session_id] = AIInterviewer()
        return self._interviewers[session_id]

    async def handle_answer(self, session_id: uuid.UUID, user_answer: str) -> dict[str, Any]:
        iv = await self.get_interviewer(str(session_id))

        # 语音分析
        voice = self.voice_analyzer.analyze(user_answer)

        # 记录转写
        session = await self.get_session(session_id)
        if session:
            transcript = list(session.transcript or [])
            transcript.append({
                "speaker": "user", "text": user_answer,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "voice_metrics": voice,
            })
            session.transcript = transcript
            await self.db.commit()

        # 生成追问
        next_q = await iv.next_question(user_answer)
        if session:
            transcript = list(session.transcript or [])
            transcript.append({
                "speaker": "interviewer", "text": next_q,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            session.transcript = transcript
            if iv.is_complete:
                session.status = "completed"
                session.ended_at = datetime.now(timezone.utc)
            await self.db.commit()

        return {"next_question": next_q, "is_complete": iv.is_complete, "voice_metrics": voice}

    # ── 多模态分析 ────────────────────────────────────────────

    async def process_emotion_frame(self, session_id: uuid.UUID, landmarks: list[dict]) -> dict[str, float]:
        result = self.analyzer.analyze_frame(landmarks)
        session = await self.get_session(session_id)
        if session:
            emotions = list(session.emotions or [])
            emotions.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **result,
            })
            session.emotions = emotions
            await self.db.commit()
        return result

    # ── 报告 ──────────────────────────────────────────────────

    async def generate_report(self, session_id: uuid.UUID) -> dict[str, Any]:
        session = await self.get_session(session_id)
        if not session:
            raise ValueError("会话不存在")

        report_data = self.report_generator.generate(
            str(session_id),
            session.transcript or [],
            session.emotions or [],
            session.voice_metrics or [],
        )

        report = InterviewReport(
            session_id=session_id,
            overall_score=report_data["overall_score"],
            scores=report_data["scores"],
            strengths=report_data["strengths"],
            weaknesses=report_data["weaknesses"],
            recommendations=report_data["recommendations"],
            detailed_feedback=report_data["detailed_feedback"],
            question_results=report_data["question_results"],
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report_data

    async def get_report(self, session_id: uuid.UUID) -> InterviewReport | None:
        result = await self.db.execute(
            select(InterviewReport).where(InterviewReport.session_id == session_id)
        )
        return result.scalar_one_or_none()

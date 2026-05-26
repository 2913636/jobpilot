"""Interview-service 核心测试 — mock LiveKit 依赖。"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pytest

from services.interview_service.livekit import LiveKitService
from services.interview_service.interviewer import AIInterviewer, SAMPLE_QUESTIONS, STAGES
from services.interview_service.analyzer import EmotionAnalyzer, VoiceAnalyzer, ReportGenerator
from services.interview_service.transcriber import Transcriber


class TestLiveKit:
    def test_create_room_name(self):
        svc = LiveKitService()
        name = svc.create_room_name()
        assert name.startswith("interview-")
        assert len(name) > 15

    def test_mock_token(self):
        svc = LiveKitService()
        token = svc._mock_token("room-1", "candidate")
        assert token.startswith("dev_")
        assert len(token) == 36


class TestAIInterviewer:
    def test_greeting(self):
        iv = AIInterviewer()
        g = iv.get_greeting()
        assert "你好" in g and "面试" in g

    def test_first_question(self):
        iv = AIInterviewer()
        g = iv.get_greeting()
        assert len(g) > 10

    def test_stages_defined(self):
        assert len(STAGES) >= 5
        for s in STAGES:
            assert "name" in s

    def test_sample_questions(self):
        assert len(SAMPLE_QUESTIONS) >= 3
        for cat, qs in SAMPLE_QUESTIONS.items():
            assert len(qs) >= 1

    def test_is_complete_after_questions(self):
        iv = AIInterviewer()
        assert not iv.is_complete
        iv.stage_index = len(STAGES) - 1
        iv.current_stage_questions = 2
        assert iv.is_complete

    @pytest.mark.asyncio
    async def test_next_question_returns_string(self):
        iv = AIInterviewer()
        q = await iv.next_question()
        assert isinstance(q, str) and len(q) > 0

    @pytest.mark.asyncio
    async def test_tts_mock(self):
        iv = AIInterviewer()
        result = await iv.synthesize_speech("你好")
        assert result is None  # mock provider returns None


class TestAnalyzers:
    def test_emotion_analyzer_empty(self):
        a = EmotionAnalyzer()
        result = a.analyze_frame([])
        assert 0 <= result["confidence_score"] <= 100

    def test_emotion_analyzer_with_data(self):
        a = EmotionAnalyzer()
        fake_landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0} for _ in range(60)]
        result = a.analyze_frame(fake_landmarks)
        assert "smile_ratio" in result
        assert "confidence_score" in result

    def test_voice_analyzer_normal(self):
        a = VoiceAnalyzer()
        result = a.analyze("Python is a great language for backend development.", 3.0)
        assert result["speech_rate"] > 0
        assert result["word_count"] > 0

    def test_voice_analyzer_fillers(self):
        a = VoiceAnalyzer()
        result = a.analyze("呃 那个 就是 Python 然后 Docker", 5.0)
        assert len(result["filler_words"]) >= 3
        assert result["filler_ratio"] > 0.3

    def test_report_generator(self):
        g = ReportGenerator()
        transcript = [
            {"speaker": "interviewer", "text": "请介绍Python的GIL", "timestamp": "2026-01-01T00:00:00"},
            {"speaker": "user", "text": "GIL是全局解释器锁，它影响多线程并发。Python通过GIL保证内存安全...", "timestamp": "2026-01-01T00:00:05"},
        ]
        emotions = [{"smile_ratio": 0.7, "confidence_score": 75}]
        voice = [{"speech_rate": 140, "filler_ratio": 0.05}]
        report = g.generate("test-session", transcript, emotions, voice)
        assert "overall_score" in report
        assert 0 <= report["overall_score"] <= 100
        assert len(report["scores"]) >= 5
        assert len(report["strengths"]) >= 1
        assert len(report["weaknesses"]) >= 1
        assert len(report["recommendations"]) >= 1


class TestTranscriber:
    @pytest.mark.asyncio
    async def test_mock_transcribe(self):
        t = Transcriber()
        result = await t._mock_transcribe(b"fake audio data")
        assert "[模拟转写" in result

    @pytest.mark.asyncio
    async def test_transcribe_returns_string(self):
        t = Transcriber()
        result = await t.transcribe(b"test audio", 16000)
        assert isinstance(result, str) and len(result) > 0

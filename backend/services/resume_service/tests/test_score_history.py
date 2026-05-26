"""Tests for ATS score history."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import uuid
import pytest
from services.resume_service.service import ScoreHistoryService
from services.resume_service.scorer import ATSScorer


class TestScoreHistory:
    def test_scorer_has_35_rules(self):
        scorer = ATSScorer()
        result = scorer.score("Python developer with 5 years experience.", ["python", "aws"])
        assert "score" in result
        assert "breakdown" in result
        assert len(result["breakdown"]) == 5  # 5 categories
        details = result.get("details", {})
        all_rules = []
        for cat in ["format_rules", "keyword_rules", "content_rules", "structure_rules", "impact_rules"]:
            all_rules.extend(details.get(cat, {}).keys())
        assert len(all_rules) >= 30, f"Expected >= 30 rules, got {len(all_rules)}"


class TestTrendLogic:
    def test_improving_trend(self):
        """上升趋势：最近分数高于之前。"""
        from unittest.mock import AsyncMock, MagicMock
        db = AsyncMock()

        # Mock 分数序列: 60 → 65 → 70
        records = [
            MagicMock(score=60.0, created_at=None, id=uuid.uuid4(),
                      breakdown=None, missing_keywords=None, suggestions=None),
            MagicMock(score=65.0, created_at=None, id=uuid.uuid4(),
                      breakdown=None, missing_keywords=None, suggestions=None),
            MagicMock(score=70.0, created_at=None, id=uuid.uuid4(),
                      breakdown=None, missing_keywords=None, suggestions=None),
        ]

        svc = ScoreHistoryService(db)
        # Bypass DB call
        async def mock_execute(*args, **kwargs):
            class MockResult:
                def scalars(self):
                    return MagicMock(all=lambda: records)
            return MockResult()

        db.execute = mock_execute

        result = svc.get_history(uuid.uuid4())
        assert result["trend"] == "improving"

    def test_declining_trend(self):
        """下降趋势：最近分数低于之前。"""
        from unittest.mock import AsyncMock, MagicMock
        db = AsyncMock()
        records = [
            MagicMock(score=80.0, created_at=None, id=uuid.uuid4(),
                      breakdown=None, missing_keywords=None, suggestions=None),
            MagicMock(score=75.0, created_at=None, id=uuid.uuid4(),
                      breakdown=None, missing_keywords=None, suggestions=None),
            MagicMock(score=68.0, created_at=None, id=uuid.uuid4(),
                      breakdown=None, missing_keywords=None, suggestions=None),
        ]
        svc = ScoreHistoryService(db)
        async def mock_execute(*args, **kwargs):
            class MockResult:
                def scalars(self):
                    return MagicMock(all=lambda: records)
            return MockResult()
        db.execute = mock_execute
        result = svc.get_history(uuid.uuid4())
        assert result["trend"] == "declining"

    def test_stable_trend(self):
        """稳定趋势。"""
        from unittest.mock import AsyncMock, MagicMock
        db = AsyncMock()
        records = [
            MagicMock(score=70.0, created_at=None, id=uuid.uuid4(),
                      breakdown=None, missing_keywords=None, suggestions=None),
            MagicMock(score=71.0, created_at=None, id=uuid.uuid4(),
                      breakdown=None, missing_keywords=None, suggestions=None),
            MagicMock(score=70.5, created_at=None, id=uuid.uuid4(),
                      breakdown=None, missing_keywords=None, suggestions=None),
        ]
        svc = ScoreHistoryService(db)
        async def mock_execute(*args, **kwargs):
            class MockResult:
                def scalars(self):
                    return MagicMock(all=lambda: records)
            return MockResult()
        db.execute = mock_execute
        result = svc.get_history(uuid.uuid4())
        assert result["trend"] == "stable"

    def test_single_record(self):
        """只有一条记录时趋势为 stable."""
        from unittest.mock import AsyncMock, MagicMock
        db = AsyncMock()
        records = [MagicMock(score=75.0, created_at=None, id=uuid.uuid4(),
                             breakdown=None, missing_keywords=None, suggestions=None)]
        svc = ScoreHistoryService(db)
        async def mock_execute(*args, **kwargs):
            class MockResult:
                def scalars(self):
                    return MagicMock(all=lambda: records)
            return MockResult()
        db.execute = mock_execute
        result = svc.get_history(uuid.uuid4())
        assert result["latest_score"] == 75.0
        assert result["avg_score"] == 75.0
        assert result["trend"] == "stable"

    def test_empty_history(self):
        """无记录时返回默认值。"""
        from unittest.mock import AsyncMock, MagicMock
        db = AsyncMock()
        records: list = []
        svc = ScoreHistoryService(db)
        async def mock_execute(*args, **kwargs):
            class MockResult:
                def scalars(self):
                    return MagicMock(all=lambda: records)
            return MockResult()
        db.execute = mock_execute
        result = svc.get_history(uuid.uuid4())
        assert result["latest_score"] is None
        assert result["trend"] == "stable"

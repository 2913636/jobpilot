"""Apply-service 核心测试 — 状态机、填表引擎。"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pytest

from services.apply_service.models import ALL_STATUSES, VALID_TRANSITIONS
from services.apply_service.service import ApplyService


class TestStateMachine:
    """状态机规则测试。"""

    def test_valid_transitions(self):
        """所有预定义的转换都需合法。"""
        # draft -> submitted 是有效的
        assert "submitted" in VALID_TRANSITIONS["draft"]
        # submitted -> screening 有效
        assert "screening" in VALID_TRANSITIONS["submitted"]
        # submitted -> withdrawn 有效
        assert "withdrawn" in VALID_TRANSITIONS["submitted"]

    def test_invalid_transitions(self):
        """跳过状态的转换不被允许。"""
        # draft -> offer 不允许
        assert "offer" not in VALID_TRANSITIONS.get("draft", set())
        # hired -> 任何状态都不允许（终态）
        assert len(VALID_TRANSITIONS.get("hired", set())) == 0
        # rejected -> 任何状态都不允许
        assert len(VALID_TRANSITIONS.get("rejected", set())) == 0

    def test_interview_to_second(self):
        """面试可以进入二面。"""
        assert "second_interview" in VALID_TRANSITIONS["interview"]

    def test_second_interview_to_offer(self):
        """二面可以进入 offer。"""
        assert "offer" in VALID_TRANSITIONS["second_interview"]

    def test_offer_to_accepted_or_declined(self):
        """offer 只能接受或拒绝。"""
        transitions = VALID_TRANSITIONS["offer"]
        assert "accepted" in transitions
        assert "declined" in transitions
        assert len(transitions) == 2

    def test_withdrawn_is_terminal(self):
        """撤回是终态。"""
        assert len(VALID_TRANSITIONS["withdrawn"]) == 0

    def test_all_statuses_defined(self):
        """所有状态都有转换规则定义。"""
        assert len(ALL_STATUSES) >= 10
        for s in ALL_STATUSES:
            assert s in VALID_TRANSITIONS, f"状态 {s} 缺少转换规则"

    def test_no_self_transition(self):
        """状态机不应允许自身转换。"""
        for status, transitions in VALID_TRANSITIONS.items():
            assert status not in transitions, f"{status} 不应允许转换到自身"


class TestFormFiller:
    """智能填表引擎测试。"""

    def test_field_label_map_complete(self):
        from services.apply_service.form_filler import _FIELD_LABEL_MAP
        # 常见字段应有映射
        assert "email" in _FIELD_LABEL_MAP
        assert "姓名" in _FIELD_LABEL_MAP
        assert "phone" in _FIELD_LABEL_MAP
        assert "skills" in _FIELD_LABEL_MAP

    def test_match_field_direct(self):
        from services.apply_service.form_filler import FormFiller
        filler = FormFiller({"email": "test@test.com", "full_name": "Test"})
        assert filler._match_field("email") == "email"
        assert filler._match_field("name") == "full_name"

    def test_match_field_substring(self):
        from services.apply_service.form_filler import FormFiller
        filler = FormFiller({})
        # "e-mail" 包含 "email"
        result = filler._match_field("e-mail")
        assert result is not None

    def test_get_profile_value(self):
        from services.apply_service.form_filler import FormFiller
        filler = FormFiller({
            "email": "alice@example.com",
            "skills": ["python", "docker", "kubernetes"],
            "full_name": "Alice",
        })
        assert filler._get_profile_value("email") == "alice@example.com"
        assert "python" in filler._get_profile_value("skills")
        assert filler._get_profile_value("nonexistent") == ""

    def test_domain_patterns(self):
        from services.apply_service.form_filler import _DOMAIN_PATTERNS
        assert "zhipin.com" in _DOMAIN_PATTERNS
        assert "linkedin.com" in _DOMAIN_PATTERNS
        assert "lagou.com" in _DOMAIN_PATTERNS
        for domain, patterns in _DOMAIN_PATTERNS.items():
            assert isinstance(patterns, list)
            for p in patterns:
                assert "selector" in p
                assert "profile_key" in p

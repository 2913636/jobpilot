"""Match-service 核心功能测试 — 不需要外部服务的单元测试。"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pytest

from services.match_service.career import CareerPathService
from services.match_service.salary import SalaryPredictor
from services.match_service.comparator import JobComparator


class TestSalaryPredictor:
    @pytest.fixture
    def predictor(self):
        return SalaryPredictor()

    def test_predict_basic(self, predictor):
        result = predictor._rule_based_predict(
            title="senior software engineer", location="Beijing",
            experience_years=5, education="bachelor", skills=["python", "aws", "kubernetes"],
            company_size="large",
        )
        assert result["predicted_median"] > 200000
        assert result["predicted_min"] < result["predicted_median"] < result["predicted_max"]
        assert result["currency"] == "CNY"
        assert "experience_multiplier" in result["factors"]

    def test_predict_junior(self, predictor):
        result = predictor._rule_based_predict(
            title="python developer", location="Beijing",
            experience_years=1, education="bachelor", skills=["python"],
            company_size="startup",
        )
        assert result["predicted_median"] < 300000

    def test_predict_experience_boost(self, predictor):
        junior = predictor._rule_based_predict(
            title="backend developer", location="Shanghai",
            experience_years=1, education="bachelor", skills=[], company_size="medium",
        )
        senior = predictor._rule_based_predict(
            title="backend developer", location="Shanghai",
            experience_years=8, education="bachelor", skills=[], company_size="medium",
        )
        assert senior["predicted_median"] > junior["predicted_median"]

    def test_predict_education_boost(self, predictor):
        bach = predictor._rule_based_predict(
            title="software engineer", location="Beijing",
            experience_years=3, education="bachelor", skills=[], company_size="medium",
        )
        phd = predictor._rule_based_predict(
            title="software engineer", location="Beijing",
            experience_years=3, education="phd", skills=[], company_size="medium",
        )
        assert phd["predicted_median"] > bach["predicted_median"]

    def test_predict_premium_skills(self, predictor):
        basic = predictor._rule_based_predict(
            title="backend developer", location="Beijing",
            experience_years=3, education="bachelor", skills=["python"],
            company_size="medium",
        )
        premium = predictor._rule_based_predict(
            title="backend developer", location="Beijing",
            experience_years=3, education="bachelor",
            skills=["python", "kubernetes", "aws", "machine learning", "tensorflow"],
            company_size="medium",
        )
        assert premium["predicted_median"] > basic["predicted_median"]


class TestCareerPath:
    def test_fallback_path_python(self):
        svc = CareerPathService(None)
        result = svc._fallback_path(["python"], "senior software engineer")
        assert len(result["path"]) >= 2
        assert result["total_months"] > 0
        assert isinstance(result["alternative_roles"], list)

    def test_fallback_path_unknown_skill(self):
        svc = CareerPathService(None)
        result = svc._fallback_path(["unknown_skill"], "devops engineer")
        assert len(result["path"]) == 3
        assert result["total_months"] > 0
        assert len(result["alternative_roles"]) > 0

    def test_alternatives_for_backend(self):
        svc = CareerPathService(None)
        alts = svc._alternatives("backend developer")
        assert len(alts) >= 2


class TestComparator:
    def test_score_dimensions(self):
        comp = JobComparator(None)
        job = {"skills": ["python", "aws", "docker"], "salary_max": 400000,
               "location": "Shanghai", "company": "ByteDance"}
        assert comp._score_dimension(job, "skill_growth") > 5
        assert comp._score_dimension(job, "salary") > 5
        assert comp._score_dimension(job, "company_prospect") > 8

    def test_template_report(self):
        comp = JobComparator(None)
        jobs = [
            {"id": "1", "title": "SDE", "company": "Acme", "location": "Beijing",
             "salary_min": 200000, "salary_max": 350000, "skills": ["python"], "description": "Build APIs"},
            {"id": "2", "title": "Senior SDE", "company": "ByteDance", "location": "Shanghai",
             "salary_min": 400000, "salary_max": 600000, "skills": ["python", "k8s"], "description": "Lead team"},
        ]
        dims = comp._compute_dimensions(jobs)
        report = comp._template_report(jobs, dims)
        assert "SDE" in report
        assert "ByteDance" in report
        assert "技能成长" in report

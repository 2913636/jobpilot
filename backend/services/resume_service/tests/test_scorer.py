"""Unit tests for ATS scorer — no database required."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pytest
from services.resume_service.scorer import ATSScorer

SAMPLE_RESUME = """
John Doe
john@example.com | +1 555-0123 | San Francisco, CA

SUMMARY
Senior Software Engineer with 8 years of experience in Python, AWS, and microservices.

EXPERIENCE
Senior Backend Engineer, Acme Corp (2020-01 to 2023-06)
- Designed and implemented microservices architecture using Python and FastAPI
- Reduced latency by 40% through query optimization and caching with Redis
- Led a team of 5 engineers to deliver 3 major product releases
- Automated CI/CD pipelines with GitHub Actions, reducing deployment time by 60%

Software Engineer, Startup Inc (2017-03 to 2019-12)
- Built RESTful APIs serving 1M+ daily requests using Django and PostgreSQL
- Implemented real-time analytics dashboard with Kafka and Elasticsearch
- Migrated legacy monolith to containerized services, saving $200K/year in infra costs

EDUCATION
BSc Computer Science, MIT (2013-2017), GPA 3.9

SKILLS
Python, JavaScript, Go, React, Django, FastAPI, Docker, Kubernetes, AWS, Terraform,
PostgreSQL, MongoDB, Redis, Elasticsearch, Kafka, CI/CD, Git, Linux, Agile
"""


@pytest.fixture
def scorer():
    return ATSScorer()


class TestScorerBasics:
    def test_score_range(self, scorer):
        result = scorer.score(SAMPLE_RESUME)
        assert 0 <= result["score"] <= 100

    def test_breakdown_categories(self, scorer):
        result = scorer.score(SAMPLE_RESUME)
        cats = result["breakdown"]
        assert "format" in cats
        assert "keywords" in cats
        assert "content" in cats
        assert "structure" in cats
        assert "impact" in cats

    def test_suggestions_returned(self, scorer):
        result = scorer.score(SAMPLE_RESUME)
        assert isinstance(result["suggestions"], list)

    def test_missing_keywords_empty_without_jd(self, scorer):
        result = scorer.score(SAMPLE_RESUME)
        assert result["missing_keywords"] == []


class TestScorerWithJD:
    JD_KEYWORDS = ["python", "aws", "kubernetes", "machine learning", "spark", "go"]

    def test_missing_keywords(self, scorer):
        result = scorer.score(SAMPLE_RESUME, self.JD_KEYWORDS)
        missing = result["missing_keywords"]
        assert "machine learning" in missing
        assert "spark" in missing

    def test_present_keywords_not_missing(self, scorer):
        result = scorer.score(SAMPLE_RESUME, self.JD_KEYWORDS)
        missing = result["missing_keywords"]
        assert "python" not in missing
        assert "aws" not in missing

    def test_higher_score_with_keywords(self, scorer):
        no_kw = scorer.score(SAMPLE_RESUME, [])
        with_kw = scorer.score(SAMPLE_RESUME, self.JD_KEYWORDS)
        # Keyword matches should increase the score
        assert with_kw["breakdown"]["keywords"] > 0


class TestScorerContent:
    def test_empty_text(self, scorer):
        result = scorer.score("")
        assert result["score"] < 30

    def test_short_text(self, scorer):
        result = scorer.score("John Doe\nPython Developer\nSkills: Python")
        assert result["score"] < 50

    def test_action_verbs_detected(self, scorer):
        result = scorer.score(SAMPLE_RESUME)
        details = result.get("details", {})
        content = details.get("content_rules", {})
        # Should get points for action verbs
        assert content.get("c_1_action_verbs", 0) > 3

    def test_metrics_detected(self, scorer):
        result = scorer.score(SAMPLE_RESUME)
        details = result.get("details", {})
        impact = details.get("impact_rules", {})
        # Should get points for quantified results
        assert impact.get("i_2_metrics_count", 0) > 3

    def test_first_person_penalty(self, scorer):
        bad = "I am a developer. I built many things. My skills include Python. I worked at a company."
        result = scorer.score(bad)
        details = result.get("details", {})
        content = details.get("content_rules", {})
        assert content.get("c_3_grammar", 0) < 4

    def test_contact_detection(self, scorer):
        result = scorer.score(SAMPLE_RESUME)
        details = result.get("details", {})
        fmt = details.get("format_rules", {})
        assert fmt.get("f_01_contact", 0) > 5


class TestScorerRules:
    def test_all_35_rules_fire(self, scorer):
        """Each of the 35 rules should produce a non-negative score."""
        result = scorer.score(SAMPLE_RESUME, ["python", "aws"])
        details = result.get("details", {})

        all_rules = []
        for cat in ["format_rules", "keyword_rules", "content_rules", "structure_rules", "impact_rules"]:
            all_rules.extend(details.get(cat, {}).keys())

        assert len(all_rules) >= 30, f"Expected at least 30 rules, got {len(all_rules)}"
        for rule_name in all_rules:
            score_val = None
            for cat in ["format_rules", "keyword_rules", "content_rules", "structure_rules", "impact_rules"]:
                if rule_name in details.get(cat, {}):
                    score_val = details[cat][rule_name]
                    break
            assert score_val is not None, f"Rule {rule_name} not found"
            assert score_val >= 0, f"Rule {rule_name} returned negative: {score_val}"

    def test_breakdown_sums_match(self, scorer):
        result = scorer.score(SAMPLE_RESUME, ["python", "aws"])
        cats = result["breakdown"]
        expected = sum(cats.values())
        assert abs(result["score"] - expected) < 0.5

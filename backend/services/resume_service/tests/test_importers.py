"""Tests for LinkedIn/GitHub importers."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pytest

from services.resume_service.importers import (
    _extract_linkedin_name,
    _extract_linkedin_headline,
    _extract_linkedin_location,
    _extract_github_name,
    _extract_github_bio,
    _extract_skills_from_repos,
    _build_projects_from_repos,
    _detect_repo_language,
    import_linkedin,
    import_github,
)

LINKEDIN_HTML_SAMPLE = """<html><body>
<h1>Jane Smith</h1>
<div class="text-body-medium">Senior Software Engineer at TechCorp</div>
<span class="text-body-small">San Francisco Bay Area</span>
<div class="pvs-list__container">
  <span>Python</span>
  <span>Docker</span>
  <span>Kubernetes</span>
</div>
</body></html>"""

GITHUB_HTML_SAMPLE = """<html><body>
<span itemprop="name">JohnDev</span>
<meta name="description" content="JohnDev · Full-stack developer">
<div class="user-profile-bio">Building great software with Python and React.</div>
<span itemprop="homeLocation">New York, NY</span>
<div class="pinned-item-list-item">
  <a href="/john/my-project"><span>my-project</span></a>
  <p>A Python web application built with FastAPI and Docker</p>
</div>
</body></html>"""


class TestLinkedInParser:
    def test_extract_name(self):
        assert _extract_linkedin_name(LINKEDIN_HTML_SAMPLE) == "Jane Smith"

    def test_extract_headline(self):
        headline = _extract_linkedin_headline(LINKEDIN_HTML_SAMPLE)
        assert headline and "Senior Software Engineer" in headline

    def test_extract_location(self):
        loc = _extract_linkedin_location(LINKEDIN_HTML_SAMPLE)
        assert loc and "San Francisco" in loc

    def test_empty_html(self):
        assert _extract_linkedin_name("") is None
        assert _extract_linkedin_headline("") is None
        assert _extract_linkedin_location("") is None


class TestGitHubParser:
    def test_extract_name(self):
        assert _extract_github_name(GITHUB_HTML_SAMPLE) == "JohnDev"

    def test_extract_bio(self):
        bio = _extract_github_bio(GITHUB_HTML_SAMPLE)
        assert bio and "Python" in bio

    def test_extract_location(self):
        loc = _extract_github_location(GITHUB_HTML_SAMPLE)
        assert loc == "New York, NY"

    def test_empty_html(self):
        assert _extract_github_name("") is None
        assert _extract_github_bio("") is None


class TestRepoParsing:
    def test_detect_language(self):
        assert _detect_repo_language("python-api", "FastAPI backend") == "python"
        assert _detect_repo_language("react-dashboard", "A React app") == "javascript"
        assert _detect_repo_language("go-service", "A Go microservice") == "go"

    def test_extract_skills_from_repos(self):
        repos = [
            {"name": "api", "description": "Built with Python and FastAPI",
             "language": "python", "url": ""},
            {"name": "frontend", "description": "React and TypeScript project",
             "language": "javascript", "url": ""},
        ]
        skills = _extract_skills_from_repos(repos)
        assert "python" in skills
        assert "fastapi" in skills or "javascript" in skills

    def test_build_projects_from_repos(self):
        repos = [{"name": "my-app", "description": "Great app", "url": "https://github.com/a/b"}]
        projects = _build_projects_from_repos(repos)
        assert len(projects) == 1
        assert projects[0]["name"] == "my-app"


class TestImportErrors:
    @pytest.mark.asyncio
    async def test_invalid_linkedin_url(self):
        with pytest.raises(ValueError, match="Invalid LinkedIn URL"):
            await import_linkedin("https://example.com/profile")

    @pytest.mark.asyncio
    async def test_linkedin_404(self):
        with pytest.raises(ValueError, match="HTTP"):
            await import_linkedin("https://www.linkedin.com/in/nonexistent-user-123456")

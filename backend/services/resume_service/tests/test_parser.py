"""Unit tests for resume parser — text extraction and entity recognition."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pytest

from services.resume_service.parser import (
    ResumeParser,
    _extract_email,
    _extract_phone,
    _extract_skills,
    _segment_text,
    extract_text_from_txt,
)

SAMPLE_RESUME = b"""
John Smith
john.smith@example.com | (555) 123-4567 | New York, NY

SUMMARY
Senior Full-Stack Developer with expertise in Python, React, and AWS cloud infrastructure.

EXPERIENCE
Senior Developer, Tech Corp (2020-01 - 2023-06)
- Designed and implemented REST APIs using Python and FastAPI
- Led migration to Docker and Kubernetes, reducing deployment time by 50%
- Built real-time analytics using Kafka and Elasticsearch

Junior Developer, StartupCo (2017-06 - 2019-12)
- Developed React frontend with TypeScript and Redux
- Built CI/CD pipelines with GitHub Actions

EDUCATION
BSc Computer Science, Stanford University (2013-2017), GPA 3.7

SKILLS
Python, JavaScript, TypeScript, React, FastAPI, Docker, Kubernetes, AWS, Kafka,
Elasticsearch, PostgreSQL, Redis, Git, CI/CD, GitHub Actions, Linux
"""


@pytest.fixture
def parser():
    return ResumeParser()


class TestTextExtraction:
    def test_extract_txt(self):
        text = extract_text_from_txt(SAMPLE_RESUME)
        assert "John Smith" in text
        assert "john.smith@example.com" in text

    def test_extract_txt_encoding(self):
        data = "Résumé with UTF-8".encode("utf-8")
        text = extract_text_from_txt(data)
        assert "Résumé" in text


class TestEntityExtraction:
    def test_extract_email(self):
        assert _extract_email("Contact: alice@example.com") == "alice@example.com"
        assert _extract_email("No email here") is None

    def test_extract_email_complex(self):
        assert _extract_email("Email: user.name+tag@company.co.uk") == "user.name+tag@company.co.uk"

    def test_extract_phone(self):
        assert _extract_phone("Call +1 555-123-4567") == "+1 555-123-4567"
        assert _extract_phone("Phone: (555) 123-4567") is not None

    def test_extract_skills(self):
        text = "Experienced in Python, Docker, and AWS cloud services."
        skills = _extract_skills(text)
        assert "python" in skills
        assert "docker" in skills
        assert "aws" in skills

    def test_extract_skills_case_insensitive(self):
        skills = _extract_skills("PYTHON and React")
        assert "python" in skills
        assert "react" in skills

    def test_extract_skills_unknown(self):
        skills = _extract_skills("Expert in RandomUnknownTool")
        assert "randomunknowntool" not in skills


class TestSegmentation:
    def test_segment_sections(self):
        text = """John Doe
SUMMARY
Experienced engineer.
EXPERIENCE
Worked at Acme Corp.
EDUCATION
MIT graduate."""
        sections = _segment_text(text)
        assert "summary" in sections
        assert "experience" in sections
        assert "education" in sections

    def test_segment_header_in_header(self):
        sections = _segment_text("Jane Doe\njohn@example.com\nEXPERIENCE\nCompany XYZ")
        assert "header" in sections
        assert "experience" in sections


class TestParserIntegration:
    @pytest.mark.asyncio
    async def test_parse_txt(self, parser):
        content, raw_text, confidence = await parser.parse("resume.txt", SAMPLE_RESUME)
        assert content.email == "john.smith@example.com"
        assert content.full_name is not None
        assert "python" in content.skills
        assert "docker" in content.skills
        assert 0 < confidence <= 1.0

    @pytest.mark.asyncio
    async def test_parse_returns_raw_text(self, parser):
        content, raw_text, confidence = await parser.parse("resume.txt", SAMPLE_RESUME)
        assert "John Smith" in raw_text

    @pytest.mark.asyncio
    async def test_parse_empty_file(self, parser):
        content, raw_text, confidence = await parser.parse("empty.txt", b"")
        assert raw_text == ""
        assert confidence <= 0.3

    @pytest.mark.asyncio
    async def test_parse_unsupported_ext(self, parser):
        with pytest.raises(ValueError, match="Unsupported"):
            await parser.parse("file.xyz", b"data")


class TestImageOCR:
    def test_extract_text_from_image_module_exists(self):
        """OCR 模块函数名称应存在。"""
        from services.resume_service.parser import extract_text_from_image
        assert callable(extract_text_from_image)

    def test_png_jpg_supported(self):
        """PNG 和 JPG 应在支持列表中。"""
        from services.resume_service.parser import extract_text
        # 验证不会 raise ValueError for image extensions
        # 实际 OCR 需要 tesseract，在 CI 中可能不可用，所以只测导入
        try:
            extract_text("resume.png", b"fake_png_data")
        except ValueError as e:
            if "Unsupported" in str(e):
                pytest.fail("PNG should be supported")
        except ImportError:
            pass  # Tesseract not installed in test env, acceptable

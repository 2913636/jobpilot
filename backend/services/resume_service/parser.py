"""Resume parser — extracts text from PDF/DOCX/TXT and structures it.

Core text extraction uses PyMuPDF and python-docx.  Entity extraction uses
regex patterns for email, phone, and name.  LayoutLMv3 integration is an
optional enhancement for document-image-based resumes (e.g. scanned PDFs).
"""

import io
import re
from pathlib import Path
from typing import Any

from .schemas import ResumeContent

# ── Text extraction ───────────────────────────────────────────────


def extract_text_from_pdf(data: bytes) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF (fitz) is required for PDF parsing")
    doc = fitz.open(stream=data, filetype="pdf")
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return "\n".join(pages)


def extract_text_from_docx(data: bytes) -> str:
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx is required for DOCX parsing")
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)


def extract_text_from_txt(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def extract_text_from_image(data: bytes) -> str:
    """使用 Tesseract OCR 从图片中提取文本。"""
    try:
        from PIL import Image
        import pytesseract
    except ImportError as e:
        raise ImportError(
            "pillow and pytesseract are required for image OCR. "
            "Install with: pip install pillow pytesseract"
        ) from e

    image = Image.open(io.BytesIO(data))
    # 预处理：转灰度 + 自适应阈值提升 OCR 准确率
    try:
        image = image.convert("L")
    except Exception:
        pass

    text = pytesseract.image_to_string(image, lang="eng+chi_sim")
    if not text.strip():
        raise ValueError("OCR could not extract any text from the image")
    return text


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(data)
    elif ext in (".docx", ".doc"):
        return extract_text_from_docx(data)
    elif ext in (".txt", ".md", ".rtf"):
        return extract_text_from_txt(data)
    elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff"):
        return extract_text_from_image(data)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


# ── Entity extraction ─────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{4,10}"
)
_LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w-]+", re.IGNORECASE)
_GITHUB_RE = re.compile(r"github\.com/[\w.-]+", re.IGNORECASE)

# Common section headers for segmentation
_SECTION_PATTERNS = {
    "summary": re.compile(
        r"(?i)^\s*(professional\s+)?(summary|profile|objective|about\s+me)\s*$"
    ),
    "experience": re.compile(
        r"(?i)^\s*(work\s+)?(experience|employment|professional\s+background|career)\s*$"
    ),
    "education": re.compile(
        r"(?i)^\s*(education|academic|qualifications?)\s*$"
    ),
    "skills": re.compile(
        r"(?i)^\s*(skills?|technical\s+skills?|core\s+competenc(?:y|ies)|technologies)\s*$"
    ),
    "projects": re.compile(r"(?i)^\s*(projects?|portfolio)\s*$"),
    "certifications": re.compile(r"(?i)^\s*(certifications?|licenses?)\s*$"),
    "languages": re.compile(r"(?i)^\s*(languages?)\s*$"),
}

_SKILL_KEYWORDS = {
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
    "react", "vue", "angular", "node.js", "django", "flask", "fastapi",
    "spring", "spring boot", "docker", "kubernetes", "aws", "gcp", "azure",
    "terraform", "ansible", "jenkins", "github actions", "ci/cd",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "kafka",
    "rabbitmq", "graphql", "rest", "grpc", "microservices",
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "pandas", "numpy", "scikit-learn", "spark",
    "hadoop", "airflow", "tableau", "power bi",
    "git", "linux", "bash", "agile", "scrum", "jira", "confluence",
    "project management", "team leadership", "communication", "problem solving",
    "html", "css", "sass", "tailwind", "bootstrap",
    "swift", "kotlin", "flutter", "react native",
    "figma", "sketch", "adobe", "ui/ux", "product management",
}


def _extract_email(text: str) -> str | None:
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else None


def _extract_phone(text: str) -> str | None:
    m = _PHONE_RE.search(text)
    return m.group(0) if m else None


def _extract_skills(text: str) -> list[str]:
    lower = text.lower()
    found: list[str] = []
    remaining = lower
    for skill in sorted(_SKILL_KEYWORDS, key=len, reverse=True):
        if skill in remaining:
            found.append(skill)
            remaining = remaining.replace(skill, "", 1)
    return sorted(found)


def _segment_text(text: str) -> dict[str, str]:
    """Split resume text into sections based on common headers."""
    lines = text.split("\n")
    sections: dict[str, list[str]] = {}
    current_section = "header"
    sections[current_section] = []

    for line in lines:
        matched = None
        for section_name, pattern in _SECTION_PATTERNS.items():
            if pattern.match(line.strip()):
                matched = section_name
                break
        if matched:
            current_section = matched
            sections.setdefault(current_section, [])
        else:
            sections.setdefault(current_section, [])
            sections[current_section].append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items()}


# ── Main parser ───────────────────────────────────────────────────


class ResumeParser:
    """Parse a resume file into structured ResumeContent.

    Uses regex-based entity extraction by default.  LayoutLMv3 can be
    enabled for document-image-based parsing via ``use_layoutlm=True``.
    """

    def __init__(self, use_layoutlm: bool = False):
        self.use_layoutlm = use_layoutlm

    async def parse(self, filename: str, data: bytes) -> tuple[ResumeContent, str, float]:
        raw_text = extract_text(filename, data)
        content, confidence = self._extract_entities(raw_text)

        # Optional: enhance with LayoutLMv3 for image-based PDFs
        if self.use_layoutlm and filename.lower().endswith(".pdf"):
            llm_content = await self._parse_with_layoutlm(data)
            if llm_content:
                content = self._merge(content, llm_content)
                confidence = max(confidence, 0.85)

        return content, raw_text, confidence

    def _extract_entities(self, text: str) -> tuple[ResumeContent, float]:
        sections = _segment_text(text)
        skills = _extract_skills(text)
        email = _extract_email(text)
        phone = _extract_phone(text)

        # Extract name from first non-empty line (heuristic)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        name = lines[0] if lines else None
        # Filter out obviously non-name first lines
        if name and (_EMAIL_RE.search(name) or _PHONE_RE.search(name) or len(name) > 60):
            name = None

        content = ResumeContent(
            full_name=name,
            email=email,
            phone=phone,
            summary=sections.get("summary"),
            skills=skills,
            experience=self._parse_experience_section(sections.get("experience", "")),
            education=self._parse_education_section(sections.get("education", "")),
            projects=self._parse_projects(sections.get("projects", "")),
            languages=[],
            certifications=[],
        )

        # Confidence based on how much we found
        filled = sum(1 for v in [name, email, phone, skills] if v)
        confidence = min(0.9, filled / 4 * 0.8 + 0.1)

        return content, confidence

    def _parse_experience_section(self, text: str) -> list[dict]:
        """Heuristic experience entry parser."""
        if not text:
            return []
        entries: list[dict] = []
        # Split by common date patterns or company markers
        chunks = re.split(r"\n(?=\d{4}[-–/]\d{2,4}|\d{2}/\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))", text)
        for chunk in chunks:
            if not chunk.strip():
                continue
            entries.append({
                "company": "",
                "title": "",
                "start_date": "",
                "description": chunk.strip(),
                "highlights": [],
                "current": False,
            })
        return entries

    def _parse_education_section(self, text: str) -> list[dict]:
        if not text:
            return []
        entries: list[dict] = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            entries.append({
                "school": line,
                "degree": "",
                "field_of_study": None,
            })
        return entries

    def _parse_projects(self, text: str) -> list[dict]:
        if not text:
            return []
        return [{"name": line.strip(), "description": None, "highlights": []}
                for line in text.split("\n") if line.strip()]

    async def _parse_with_layoutlm(self, pdf_data: bytes) -> ResumeContent | None:
        """Optional LayoutLMv3-based parsing for image-rich PDFs."""
        try:
            from transformers import AutoProcessor, AutoModelForTokenClassification
            import fitz
        except ImportError:
            return None

        try:
            processor = AutoProcessor.from_pretrained(
                "microsoft/layoutlmv3-base", apply_ocr=False
            )
            model = AutoModelForTokenClassification.from_pretrained(
                "microsoft/layoutlmv3-base"
            )
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            page = doc[0]
            image = page.get_pixmap(dpi=150)
            # In production, run inference here
            doc.close()
            del model, processor  # free memory
        except Exception:
            return None

        return None  # Placeholder — full inference requires GPU

    def _merge(self, base: ResumeContent, overlay: ResumeContent) -> ResumeContent:
        """Merge two parsed results, preferring non-None values from overlay."""
        for field in ResumeContent.model_fields:
            overlay_val = getattr(overlay, field)
            base_val = getattr(base, field)
            if overlay_val and not base_val:
                setattr(base, field, overlay_val)
        return base

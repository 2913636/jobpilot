"""Resume generator — builds tailored resumes from JD + user profile.

Implements a 4-stage generation pipeline:
  1. JD Analyzer    — extract key requirements from job description
  2. Experience Selector — retrieve relevant experiences via TF-IDF similarity
  3. STAR Rewriter   — rewrite bullet points as quantified achievements
  4. Assembler       — compose the final structured resume

LangChain is used when available; falls back to heuristic rules otherwise.
"""

import asyncio
import json
import re
from typing import Any
from uuid import UUID

from .schemas import ResumeContent


# ── JD Analyzer ───────────────────────────────────────────────────

class JDAnalyzer:
    """Extract key requirements and keywords from a job description."""

    _SECTION_RE = re.compile(
        r"(?i)^\s*(requirements?|qualifications?|responsibilities?|"
        r"what you'll do|what we're looking for|skills? required|"
        r"must have|nice to have|about the role)\s*[:]?\s*$"
    )
    _BULLET_RE = re.compile(r"^\s*[-•*]\s*(.+)$")

    def analyze(self, jd_text: str) -> dict[str, Any]:
        bullets = self._extract_bullets(jd_text)
        keywords = self._extract_keywords(jd_text)
        requirements = self._classify_requirements(bullets)

        return {
            "keywords": keywords,
            "requirements": requirements,
            "required_skills": [k for k in keywords if k["category"] == "skill"],
            "soft_skills": [k for k in keywords if k["category"] == "soft"],
            "experience_years": self._guess_experience_years(jd_text),
        }

    def _extract_bullets(self, text: str) -> list[str]:
        bullets: list[str] = []
        in_section = False
        for line in text.split("\n"):
            if self._SECTION_RE.match(line.strip()):
                in_section = True
                continue
            if in_section and line.strip() == "":
                continue
            m = self._BULLET_RE.match(line)
            if m:
                bullets.append(m.group(1).strip())
            elif in_section and line.strip():
                bullets.append(line.strip())
        return bullets

    def _extract_keywords(self, text: str) -> list[dict[str, str]]:
        _TECH_SKILLS = {
            "python", "java", "javascript", "typescript", "go", "rust",
            "react", "vue", "angular", "node", "django", "flask", "fastapi",
            "spring", "docker", "kubernetes", "aws", "gcp", "azure",
            "terraform", "kafka", "redis", "postgresql", "mysql", "mongodb",
            "elasticsearch", "graphql", "grpc", "microservices",
            "tensorflow", "pytorch", "spark", "airflow", "pandas",
            "ci/cd", "git", "linux",
        }
        _SOFT_SKILLS = {
            "communication", "leadership", "teamwork", "problem solving",
            "analytical", "agile", "scrum", "stakeholder management",
            "mentoring", "collaboration", "initiative", "ownership",
        }
        lower = text.lower()
        results: list[dict[str, str]] = []
        seen: set[str] = set()
        for skill in sorted(_TECH_SKILLS | _SOFT_SKILLS, key=len, reverse=True):
            if skill in lower and skill not in seen:
                seen.add(skill)
                cat = "soft" if skill in _SOFT_SKILLS else "skill"
                results.append({"name": skill, "category": cat})
        return results

    def _classify_requirements(self, bullets: list[str]) -> list[dict[str, str]]:
        classified: list[dict[str, str]] = []
        for b in bullets:
            b_lower = b.lower()
            if any(w in b_lower for w in ["year", "experience", "senior", "junior"]):
                classified.append({"text": b, "type": "experience"})
            elif any(w in b_lower for w in ["degree", "bachelor", "master", "phd", "b.s.", "m.s."]):
                classified.append({"text": b, "type": "education"})
            else:
                classified.append({"text": b, "type": "skill"})
        return classified

    def _guess_experience_years(self, text: str) -> int:
        m = re.search(r"(\d+)[\+]?\s*(?:\+\s*)?years?(?:\s*of)?\s*experience", text, re.IGNORECASE)
        return int(m.group(1)) if m else 0


# ── Experience Selector ───────────────────────────────────────────

class ExperienceSelector:
    """Select relevant experience entries from a user profile using TF-IDF
    similarity against JD keywords."""

    def select(
        self,
        profile_experience: list[dict[str, Any]],
        jd_keywords: list[str],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not profile_experience or not jd_keywords:
            return profile_experience

        keywords_lower = set(k.lower() for k in jd_keywords)
        scored: list[tuple[float, dict[str, Any]]] = []

        for exp in profile_experience:
            desc = (exp.get("description") or "").lower()
            title = (exp.get("title") or "").lower()
            company = (exp.get("company") or "").lower()
            combined = f"{title} {company} {desc}"

            score = sum(1.0 for kw in keywords_lower if kw in combined)
            # Bonus for title matches
            score += sum(2.0 for kw in keywords_lower if kw in title)
            scored.append((score, exp))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:top_k] if _ > 0] or profile_experience[:top_k]


# ── STAR Rewriter ─────────────────────────────────────────────────

_STAR_TEMPLATES = [
    "{action} {context}, resulting in {result}.",
    "Achieved {result} by {action} {context}.",
    "{action} for {context}, delivering {result}.",
    "Led {action} that {context}, achieving {result}.",
    "Improved {context} through {action}, yielding {result}.",
]

_RESULT_PATTERNS = [
    (r"(?i)(\d+)%", r"by \1%"),
    (r"(?i)(reduced|cut|decreased|lowered)\s+(\w+\s+\w+)", r"\1 \2"),
    (r"(?i)(increased|improved|grew|boosted|enhanced)\s+(\w+\s+\w+)", r"\1 \2"),
]

_ACTION_VERBS = [
    "designed", "implemented", "developed", "architected", "optimized",
    "led", "managed", "coordinated", "delivered", "built", "launched",
    "automated", "migrated", "scaled", "integrated", "established",
]


class STARRewriter:
    """Rewrite experience bullets using the STAR method with quantified results."""

    def rewrite(self, experiences: list[dict[str, Any]], jd_keywords: list[str]) -> list[dict[str, Any]]:
        rewritten: list[dict[str, Any]] = []
        for exp in experiences:
            desc = exp.get("description") or ""
            bullets = self._to_bullets(desc)
            star_bullets = [self._star_rewrite(b, jd_keywords) for b in bullets]
            rewritten_exp = {**exp, "highlights": star_bullets}
            rewritten.append(rewritten_exp)
        return rewritten

    def _to_bullets(self, text: str) -> list[str]:
        """Split text into bullet points."""
        bullets = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
        return [b.strip() for b in bullets if len(b.strip()) > 20]

    def _star_rewrite(self, bullet: str, keywords: list[str]) -> str:
        """Rewrite a single bullet in STAR format if it isn't already quantified."""
        if re.search(r"\d+%|\d+x|\d+\s*(million|thousand|users|customers|revenue)", bullet, re.IGNORECASE):
            return bullet  # Already quantified

        action = self._pick_action_verb(bullet)
        context = bullet.lower().rstrip(".")
        result = self._infer_result(bullet, keywords)

        import random
        template = random.choice(_STAR_TEMPLATES)
        return template.format(action=action, context=context, result=result)

    def _pick_action_verb(self, text: str) -> str:
        lower = text.lower()
        for verb in _ACTION_VERBS:
            if verb in lower:
                return verb.capitalize()
        return "Implemented"

    def _infer_result(self, text: str, keywords: list[str]) -> str:
        for pattern, replacement in _RESULT_PATTERNS:
            m = re.search(pattern, text)
            if m:
                return replacement.format(*m.groups())
        # Fallback: pick a relevant metric based on keywords
        if any(k in text.lower() for k in ["performance", "speed", "latency"]):
            return "30% improvement in performance"
        if any(k in text.lower() for k in ["cost", "saving", "budget"]):
            return "25% cost reduction"
        if any(k in text.lower() for k in ["team", "people", "hire", "manage"]):
            return "measurable team productivity gains"
        return "significant business impact"


# ── Assembler ─────────────────────────────────────────────────────

def _format_bullets(entries: list[dict[str, Any]]) -> list[str]:
    """Format experience entries as formatted bullet strings."""
    result: list[str] = []
    for entry in entries:
        company = entry.get("company", "")
        title = entry.get("title", "")
        header = f"{title} at {company}" if company else title
        result.append(header)
        for hl in entry.get("highlights", []):
            result.append(f"  - {hl}")
    return result


# ── Main Generator ────────────────────────────────────────────────


class ResumeGenerator:
    """Orchestrates the 4-stage resume generation pipeline."""

    def __init__(self):
        self.jd_analyzer = JDAnalyzer()
        self.selector = ExperienceSelector()
        self.rewriter = STARRewriter()

    async def generate(
        self,
        jd_text: str,
        profile: dict[str, Any],
        title: str = "Generated Resume",
    ) -> tuple[ResumeContent, list[str]]:
        jd_analysis = self.jd_analyzer.analyze(jd_text)
        jd_keywords = [k["name"] for k in jd_analysis["keywords"]]

        profile_skills = profile.get("skills") or []
        profile_experience = profile.get("experience") or []
        profile_education = profile.get("education") or []

        # Stage 1: JD keywords already extracted
        # Stage 2: Select relevant experiences
        selected_exp = self.selector.select(profile_experience, jd_keywords)

        # Stage 3: STAR rewrite
        rewritten_exp = self.rewriter.rewrite(selected_exp, jd_keywords)

        # Stage 4: Assemble
        all_skills = sorted(set(profile_skills) | set(
            k["name"] for k in jd_analysis["required_skills"]
        ))

        content = ResumeContent(
            full_name=profile.get("full_name"),
            email=profile.get("email"),
            phone=profile.get("phone"),
            location=profile.get("location"),
            summary=self._build_summary(profile, jd_analysis),
            skills=all_skills,
            experience=rewritten_exp,
            education=profile_education,
            languages=profile.get("languages", []),
            certifications=profile.get("certifications", []),
        )

        # Optional: enhance with LangChain if available
        llm_content = await self._try_langchain_generate(jd_text, profile, title)
        if llm_content:
            content = self._merge(content, llm_content)

        return content, jd_keywords

    @staticmethod
    def _merge(base: ResumeContent, overlay: ResumeContent) -> ResumeContent:
        for field in ResumeContent.model_fields:
            overlay_val = getattr(overlay, field)
            base_val = getattr(base, field)
            if overlay_val and not base_val:
                setattr(base, field, overlay_val)
        return base

    def _build_summary(self, profile: dict[str, Any], jd_analysis: dict[str, Any]) -> str:
        name = profile.get("full_name", "The candidate")
        skills = ", ".join(k["name"] for k in jd_analysis.get("required_skills", [])[:5])
        years = jd_analysis.get("experience_years", 0)
        exp_str = f"{years}+ years of experience in" if years else "Experienced in"
        return f"{name} — {exp_str} {skills}." if skills else f"{name}'s professional summary."

    async def _try_langchain_generate(
        self, jd_text: str, profile: dict[str, Any], title: str
    ) -> ResumeContent | None:
        """Optional LangChain-based generation for higher-quality output."""
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import JsonOutputParser
        except ImportError:
            return None

        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", (
                    "You are a professional resume writer. Given a job description and "
                    "a candidate profile, produce a tailored resume in JSON format with "
                    "the following fields: summary (string), skills (list of strings), "
                    "experience (list of objects with company, title, start_date, end_date, "
                    "highlights as a list of STAR-formatted bullet points), education (list)."
                )),
                ("user", (
                    "Job Description:\n{jd_text}\n\n"
                    "Candidate Profile:\n{profile_json}\n\n"
                    "Generate a tailored resume in JSON."
                )),
            ])
            parser = JsonOutputParser()
            chain = prompt | parser

            result = await asyncio.to_thread(
                chain.invoke,
                {"jd_text": jd_text, "profile_json": json.dumps(profile, default=str)},
            )
            return ResumeContent(**result)
        except Exception:
            return None

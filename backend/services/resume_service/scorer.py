"""ATS (Applicant Tracking System) resume scorer.

Evaluates resumes against 35 rules across 5 categories:
  - Format (10 rules)  — file structure, length, contact completeness
  - Keywords (8 rules) — JD keyword coverage, density, placement
  - Content (7 rules)  — action verbs, quantifiable results, grammar
  - Structure (5 rules) — logical ordering, section balance
  - Impact (5 rules)   — STAR usage, metrics, differentiation
"""

import math
import re
from collections import Counter
from typing import Any


class ATSScorer:
    """Score a resume on a 0-100 scale with detailed breakdown."""

    # ── Format Rules (10) ─────────────────────────────────────────

    def _rule_contact_completeness(self, text: str) -> float:
        """Check: email + phone + name present → 10 points."""
        has_email = bool(re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text))
        has_phone = bool(re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{7,}", text))
        has_name = len(text.strip().split("\n")[0]) < 60
        score = (has_email * 4 + has_phone * 3 + has_name * 3)
        return score

    def _rule_length_score(self, text: str) -> float:
        """Ideal resume is 300-900 words (1-2 pages)."""
        words = len(text.split())
        if 300 <= words <= 900:
            return 5.0
        elif 200 <= words <= 1100:
            return 3.0
        elif words > 0:
            return 1.0
        return 0.0

    def _rule_no_photo_check(self, text: str) -> float:
        """Photos on resumes can cause ATS rejection."""
        return 2.0  # Can't detect reliably from text

    def _rule_standard_sections(self, text: str) -> float:
        """Has summary + experience + education + skills sections."""
        sections = 0
        lower = text.lower()
        for kw in ["summary", "profile", "objective"]:
            if kw in lower:
                sections += 1
                break
        if re.search(r"(?i)experience|employment|work history", text):
            sections += 1
        if re.search(r"(?i)education|academic|university|college", text):
            sections += 1
        if re.search(r"(?i)skills?|technical|technologies|competencies", text):
            sections += 1
        return min(4.0, sections * 1.0) * 3.75  # max 15

    def _rule_file_format_check(self, text: str) -> float:
        """No garbled text from bad PDF extraction → 3 pts."""
        garbled_ratio = len(re.findall(r"[^\x20-\x7E\s]", text)) / max(1, len(text))
        if garbled_ratio < 0.05:
            return 3.0
        elif garbled_ratio < 0.15:
            return 1.5
        return 0.0

    def _rule_font_check(self) -> float:
        return 2.0  # can't check from plain text

    def _rule_margin_whitespace(self, text: str) -> float:
        """Check for reasonable line lengths (60-100 chars)."""
        lines = [l for l in text.split("\n") if l.strip()]
        if not lines:
            return 0.0
        good_lines = sum(1 for l in lines if 50 <= len(l) <= 120)
        ratio = good_lines / len(lines)
        return 2.0 * min(1.0, ratio)

    def _rule_consistent_formatting(self, text: str) -> float:
        """Check for consistent date formats and bullet styles."""
        date_formats = len(set(re.findall(r"\d{4}[-/]\d{2}", text)))
        if date_formats <= 1:
            return 3.0
        return 1.5

    def _rule_no_tables_columns(self, text: str) -> float:
        """Tables and columns confuse ATS parsers (check for multiple spaces)."""
        multi_space_lines = sum(1 for l in text.split("\n") if "    " in l)
        if multi_space_lines < 3:
            return 2.0
        return 1.0

    def _rule_pdf_text_extractable(self, text: str) -> float:
        """Enough text was extracted (at least 100 chars)."""
        return 5.0 if len(text) > 100 else 0.0

    # ── Keyword Rules (8) ─────────────────────────────────────────

    def _keyword_rules(self, text: str, jd_keywords: list[str]) -> dict[str, float]:
        results: dict[str, float] = {}
        lower = text.lower()
        kw_lower = [k.lower() for k in jd_keywords]

        if not kw_lower:
            return {f"kw_{i}": 0.0 for i in range(1, 9)}

        found = [k for k in kw_lower if k in lower]
        coverage = len(found) / len(kw_lower)

        results["kw_1_coverage"] = coverage * 10.0  # Keyword coverage
        results["kw_2_exact_match"] = len([k for k in kw_lower if re.search(rf"\b{re.escape(k)}\b", lower)]) / max(1, len(kw_lower)) * 5.0  # Exact matches
        results["kw_3_density"] = min(5.0, sum(lower.count(k) for k in found) / max(1, len(lower.split())) * 500)  # Keyword density
        results["kw_4_top_placement"] = 3.0 if any(k in lower[:500] for k in kw_lower) else 0.0  # Keywords in first 500 chars
        results["kw_5_title_match"] = 2.0 if any(k in lower[:100] for k in kw_lower) else 0.0  # Keywords near title
        results["kw_6_section_relevance"] = 2.0 if any(k in (text.split("\n")[0] or "").lower() for k in kw_lower) else 1.0
        results["kw_7_frequency"] = min(3.0, sum(lower.count(k) for k in found) / max(1, len(kw_lower)))  # Average frequency
        results["kw_8_context_match"] = coverage * 2.0  # Bonus for overall relevance

        return results

    # ── Content Rules (7) ─────────────────────────────────────────

    def _content_rules(self, text: str) -> dict[str, float]:
        words = text.split()
        lower = text.lower()

        action_verbs = r"\b(designed|implemented|developed|led|managed|built|created|launched|optimized|automated|architected|delivered|established|coordinated|achieved|increased|reduced|improved|scaled)\b"
        action_count = len(re.findall(action_verbs, lower))

        metrics = len(re.findall(r"\d+%|\d+x|\$\d+|\d+\s*(million|thousand|billion)", lower))
        bullets = len(re.findall(r"^[-•*]\s", text, re.MULTILINE))
        grammar_issues = len(re.findall(r"\b(i|i'm|i've|me|my|myself)\b", lower))

        return {
            "c_1_action_verbs": min(8.0, action_count * 1.5),  # Action verb usage
            "c_2_quantifiable": min(10.0, metrics * 3.0),  # Quantifiable results
            "c_3_grammar": max(0.0, 5.0 - grammar_issues * 1.0),  # Grammar (no first-person)
            "c_4_word_count": min(5.0, len(words) / 150 * 5.0),  # Appropriate length
            "c_5_bullet_points": min(4.0, bullets * 0.8),  # Bullet point usage
            "c_6_no_cliches": 3.0 if "hardworking" not in lower and "team player" not in lower else 1.0,  # Avoid clichés
            "c_7_job_specific": 3.0,  # Job-specific content (baseline)
        }

    # ── Structure Rules (5) ───────────────────────────────────────

    def _structure_rules(self, text: str) -> dict[str, float]:
        sections = ["summary", "experience", "education", "skills"]
        present = [s for s in sections if s in text.lower()]

        lines = [l for l in text.split("\n") if l.strip()]
        lengths = [len(l) for l in lines] if lines else [0]

        return {
            "s_1_section_order": min(5.0, len(present) * 1.25),  # Section count
            "s_2_experience_first": 3.0 if "experience" in text.lower()[:len(text)//3] else 1.0,  # Experience placement
            "s_3_balanced_sections": 2.0 if 3 <= len(present) <= 5 else 1.0,  # Balanced sections
            "s_4_readability": min(3.0, sum(1 for l in lengths if 20 < l < 150) / max(1, len(lengths)) * 3.0),  # Readable lines
            "s_5_header_clarity": 2.0,  # Headers are clear (baseline)
        }

    # ── Impact Rules (5) ──────────────────────────────────────────

    def _impact_rules(self, text: str) -> dict[str, float]:
        lower = text.lower()
        star_pattern = re.findall(
            r"(?:increased|decreased|improved|reduced|achieved|delivered|generated|launched).*?(?:\d+%|\$\d+|\d+x)",
            lower,
        )
        awards = len(re.findall(r"\b(award|recognition|honor|patent|published|speaker)\b", lower))
        leadership = len(re.findall(r"\b(led|managed|directed|supervised|mentored|coached)\b", lower))
        metrics_count = len(re.findall(r"\d+%|\$\d+|\d+x|\d+\s*(million|thousand)", lower))

        return {
            "i_1_star_format": min(8.0, len(star_pattern) * 2.0),  # STAR format usage
            "i_2_metrics_count": min(8.0, metrics_count * 2.0),  # Quantified results count
            "i_3_awards": min(4.0, awards * 2.0),  # Awards/recognition
            "i_4_leadership": min(5.0, leadership * 1.5),  # Leadership indicators
            "i_5_differentiation": min(5.0, (len(star_pattern) + awards + leadership) * 1.0),  # Overall differentiation
        }

    # ── Main scoring ──────────────────────────────────────────────

    def score(
        self, text: str, jd_keywords: list[str] | None = None
    ) -> dict[str, Any]:
        """Score a resume and return full breakdown with suggestions."""
        jd_keywords = jd_keywords or []

        # Collect all rule scores
        format_scores: dict[str, float] = {
            "f_01_contact": self._rule_contact_completeness(text),
            "f_02_length": self._rule_length_score(text),
            "f_03_no_photo": self._rule_no_photo_check(text),
            "f_04_sections": self._rule_standard_sections(text),
            "f_05_no_garbled": self._rule_file_format_check(text),
            "f_06_font": self._rule_font_check(),
            "f_07_margins": self._rule_margin_whitespace(text),
            "f_08_consistent": self._rule_consistent_formatting(text),
            "f_09_no_tables": self._rule_no_tables_columns(text),
            "f_10_extractable": self._rule_pdf_text_extractable(text),
        }
        kw_scores = self._keyword_rules(text, jd_keywords)
        content_scores = self._content_rules(text)
        struct_scores = self._structure_rules(text)
        impact_scores = self._impact_rules(text)

        # Category totals
        format_total = sum(format_scores.values())
        kw_total = sum(kw_scores.values())
        content_total = sum(content_scores.values())
        struct_total = sum(struct_scores.values())
        impact_total = sum(impact_scores.values())

        overall = format_total + kw_total + content_total + struct_total + impact_total
        overall = round(min(100.0, overall), 1)

        # Missing keywords
        lower = text.lower()
        missing = [k for k in jd_keywords if k.lower() not in lower]

        # Suggestions engine
        suggestions: list[str] = []
        if format_scores["f_01_contact"] < 8:
            suggestions.append("Add or verify your email and phone number")
        if format_scores["f_02_length"] < 3:
            suggestions.append("Adjust resume length to 1-2 pages (300-900 words)")
        if format_scores["f_04_sections"] < 10:
            suggestions.append("Add standard sections: Summary, Experience, Education, Skills")
        if kw_scores.get("kw_1_coverage", 0) < 5:
            suggestions.append("Increase keyword coverage — more JD keywords needed")
        if kw_scores.get("kw_3_density", 0) < 2:
            suggestions.append("Improve keyword density throughout the resume")
        if content_scores.get("c_1_action_verbs", 0) < 5:
            suggestions.append("Use more action verbs (designed, implemented, led, optimized)")
        if content_scores.get("c_2_quantifiable", 0) < 5:
            suggestions.append("Add quantifiable results (%, $, numbers)")
        if content_scores.get("c_3_grammar", 0) < 4:
            suggestions.append("Avoid first-person pronouns (I, me, my)")
        if impact_scores.get("i_1_star_format", 0) < 4:
            suggestions.append("Rewrite bullets in STAR format (Situation, Task, Action, Result)")
        if impact_scores.get("i_3_awards", 0) < 2:
            suggestions.append("Consider adding awards, recognitions, or publications")
        if missing:
            suggestions.append(f"Missing keywords: {', '.join(missing[:5])}")
        if impact_scores.get("i_4_leadership", 0) < 3:
            suggestions.append("Highlight leadership or mentoring experience")
        if struct_scores.get("s_4_readability", 0) < 2:
            suggestions.append("Improve readability with shorter paragraphs and bullet points")

        return {
            "score": overall,
            "breakdown": {
                "format": round(format_total, 1),
                "keywords": round(kw_total, 1),
                "content": round(content_total, 1),
                "structure": round(struct_total, 1),
                "impact": round(impact_total, 1),
            },
            "missing_keywords": missing[:10],
            "suggestions": suggestions[:8],
            "details": {
                "format_rules": format_scores,
                "keyword_rules": kw_scores,
                "content_rules": content_scores,
                "structure_rules": struct_scores,
                "impact_rules": impact_scores,
            },
        }

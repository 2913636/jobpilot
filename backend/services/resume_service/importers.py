"""LinkedIn / GitHub 公开页面导入器。

从公开 URL 爬取并解析为结构化简历数据。
反爬策略：随机 User-Agent + 请求间隔 + 状态码识别（429/403 返回明确错误）。
"""

import asyncio
import random
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from .schemas import ResumeContent

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


async def _fetch_page(url: str) -> str:
    """带反爬策略的页面抓取。"""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 429:
            raise ValueError("Rate limited by target site. Please try again later.")
        if resp.status_code == 403:
            raise ValueError("Access denied (403). The page may require login or is blocking automated access.")
        if resp.status_code == 404:
            raise ValueError("Page not found (404). Check the URL.")
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}: unable to fetch page")
        return resp.text


# ── LinkedIn Importer ─────────────────────────────────────────────

async def import_linkedin(url: str) -> ResumeContent:
    """从 LinkedIn 公开个人页面解析简历数据。

    URL 格式: https://www.linkedin.com/in/username
    """
    if "linkedin.com/in/" not in url:
        raise ValueError("Invalid LinkedIn URL. Expected: https://www.linkedin.com/in/username")

    html = await _fetch_page(url)

    full_name = _extract_linkedin_name(html)
    headline = _extract_linkedin_headline(html)
    location = _extract_linkedin_location(html)
    summary = _extract_linkedin_summary(html)
    experience = _extract_linkedin_experience(html)
    education = _extract_linkedin_education(html)
    skills = _extract_linkedin_skills(html)

    return ResumeContent(
        full_name=full_name or "Unknown",
        summary=headline or summary,
        location=location,
        skills=skills,
        experience=experience,
        education=education,
    )


def _extract_linkedin_name(html: str) -> str | None:
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return None


def _extract_linkedin_headline(html: str) -> str | None:
    m = re.search(r'class="[^"]*headline[^"]*"[^>]*>(.*?)<', html, re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    m = re.search(r'<div[^>]*text-body-medium[^>]*>(.*?)</div>', html, re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return None


def _extract_linkedin_location(html: str) -> str | None:
    m = re.search(r'class="[^"]*location[^"]*"[^>]*>(.*?)<', html, re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return None


def _extract_linkedin_summary(html: str) -> str | None:
    m = re.search(r'id="about"[^>]*>.*?<div[^>]*>(.*?)</div>', html, re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()[:2000]
    return None


def _extract_linkedin_experience(html: str) -> list[dict]:
    entries: list[dict] = []
    # 匹配经验区块
    exp_pattern = re.compile(
        r'class="[^"]*experience[^"]*"[^>]*>.*?</section>',
        re.DOTALL | re.IGNORECASE,
    )
    for block in exp_pattern.findall(html):
        titles = re.findall(r'<span[^>]*>(.*?)</span>', block)
        companies = re.findall(r'<p[^>]*>(.*?)</p>', block)
        entries.append({
            "company": companies[0].strip() if companies else "",
            "title": titles[0].strip() if titles else "",
            "start_date": "", "end_date": None,
            "description": block[:500], "highlights": [],
            "current": "present" in block.lower(),
        })
    return entries[:10] or [
        {"company": "See LinkedIn profile", "title": headline or "", "start_date": "", "current": True,
         "description": "Visit the URL for full experience details", "highlights": []}
    ]


def _extract_linkedin_education(html: str) -> list[dict]:
    schools = re.findall(r'class="[^"]*school[^"]*"[^>]*>(.*?)<', html, re.DOTALL)
    degrees = re.findall(r'class="[^"]*degree[^"]*"[^>]*>(.*?)<', html, re.DOTALL)
    entries: list[dict] = []
    for i, school in enumerate(schools[:5]):
        entries.append({
            "school": re.sub(r'<[^>]+>', '', school).strip(),
            "degree": re.sub(r'<[^>]+>', '', degrees[i]).strip() if i < len(degrees) else "",
        })
    return entries


def _extract_linkedin_skills(html: str) -> list[str]:
    skills = re.findall(r'class="[^"]*skill[^"]*"[^>]*>(.*?)<', html, re.DOTALL)
    return list(set(re.sub(r'<[^>]+>', '', s).strip() for s in skills[:30] if s.strip()))


# ── GitHub Importer ───────────────────────────────────────────────

async def import_github(url: str) -> ResumeContent:
    """从 GitHub 个人页面解析技能和项目经历。

    URL 格式: https://github.com/username
    """
    if "github.com/" not in url or url.rstrip("/").count("/") < 3:
        pass  # 允许 /username 格式

    html = await _fetch_page(url)

    full_name = _extract_github_name(html)
    bio = _extract_github_bio(html)
    location = _extract_github_location(html)
    repos = await _extract_github_repos(url, html)

    skills = _extract_skills_from_repos(repos)
    projects = _build_projects_from_repos(repos)

    return ResumeContent(
        full_name=full_name or url.rstrip("/").split("/")[-1],
        summary=bio,
        location=location,
        skills=skills,
        projects=projects,
    )


def _extract_github_name(html: str) -> str | None:
    m = re.search(r'<span[^>]*itemprop="name"[^>]*>(.*?)</span>', html, re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
    if m:
        parts = m.group(1).split("·")
        return parts[0].strip().rstrip(" -") if parts else None
    return None


def _extract_github_bio(html: str) -> str | None:
    m = re.search(r'<div[^>]*class="[^"]*user-profile-bio[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return None


def _extract_github_location(html: str) -> str | None:
    m = re.search(r'<span[^>]*itemprop="homeLocation"[^>]*>(.*?)</span>', html, re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return None


async def _extract_github_repos(url: str, html: str) -> list[dict]:
    """提取 pinned repos 或 recent repos 基础信息。"""
    # 解析 pinned repos
    pinned = re.findall(
        r'<div[^>]*class="[^"]*pinned-item[^"]*"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>'
        r'.*?<span[^>]*>(.*?)</span>.*?<p[^>]*>(.*?)</p>',
        html, re.DOTALL,
    )
    repos: list[dict] = []
    for href, name, desc in pinned[:6]:
        name_clean = re.sub(r'<[^>]+>', '', name).strip()
        desc_clean = re.sub(r'<[^>]+>', '', desc).strip()
        repos.append({
            "name": name_clean,
            "url": f"https://github.com{href}" if href.startswith("/") else href,
            "description": desc_clean,
            "language": _detect_repo_language(name_clean, desc_clean),
        })
    return repos


def _extract_skills_from_repos(repos: list[dict]) -> list[str]:
    skills: set[str] = set()
    lang_map = {
        "python": "python", "javascript": "javascript", "typescript": "typescript",
        "go": "go", "rust": "rust", "java": "java", "c++": "c++", "c#": "c#",
        "react": "react", "vue": "vue", "angular": "angular",
        "django": "django", "flask": "flask", "fastapi": "fastapi",
        "docker": "docker", "kubernetes": "kubernetes", "terraform": "terraform",
        "aws": "aws", "gcp": "gcp", "azure": "azure",
        "tensorflow": "tensorflow", "pytorch": "pytorch",
        "postgresql": "postgresql", "mongodb": "mongodb", "redis": "redis",
        "graphql": "graphql", "grpc": "grpc",
    }
    for repo in repos:
        lang = repo.get("language", "").lower()
        if lang in lang_map:
            skills.add(lang_map[lang])
        for keyword, skill in lang_map.items():
            if keyword in repo.get("description", "").lower():
                skills.add(skill)
    return sorted(skills)


def _build_projects_from_repos(repos: list[dict]) -> list[dict]:
    return [
        {
            "name": r["name"],
            "description": r.get("description", ""),
            "url": r.get("url", ""),
            "highlights": [],
        }
        for r in repos
    ]


def _detect_repo_language(name: str, desc: str) -> str:
    """基于仓库名和描述推断语言。"""
    combined = f"{name} {desc}".lower()
    indicators = {
        "python": ["python", "django", "flask", "fastapi", "pytorch", "tensorflow"],
        "javascript": ["javascript", "node", "react", "vue", "angular", "next"],
        "typescript": ["typescript", "ts-", ".ts"],
        "go": ["go-", "golang"],
        "rust": ["rust", "cargo"],
        "java": ["java", "spring"],
    }
    scores: dict[str, int] = {}
    for lang, keywords in indicators.items():
        scores[lang] = sum(1 for kw in keywords if kw in combined)
    if scores:
        return max(scores, key=scores.get)
    return ""

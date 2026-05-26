"""智能填表引擎 — LLM 分析目标表单字段，匹配用户档案键值。

流程：
  1. 解析页面 HTML，提取所有 input/select/textarea 字段
  2. 用规则 + LLM 将表单字段映射到用户档案键
  3. 生成 FieldMapping 列表返回给浏览器扩展
"""

import json
import re
from typing import Any
from urllib.parse import urlparse


# ── 内置字段映射规则 ──────────────────────────────────────────────

# 常见的表单字段名 -> 用户档案键的映射表
_FIELD_LABEL_MAP: dict[str, str] = {
    # 个人信息
    "email": "email", "e-mail": "email", "邮箱": "email", "电子邮箱": "email",
    "full_name": "full_name", "name": "full_name", "姓名": "full_name", "名字": "full_name",
    "first_name": "first_name", "last_name": "last_name",
    "phone": "phone", "tel": "phone", "mobile": "phone", "电话": "phone", "手机": "phone",
    "location": "location", "city": "location", "城市": "location", "地址": "location",
    # 履历
    "summary": "summary", "bio": "summary", "个人简介": "summary", "自我介绍": "summary",
    "skills": "skills", "技术栈": "skills", "专业技能": "skills",
    # 工作经历
    "experience": "experience", "work_experience": "experience", "工作经历": "experience",
    "current_company": "current_company", "最近公司": "current_company",
    "current_title": "current_title", "最近职位": "current_title",
    # 教育
    "education": "education", "degree": "degree", "education_level": "degree",
    "学历": "degree", "教育": "education", "school": "school", "毕业院校": "school",
    # 链接
    "linkedin": "linkedin_url", "linkedin_url": "linkedin_url",
    "github": "github_url", "github_url": "github_url",
    "website": "website", "个人网站": "website", "portfolio": "website",
    # 其他
    "resume": "resume_file", "附件简历": "resume_file", "upload_resume": "resume_file",
    "cover_letter": "cover_letter", "求职信": "cover_letter",
    "expected_salary": "expected_salary", "期望薪资": "expected_salary",
    "start_date": "available_date", "入职时间": "available_date",
}


# 常见招聘网站的表单字段模式（按域名）
_DOMAIN_PATTERNS: dict[str, list[dict]] = {
    "zhipin.com": [
        {"selector": "input[name='name']", "profile_key": "full_name"},
        {"selector": "input[name='phone']", "profile_key": "phone"},
        {"selector": "input[name='email']", "profile_key": "email"},
        {"selector": "textarea[name='description']", "profile_key": "summary"},
    ],
    "linkedin.com": [
        {"selector": "input[id*='first-name']", "profile_key": "first_name"},
        {"selector": "input[id*='last-name']", "profile_key": "last_name"},
        {"selector": "input[name*='email']", "profile_key": "email"},
        {"selector": "input[name*='phone']", "profile_key": "phone"},
        {"selector": "input[id*='headline']", "profile_key": "summary"},
    ],
    "lagou.com": [
        {"selector": "input[name='name']", "profile_key": "full_name"},
        {"selector": "input[name='email']", "profile_key": "email"},
        {"selector": "input[name='phone']", "profile_key": "phone"},
        {"selector": "textarea[name='advantage']", "profile_key": "summary"},
    ],
    "liepin.com": [
        {"selector": "input[name*='name']", "profile_key": "full_name"},
        {"selector": "input[name*='email']", "profile_key": "email"},
        {"selector": "input[name*='mobile']", "profile_key": "phone"},
    ],
}


class FormFiller:
    """智能表单填充引擎。"""

    def __init__(self, user_profile: dict[str, Any]):
        self.profile = user_profile

    async def analyze(self, url: str, page_html: str | None = None) -> list[dict[str, Any]]:
        """分析目标 URL，返回字段映射列表。"""
        domain = urlparse(url).netloc.lower()

        # 1. 尝试内置域名规则
        for known_domain, patterns in _DOMAIN_PATTERNS.items():
            if known_domain in domain:
                return self._apply_patterns(patterns)

        # 2. 如果有 HTML，解析表单字段
        if page_html:
            return await self._analyze_html(url, page_html)

        # 3. LLM 分析
        return await self._llm_analyze(url, page_html)

    def _apply_patterns(self, patterns: list[dict]) -> list[dict[str, Any]]:
        """应用预定义的表单字段模式。"""
        results: list[dict[str, Any]] = []
        for p in patterns:
            profile_key = p["profile_key"]
            value = self._get_profile_value(profile_key)
            confidence = 0.9 if value else 0.3
            results.append({
                "form_field": p["selector"],
                "profile_key": profile_key,
                "suggested_value": value or "",
                "confidence": confidence,
                "field_type": "text",
            })
        return results

    async def _analyze_html(self, url: str, html: str) -> list[dict[str, Any]]:
        """解析 HTML 中的表单字段并匹配。"""
        results: list[dict[str, Any]] = []

        # 提取所有 input 和 textarea
        inputs = re.findall(
            r'<(?:input|textarea|select)\s+[^>]*?(?:name|id|placeholder)=["\']([^"\']+)["\'][^>]*>',
            html, re.IGNORECASE,
        )
        labels = re.findall(
            r'<label[^>]*?for=["\']([^"\']+)["\'][^>]*>(.*?)</label>',
            html, re.IGNORECASE,
        )

        seen_fields: set[str] = set()
        for field_name in inputs:
            field_lower = field_name.lower().strip()
            if field_lower in seen_fields:
                continue
            seen_fields.add(field_lower)

            # 匹配字段名
            profile_key = self._match_field(field_lower)
            confidence = 0.7 if profile_key else 0.1
            if not profile_key:
                # 尝试从 label 文本匹配
                for label_for, label_text in labels:
                    if label_for.lower() == field_lower:
                        profile_key = self._match_field(label_text.lower())
                        confidence = 0.8 if profile_key else 0.2
                        break

            value = self._get_profile_value(profile_key) if profile_key else ""
            results.append({
                "form_field": f"[name='{field_name}']",
                "profile_key": profile_key or "unknown",
                "suggested_value": value or "",
                "confidence": confidence,
                "field_type": "text",
            })

        return results

    async def _llm_analyze(self, url: str, html: str | None) -> list[dict[str, Any]]:
        """使用 LLM 分析表单（降级到通用规则）。"""
        # 尝试 Claude API
        try:
            import anthropic
            import os
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key and html:
                return await self._call_claude(api_key, url, html)
        except Exception:
            pass

        # 降级：返回常见字段映射
        domain = urlparse(url).netloc
        return [
            {"form_field": "input[name='email']", "profile_key": "email",
             "suggested_value": self.profile.get("email", ""), "confidence": 0.6, "field_type": "email"},
            {"form_field": "input[name='name']", "profile_key": "full_name",
             "suggested_value": self.profile.get("full_name", ""), "confidence": 0.6, "field_type": "text"},
            {"form_field": "input[name='phone']", "profile_key": "phone",
             "suggested_value": self.profile.get("phone", ""), "confidence": 0.5, "field_type": "tel"},
            {"form_field": "textarea[name='description']", "profile_key": "summary",
             "suggested_value": self.profile.get("summary", ""), "confidence": 0.4, "field_type": "textarea"},
        ]

    async def _call_claude(self, api_key: str, url: str, html: str) -> list[dict[str, Any]]:
        client = __import__("anthropic").Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": (
                f"Analyze this job application form at {url}.\n\n"
                f"HTML:\n{html[:8000]}\n\n"
                f"User profile keys: {list(self.profile.keys())}\n\n"
                f"Return a JSON array of field mappings. Each object has: "
                f"form_field (CSS selector), profile_key, suggested_value, confidence (0-1)."
            )}],
        )
        try:
            return json.loads(msg.content[0].text)
        except json.JSONDecodeError:
            return []

    def _match_field(self, field_name: str) -> str | None:
        """将表单字段名匹配到用户档案键。"""
        # 直接匹配
        if field_name in _FIELD_LABEL_MAP:
            return _FIELD_LABEL_MAP[field_name]
        # 子串匹配
        for key, profile_key in _FIELD_LABEL_MAP.items():
            if key in field_name or field_name in key:
                return profile_key
        return None

    def _get_profile_value(self, key: str) -> str:
        """从用户档案获取值。"""
        val = self.profile.get(key, "")
        if isinstance(val, list):
            return ", ".join(str(v) for v in val[:10])
        if isinstance(val, dict):
            return json.dumps(val, ensure_ascii=False, indent=2)
        return str(val) if val else ""

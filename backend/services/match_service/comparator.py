"""岗位对比服务 — 多维度对比 + LLM 报告生成。

维度：技能成长、薪资、WLB、公司前景、地点
"""

import asyncio
import json
from typing import Any
from uuid import UUID


COMPARE_PROMPT = """你是一位资深职业规划师。请从以下维度对比分析这个岗位：

{job_summaries}

请生成一份 Markdown 格式的对比报告，覆盖以下维度：
1. 技能成长 — 该岗位能提供哪些技能提升机会
2. 薪资竞争力 — 薪资范围和行业水平对比
3. 工作生活平衡 — 工作强度和弹性制度
4. 公司前景 — 公司发展阶段和行业地位
5. 地点便利性 — 通勤、生活成本、城市发展

每个维度给出 1-10 分的评分。最后给出总结建议。
"""

DIMENSION_WEIGHTS = {
    "skill_growth": 0.25,
    "salary": 0.25,
    "work_life_balance": 0.20,
    "company_prospect": 0.20,
    "location": 0.10,
}

_DIMENSION_ZH = {
    "skill_growth": "技能成长",
    "salary": "薪资竞争力",
    "work_life_balance": "工作生活平衡",
    "company_prospect": "公司前景",
    "location": "地点便利性",
}


class JobComparator:
    """多岗位对比分析器。"""

    def __init__(self, db):
        self.db = db

    async def compare(self, jobs: list[dict[str, Any]]) -> dict[str, Any]:
        """对比多个岗位并生成报告。"""
        job_names = [j.get("title", "") for j in jobs]
        job_ids = [j.get("id", "") for j in jobs]

        # 结构化评分
        dimensions = self._compute_dimensions(jobs)

        # 雷达图数据
        radar_data: dict[str, list[float]] = {}
        for dim_key, dim_name in _DIMENSION_ZH.items():
            radar_data[dim_name] = [dim.scores.get(str(j.get("id", "")), 0) for dim in dimensions.get(dim_key, [])]

        # LLM 报告
        report_md = await self._generate_report(jobs, dimensions)

        # 收集各维度数据
        dim_list: list[dict] = []
        for dim_key, dim_name in _DIMENSION_ZH.items():
            dim_data = dimensions.get(dim_key, {})
            scores = {}
            for j in jobs:
                jid = str(j.get("id", ""))
                scores[j.get("title", "")] = dim_data.get("scores", {}).get(jid, 5.0)
            dim_list.append({
                "name": dim_name,
                "scores": scores,
                "analysis": dim_data.get("analysis", ""),
            })

        return {
            "report_markdown": report_md,
            "dimensions": dim_list,
            "radar_data": radar_data,
            "job_names": job_names,
        }

    def _compute_dimensions(self, jobs: list[dict[str, Any]]) -> dict[str, Any]:
        """基于规则计算各维度评分。"""
        dimensions: dict[str, Any] = {}

        for dim_key in DIMENSION_WEIGHTS:
            scores: dict[str, float] = {}
            for j in jobs:
                jid = str(j.get("id", ""))
                scores[jid] = self._score_dimension(j, dim_key)
            dimensions[dim_key] = {
                "scores": scores,
                "analysis": self._analysis_for_dimension(dim_key, scores, jobs),
            }

        return dimensions

    def _score_dimension(self, job: dict[str, Any], dim: str) -> float:
        """为单个岗位的单个维度打分。"""
        skills = job.get("skills") or []
        salary_max = job.get("salary_max") or 0
        location = (job.get("location") or "").lower()

        if dim == "skill_growth":
            return min(10, len(skills) * 1.2 + 4)
        elif dim == "salary":
            if salary_max > 500000:
                return 9.0
            elif salary_max > 300000:
                return 7.0
            elif salary_max > 150000:
                return 5.5
            elif salary_max > 0:
                return 4.0
            return 3.0
        elif dim == "work_life_balance":
            # 基于员工规模、行业推断（未来可从外部数据获取）
            if "远程" in (job.get("title", "") + (job.get("description", ""))):
                return 8.0
            return 6.0
        elif dim == "company_prospect":
            company = (job.get("company") or "").lower()
            top_companies = {"google", "microsoft", "apple", "meta", "amazon", "nvidia",
                             "alibaba", "tencent", "bytedance", "huawei", "baidu", "meituan"}
            if any(t in company for t in top_companies):
                return 9.0
            return 6.0
        elif dim == "location":
            tier1 = {"beijing", "shanghai", "shenzhen", "hangzhou", "guangzhou"}
            if any(c in location for c in tier1):
                return 8.0
            return 6.0
        return 5.0

    def _analysis_for_dimension(self, dim: str, scores: dict[str, float],
                                 jobs: list[dict[str, Any]]) -> str:
        best_job = max(scores, key=scores.get)
        best_title = next((j["title"] for j in jobs if str(j.get("id", "")) == best_job), "")
        dim_name = _DIMENSION_ZH.get(dim, dim)
        return f"在{dim_name}方面，'{best_title}'表现最佳，评分 {scores[best_job]:.1f}/10。"

    async def _generate_report(self, jobs: list[dict[str, Any]],
                                dimensions: dict[str, Any]) -> str:
        """生成 Markdown 对比报告。尝试调用 LLM，失败则用模板。"""
        job_summaries = self._build_job_summary(jobs)
        prompt = COMPARE_PROMPT.format(job_summaries=job_summaries)

        # 尝试调用 Claude API
        try:
            llm_report = await self._call_llm(prompt)
            if llm_report:
                return llm_report
        except Exception:
            pass

        # 模板降级
        return self._template_report(jobs, dimensions)

    async def _call_llm(self, prompt: str) -> str | None:
        """调用 LLM API 生成报告。"""
        try:
            import anthropic
            import os
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                return None
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        except Exception:
            return None

    def _build_job_summary(self, jobs: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for j in jobs:
            parts.append(
                f"## {j.get('title', 'N/A')} @ {j.get('company', 'N/A')}\n"
                f"- 地点: {j.get('location', 'N/A')}\n"
                f"- 薪资: {j.get('salary_min', '-')} ~ {j.get('salary_max', '-')} {j.get('salary_currency', '')}\n"
                f"- 技能: {', '.join(j.get('skills', []) or [])}\n"
                f"- 描述: {(j.get('description', '') or '')[:300]}\n"
            )
        return "\n\n".join(parts)

    def _template_report(self, jobs: list[dict[str, Any]],
                          dimensions: dict[str, Any]) -> str:
        """模板化对比报告（无 LLM 时的降级方案）。"""
        lines = ["# 岗位对比报告\n"]
        for j in jobs:
            lines.append(f"## {j.get('title', 'N/A')} @ {j.get('company', 'N/A')}\n")
            lines.append(f"- 地点: {j.get('location', 'N/A')}")
            lines.append(f"- 薪资: {j.get('salary_min', '-')} ~ {j.get('salary_max', '-')} {j.get('salary_currency', 'CNY')}")
            lines.append(f"- 技能: {', '.join(j.get('skills', []) or [])}\n")

        lines.append("\n## 各维度分析\n")
        for dim_key, dim_name in _DIMENSION_ZH.items():
            dim_data = dimensions.get(dim_key, {})
            lines.append(f"### {dim_name}\n")
            lines.append(dim_data.get("analysis", ""))
            lines.append("")

        lines.append("\n## 总结建议\n")
        lines.append("根据以上分析，建议优先选择技能成长空间大、薪资竞争力强的岗位。")
        return "\n".join(lines)

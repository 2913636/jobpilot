"""Boss直聘爬虫 — 抓取职位列表和详情。

使用 scrapy-playwright 处理动态渲染的职位列表页。
触发方式：API 调用或 Temporal workflow。
"""

import json
import re
from typing import Any

from scrapy import Spider, Request


class BossZhipinSpider(Spider):
    name = "boss"
    allowed_domains = ["zhipin.com", "bosszhipin.com"]

    def __init__(self, keyword: str = "python", location: str = "",
                 max_pages: int = 3, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.keyword = keyword
        self.location = location
        self.max_pages = max_pages
        self.page = 1

    def start_requests(self):
        base_url = (
            f"https://www.zhipin.com/web/geek/job"
            f"?query={self.keyword}&city={self.location}&page={self.page}"
        )
        yield Request(
            url=base_url,
            callback=self.parse_list,
            meta={"playwright": True, "playwright_include_page": True},
        )

    async def parse_list(self, response: Any) -> Any:
        page = response.meta.get("playwright_page")
        if page:
            await page.wait_for_selector(".job-list-box", timeout=15000)
            html = await page.content()
            # 用新的 response 继续解析
            from scrapy.http import HtmlResponse
            response = HtmlResponse(
                url=response.url, body=html.encode(), encoding="utf-8"
            )

        # 提取职位卡片
        cards = response.css(".job-card-wrapper")
        self.logger.info(f"Page {self.page}: found {len(cards)} jobs")

        for card in cards:
            yield self._parse_card(card, response)

        # 翻页
        if self.page < self.max_pages:
            self.page += 1
            next_url = (
                f"https://www.zhipin.com/web/geek/job"
                f"?query={self.keyword}&city={self.location}&page={self.page}"
            )
            yield Request(
                url=next_url,
                callback=self.parse_list,
                meta={"playwright": True, "playwright_include_page": True},
            )

        if page:
            await page.close()

    def _parse_card(self, card: Any, response: Any) -> dict[str, Any]:
        title = card.css(".job-name::text").get("").strip()
        company = card.css(".company-name::text").get("").strip()
        location = card.css(".job-area::text").get("").strip()
        salary = card.css(".salary::text").get("").strip()
        tags = card.css(".tag-list li::text").getall()
        job_url = card.css("a.job-card-left::attr(href)").get("")

        skills: list[str] = []
        experience: str | None = None
        education: str | None = None
        for tag in tags:
            if tag in ("本科", "硕士", "博士", "大专", "学历不限"):
                education = tag
            elif any(c in tag for c in "0123456789年"):
                experience = tag
            else:
                skills.append(tag)

        salary_min, salary_max, currency = self._parse_salary(salary)

        return {
            "title": title,
            "company": company,
            "description": "",
            "location": location,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_currency": currency,
            "skills": skills,
            "experience_level": experience,
            "education_level": education,
            "source": "boss",
            "source_url": f"https://www.zhipin.com{job_url}" if job_url else None,
            "source_id": self._extract_id(job_url),
            "remote": "远程" in (title or ""),
            "employment_type": "全职",
        }

    def _parse_salary(self, text: str) -> tuple[float | None, float | None, str]:
        """解析薪资文本，如 '15K-25K' 或 '20-30K·15薪'。"""
        if not text:
            return None, None, "CNY"
        # 处理 '20K-30K·15薪' 格式
        text = text.split("·")[0].strip()
        match = re.match(r"(\d+\.?\d*)\s*[Kk]?\s*-\s*(\d+\.?\d*)\s*([Kk])?", text)
        if match:
            lo = float(match.group(1))
            hi = float(match.group(2))
            unit = match.group(3)
            if unit and unit.lower() == "k":
                lo *= 1000
                hi *= 1000
            return lo, hi, "CNY"
        return None, None, "CNY"

    def _extract_id(self, url: str | None) -> str:
        if not url:
            return ""
        m = re.search(r"/job_detail/([a-f0-9]+)", url)
        return m.group(1) if m else ""

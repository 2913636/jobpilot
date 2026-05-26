"""LinkedIn 爬虫 — 抓取职位列表和基础信息。

使用 scrapy-playwright 处理登录页面和动态加载。
"""

import json
from typing import Any

from scrapy import Spider, Request


class LinkedInSpider(Spider):
    name = "linkedin"
    allowed_domains = ["linkedin.com", "www.linkedin.com"]

    def __init__(self, keyword: str = "python developer", location: str = "",
                 max_pages: int = 3, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.keyword = keyword
        self.location = location
        self.max_pages = max_pages
        self.start = 0

    def start_requests(self):
        query = f"{self.keyword} {self.location}".strip().replace(" ", "%20")
        url = (
            f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords={query}&location=&start={self.start}"
        )
        yield Request(url=url, callback=self.parse_list)

    def parse_list(self, response: Any) -> Any:
        cards = response.css(".job-search-card")
        self.logger.info(f"Start {self.start}: found {len(cards)} jobs")

        for card in cards:
            yield self._parse_card(card)

        # 翻页
        if len(cards) >= 25 and self.start < self.max_pages * 25:
            self.start += 25
            query = f"{self.keyword} {self.location}".strip().replace(" ", "%20")
            url = (
                f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                f"?keywords={query}&location=&start={self.start}"
            )
            yield Request(url=url, callback=self.parse_list)

    def _parse_card(self, card: Any) -> dict[str, Any]:
        title = card.css(".base-search-card__title::text").get("").strip()
        company = card.css(".base-search-card__subtitle a::text").get("").strip()
        location = card.css(".job-search-card__location::text").get("").strip()
        job_url = card.css(".base-card__full-link::attr(href)").get("")
        job_id = card.css("::attr(data-entity-urn)").get("")

        skills: list[str] = []

        return {
            "title": title,
            "company": company,
            "description": "",
            "location": location,
            "remote": "remote" in location.lower() if location else False,
            "salary_min": None,
            "salary_max": None,
            "salary_currency": "USD",
            "skills": skills,
            "experience_level": None,
            "education_level": None,
            "source": "linkedin",
            "source_url": job_url,
            "source_id": job_id.replace("urn:li:jobPosting:", "") if job_id else None,
            "employment_type": "全职",
        }

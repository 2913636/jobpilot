"""Scrapy pipeline — 将爬取的职位数据写入 Elasticsearch。

同时也保存到 PostgreSQL 通过 API 调用 match-service 自身。
"""

import logging

from .settings import ITEM_PIPELINES

logger = logging.getLogger(__name__)


class ElasticsearchPipeline:
    """将职位数据同步到 Elasticsearch 索引 'jobs'。"""

    def __init__(self):
        self.es = None

    async def open_spider(self, spider):
        try:
            from common.es import get_es_client
            self.es = await get_es_client()
        except Exception as e:
            logger.warning(f"ES client init failed (non-fatal): {e}")

    async def close_spider(self, spider):
        pass

    async def process_item(self, item: dict, spider) -> dict:
        if not self.es:
            return item

        doc = {
            "title": item.get("title"),
            "company": item.get("company"),
            "description": item.get("description"),
            "location": item.get("location"),
            "remote": item.get("remote", False),
            "salary_min": item.get("salary_min"),
            "salary_max": item.get("salary_max"),
            "salary_currency": item.get("salary_currency"),
            "skills": item.get("skills", []),
            "experience_level": item.get("experience_level"),
            "source": item.get("source"),
            "source_url": item.get("source_url"),
            "is_active": True,
        }

        source_id = item.get("source_id")
        doc_id = f"{item.get('source', '')}_{source_id}" if source_id else None

        try:
            if doc_id:
                await self.es.index(
                    index="jobs",
                    id=doc_id,
                    document=doc,
                    op_type="index",
                )
                spider.logger.debug(f"Indexed job: {doc['title']} at {doc['company']}")
        except Exception as e:
            spider.logger.error(f"ES index error: {e}")

        return item

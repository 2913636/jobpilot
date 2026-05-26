"""职位搜索 — Elasticsearch 全文检索。"""

from typing import Any

from elasticsearch import AsyncElasticsearch


class JobSearchService:
    """Elasticsearch 职位搜索，支持关键词、地点、远程过滤、分页。"""

    INDEX = "jobs"

    def __init__(self, es: AsyncElasticsearch):
        self.es = es

    async def search(
        self,
        q: str = "",
        location: str | None = None,
        remote: bool | None = None,
        experience_level: str | None = None,
        salary_min: float | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        must: list[dict] = []
        filters: list[dict] = []

        if q:
            must.append({
                "multi_match": {
                    "query": q,
                    "fields": ["title^3", "company^2", "description", "skills^2"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            })
        else:
            must.append({"match_all": {}})

        if location:
            filters.append({"term": {"location.keyword": location}})
        if remote is not None:
            filters.append({"term": {"remote": remote}})
        if experience_level:
            filters.append({"term": {"experience_level.keyword": experience_level}})
        if salary_min is not None:
            filters.append({"range": {"salary_max": {"gte": salary_min}}})

        body: dict[str, Any] = {
            "query": {
                "bool": {
                    "must": must,
                    "filter": filters + [{"term": {"is_active": True}}],
                }
            },
            "from": (page - 1) * page_size,
            "size": page_size,
            "sort": [{"_score": "desc"}, {"created_at": "desc"}],
            "highlight": {
                "fields": {"title": {}, "description": {"fragment_size": 150}}
            },
        }

        result = await self.es.search(index=self.INDEX, body=body)

        hits = result["hits"]["hits"]
        items: list[dict] = []
        for h in hits:
            source = h["_source"]
            source["id"] = h["_id"]
            # 添加高亮片段
            if "highlight" in h:
                source["highlight"] = h["highlight"]
            items.append(source)

        total = result["hits"]["total"]
        if isinstance(total, dict):
            total = total["value"]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def index_job(self, job: dict[str, Any]) -> None:
        """将职位写入 ES 索引。"""
        doc_id = str(job.get("id", ""))
        await self.es.index(index=self.INDEX, id=doc_id, document=job)

    async def delete_job(self, job_id: str) -> None:
        """从 ES 索引中删除职位。"""
        await self.es.delete(index=self.INDEX, id=job_id, ignore=[404])

    async def ensure_index(self) -> None:
        """创建索引（如不存在）。"""
        exists = await self.es.indices.exists(index=self.INDEX)
        if not exists:
            await self.es.indices.create(index=self.INDEX, body={
                "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                "mappings": {
                    "properties": {
                        "title": {"type": "text", "analyzer": "standard"},
                        "company": {"type": "text"},
                        "description": {"type": "text"},
                        "location": {"type": "keyword"},
                        "remote": {"type": "boolean"},
                        "salary_min": {"type": "float"},
                        "salary_max": {"type": "float"},
                        "skills": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "experience_level": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "is_active": {"type": "boolean"},
                        "created_at": {"type": "date"},
                    }
                }
            })

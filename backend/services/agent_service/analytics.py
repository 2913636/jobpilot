"""行为分析 — Faust 流处理 + 技能热度周期性聚合。

消费 Kafka "user-events" 主题，处理数据写入 MinIO 数据湖，
定期运行分析作业更新技能热度和公司热度等指标。
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any


class AnalyticsProcessor:
    """模拟 Faust 流处理器的分析引擎。

    在生产环境中替换为 Faust app，消费 Kafka 并写入 MinIO。
    """

    def __init__(self):
        self.buffer: list[dict] = []

    async def process_event(self, event: dict[str, Any]):
        """处理单个用户事件。"""
        self.buffer.append(event)

        # 每 100 条批量写入 MinIO
        if len(self.buffer) >= 100:
            await self._flush_to_minio()

    async def _flush_to_minio(self):
        """将缓冲的事件写入 MinIO 数据湖。"""
        if not self.buffer:
            return

        today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        hour = datetime.now(timezone.utc).strftime("%H")
        filename = f"user-events/{today}/events-{hour}-{len(self.buffer)}.json"

        try:
            from minio import Minio
            client = Minio(
                os.getenv("MINIO_ENDPOINT", "minio:9000"),
                access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
                secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
                secure=False,
            )
            bucket = os.getenv("MINIO_BUCKET", "jobpilot")
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)

            data = json.dumps(self.buffer, default=str).encode()
            client.put_object(bucket, filename, data=data, length=len(data))
        except ImportError:
            pass
        except Exception:
            pass

        self.buffer.clear()


# ── 周期性分析作业（Temporal 触发） ───────────────────────────────

async def run_skill_trend_analysis(db) -> dict[str, Any]:
    """分析技能热度趋势。

    从 user_events 和 jobs 表中聚合数据，更新 skill_trends 表。
    """
    from sqlalchemy import text

    # 统计技能出现频率
    result = await db.execute(text("""
        WITH skill_data AS (
            SELECT
                jsonb_array_elements_text(
                    COALESCE(payload->'skills', '[]'::jsonb)
                ) AS skill
            FROM user_events
            WHERE event_type = 'api.post'
              AND source LIKE '%/resume%'
              AND created_at > NOW() - INTERVAL '7 days'
        )
        SELECT LOWER(skill) AS name, COUNT(*) AS cnt
        FROM skill_data
        WHERE skill != ''
        GROUP BY LOWER(skill)
        ORDER BY cnt DESC
        LIMIT 50
    """))
    trends = {row.name: row.cnt for row in await result.fetchall()}

    # 更新 skill_trends 表
    for skill_name, freq in trends.items():
        await db.execute(
            text(
                "INSERT INTO skill_trends (skill_name, frequency, period, updated_at) "
                "VALUES (:name, :freq, 'weekly', NOW()) "
                "ON CONFLICT (skill_name) DO UPDATE SET frequency = :freq, updated_at = NOW()"
            ),
            {"name": skill_name, "freq": freq},
        )
    await db.commit()

    return {"skills_analyzed": len(trends), "total_events": sum(trends.values())}


async def run_company_trend_analysis(db) -> dict[str, Any]:
    """分析公司热度。"""
    from sqlalchemy import text

    result = await db.execute(text("""
        SELECT
            COALESCE(payload->>'company', 'unknown') AS company,
            COUNT(*) AS cnt
        FROM user_events
        WHERE event_type = 'api.post'
          AND source LIKE '%/applications%'
          AND created_at > NOW() - INTERVAL '30 days'
        GROUP BY payload->>'company'
        ORDER BY cnt DESC
        LIMIT 20
    """))
    companies = {row.company: row.cnt for row in await result.fetchall()}
    return {"companies_analyzed": len(companies), "trends": companies}

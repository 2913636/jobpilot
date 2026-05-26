"""Apply Service — 申请管理、状态机、智能填表、沟通记录同步。"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .form_filler import FormFiller
from .models import (
    ALL_STATUSES,
    VALID_TRANSITIONS,
    Application,
    Communication,
    FormTemplate,
)


class ApplyService:
    """申请管理 CRUD + 状态机。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: uuid.UUID, data: dict[str, Any]) -> Application:
        now = datetime.now(timezone.utc)
        app = Application(
            user_id=user_id, job_id=data["job_id"],
            resume_id=data.get("resume_id"), company=data.get("company"),
            title=data.get("title"), notes=data.get("notes", ""),
            source_url=data.get("source_url"),
            timeline=[{"status": "draft", "timestamp": now.isoformat(), "note": "申请已创建"}],
        )
        self.db.add(app)
        await self.db.commit()
        await self.db.refresh(app)
        return app

    async def get(self, app_id: uuid.UUID) -> Application | None:
        result = await self.db.execute(select(Application).where(Application.id == app_id))
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: uuid.UUID, status: str | None = None,
        page: int = 1, page_size: int = 50,
    ) -> tuple[list[Application], int]:
        stmt = select(Application).where(Application.user_id == user_id)
        if status:
            stmt = stmt.where(Application.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(Application.updated_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def update(self, app_id: uuid.UUID, data: dict[str, Any]) -> Application | None:
        app = await self.get(app_id)
        if not app:
            return None

        new_status = data.get("status")
        if new_status and new_status != app.status:
            if not self.validate_transition(app.status, new_status):
                raise ValueError(
                    f"无效状态转换: {app.status} -> {new_status}。"
                    f"允许: {VALID_TRANSITIONS.get(app.status, set())}"
                )
            now = datetime.now(timezone.utc)
            timeline = list(app.timeline or [])
            timeline.append({"status": new_status, "timestamp": now.isoformat(),
                            "note": data.get("notes", "")})
            app.timeline = timeline
            app.status = new_status

        for field in ("notes", "company", "title"):
            if field in data and data[field] is not None:
                setattr(app, field, data[field])

        app.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(app)
        return app

    def validate_transition(self, from_status: str, to_status: str) -> bool:
        return from_status in VALID_TRANSITIONS and to_status in VALID_TRANSITIONS[from_status]

    async def get_stats(self, user_id: uuid.UUID) -> dict[str, int]:
        result = await self.db.execute(
            select(Application.status, func.count(Application.id))
            .where(Application.user_id == user_id).group_by(Application.status)
        )
        stats: dict[str, int] = {s: 0 for s in ALL_STATUSES}
        for status, count in result.all():
            stats[status] = count
        return stats

    async def fill_form(self, url: str, user_profile: dict[str, Any],
                        page_html: str | None = None) -> dict[str, Any]:
        filler = FormFiller(user_profile)
        mappings = await filler.analyze(url, page_html)

        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        existing = await self.db.execute(
            select(FormTemplate).where(FormTemplate.domain == domain,
                                        FormTemplate.url_pattern == url)
        )
        template = existing.scalar_one_or_none()
        if template:
            template.field_mappings = {"fields": mappings}
            template.usage_count = (template.usage_count or 0) + 1
        else:
            template = FormTemplate(domain=domain, url_pattern=url,
                                     field_mappings={"fields": mappings})
            self.db.add(template)
        await self.db.commit()

        return {"url": url, "domain": domain, "mappings": mappings, "template_id": template.id}

    async def sync_chat(self, user_id: uuid.UUID, data: dict[str, Any]) -> Communication:
        comm = Communication(
            user_id=user_id, application_id=data.get("application_id"),
            platform=data.get("platform", "browser"),
            direction=data.get("direction", "in"),
            sender_name=data.get("sender_name"), content=data.get("content", ""),
            raw_payload=data.get("raw_payload"),
        )
        self.db.add(comm)
        await self.db.commit()
        await self.db.refresh(comm)
        return comm

    async def list_chats(
        self, user_id: uuid.UUID, application_id: uuid.UUID | None = None,
        page: int = 1, page_size: int = 50,
    ) -> tuple[list[Communication], int]:
        stmt = select(Communication).where(Communication.user_id == user_id)
        if application_id:
            stmt = stmt.where(Communication.application_id == application_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0
        stmt = stmt.order_by(Communication.synced_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

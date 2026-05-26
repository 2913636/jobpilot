"""题库社区 — CRUD、投票、搜索、SBERT 去重。"""

import uuid
from typing import Any


class QuestionBankService:
    """题库管理 + 投票 + 语义去重。"""

    def __init__(self, db):
        self.db = db

    async def create(self, author_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
        from .models import Question
        q = Question(
            author_id=author_id, title=data["title"], content=data["content"],
            category=data.get("category", "general"),
            difficulty=data.get("difficulty", "medium"),
            tags=data.get("tags", []),
            answer_guide=data.get("answer_guide"),
        )
        self.db.add(q)
        await self.db.commit()
        await self.db.refresh(q)

        # 异步生成 embedding（用于去重检索）
        await self._index_question(q)

        return q

    async def search(self, keyword: str, category: str | None = None,
                     difficulty: str | None = None, page: int = 1,
                     page_size: int = 20) -> tuple[list, int]:
        from sqlalchemy import func, select, or_
        from .models import Question

        stmt = select(Question)
        if keyword:
            stmt = stmt.where(
                or_(Question.title.ilike(f"%{keyword}%"),
                    Question.content.ilike(f"%{keyword}%"),
                    Question.tags.any(keyword.lower()))
            )
        if category:
            stmt = stmt.where(Question.category == category)
        if difficulty:
            stmt = stmt.where(Question.difficulty == difficulty)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(Question.upvotes.desc(), Question.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def vote(self, question_id: uuid.UUID, user_id: uuid.UUID,
                   vote_type: str) -> dict[str, int]:
        from .models import Question, QuestionVote
        from sqlalchemy import select

        # 检查是否已投票
        existing = await self.db.execute(
            select(QuestionVote).where(
                QuestionVote.question_id == question_id,
                QuestionVote.user_id == user_id,
            )
        )
        old_vote = existing.scalar_one_or_none()

        q = await self.db.get(Question, question_id)
        if not q:
            raise ValueError("题目不存在")

        if old_vote:
            # 撤销旧投票
            if old_vote.vote_type == "up":
                q.upvotes = max(0, q.upvotes - 1)
            else:
                q.downvotes = max(0, q.downvotes - 1)

            if old_vote.vote_type == vote_type:
                await self.db.delete(old_vote)
                await self.db.commit()
                return {"upvotes": q.upvotes, "downvotes": q.downvotes}

            old_vote.vote_type = vote_type
        else:
            v = QuestionVote(question_id=question_id, user_id=user_id, vote_type=vote_type)
            self.db.add(v)

        if vote_type == "up":
            q.upvotes += 1
        else:
            q.downvotes += 1

        await self.db.commit()
        return {"upvotes": q.upvotes, "downvotes": q.downvotes}

    async def check_duplicate(self, title: str, content: str) -> list[dict]:
        """基于 SBERT 的语义去重 — 返回相似题目列表。"""
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            model = SentenceTransformer("all-MiniLM-L6-v2")
            query_embedding = model.encode(title + " " + content[:500], convert_to_numpy=True)

            from sqlalchemy import select
            from .models import Question
            result = await self.db.execute(
                select(Question).where(Question.embedding_id.isnot(None)).limit(100)
            )
            candidates = result.scalars().all()

            if not candidates:
                return []

            # 简单余弦相似度比较
            duplicates: list[dict] = []
            for c in candidates:
                try:
                    cand_embedding = np.frombuffer(bytes.fromhex(c.embedding_id), dtype=np.float32)
                    sim = float(np.dot(query_embedding, cand_embedding) /
                               (np.linalg.norm(query_embedding) * np.linalg.norm(cand_embedding) + 1e-9))
                    if sim > 0.85:
                        duplicates.append({"id": str(c.id), "title": c.title, "similarity": round(sim, 3)})
                except Exception:
                    continue
            return sorted(duplicates, key=lambda x: x["similarity"], reverse=True)[:5]
        except ImportError:
            return []

    async def _index_question(self, q) -> None:
        """为题目生成 SBERT embedding。"""
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embedding = model.encode(q.title + " " + q.content[:500], convert_to_numpy=True)
            q.embedding_id = embedding.tobytes().hex()
            await self.db.commit()
        except ImportError:
            pass

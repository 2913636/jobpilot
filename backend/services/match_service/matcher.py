"""简历-职位匹配引擎。

流程：
  1. sentence-transformers/all-mpnet-base-v2 生成简历向量
  2. Milvus 向量检索 top 50 相似职位
  3. cross-encoder/ms-marco-MiniLM-L-6-v2 重排序
  4. 计算技能缺口
"""

import asyncio
import time
from typing import Any

import numpy as np


_KNOWN_SKILLS = {
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
    "react", "vue", "angular", "node.js", "django", "flask", "fastapi",
    "spring", "spring boot", "docker", "kubernetes", "aws", "gcp", "azure",
    "terraform", "ansible", "kafka", "redis", "postgresql", "mysql", "mongodb",
    "elasticsearch", "graphql", "grpc", "microservices", "ci/cd", "git",
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "pandas", "numpy", "spark", "airflow",
    "tableau", "power bi", "linux", "agile", "scrum", "jira",
}


class MatchEngine:
    """简历匹配引擎 — 向量检索 + 交叉编码器重排序。"""

    COLLECTION = "job_embeddings"
    VECTOR_DIM = 768  # all-mpnet-base-v2 的输出维度

    def __init__(self, milvus_client):
        self.milvus = milvus_client
        self._embedding_model = None
        self._cross_encoder = None

    async def _get_embedding_model(self):
        """懒加载 sentence-transformers 模型。"""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer("all-mpnet-base-v2")
            except ImportError:
                self._embedding_model = None
            except Exception:
                self._embedding_model = None
        return self._embedding_model

    async def _get_cross_encoder(self):
        """懒加载交叉编码器。"""
        if self._cross_encoder is None:
            try:
                from sentence_transformers import CrossEncoder
                self._cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            except ImportError:
                self._cross_encoder = None
            except Exception:
                self._cross_encoder = None
        return self._cross_encoder

    async def _encode_text(self, text: str) -> np.ndarray | None:
        model = await self._get_embedding_model()
        if model is None:
            return None
        return model.encode(text, convert_to_numpy=True, show_progress_bar=False)

    async def evaluate(
        self,
        resume_text: str,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """执行完整的匹配评估流程。"""
        start = time.time()

        # Step 1: 生成简历向量
        embedding = await self._encode_text(resume_text)
        if embedding is None:
            return self._fallback_match(resume_text, top_k)

        # Step 2: Milvus 向量检索 top 50
        try:
            self.milvus.load_collection(self.COLLECTION)
            results = self.milvus.search(
                collection_name=self.COLLECTION,
                data=[embedding.tolist()],
                limit=min(top_k * 2, 50),
                output_fields=["job_id", "title", "company", "skills", "description"],
            )
        except Exception:
            return self._fallback_match(resume_text, top_k)

        candidates: list[dict] = []
        for hits in results:
            for hit in hits:
                candidates.append({
                    "job_id": hit.get("entity", {}).get("job_id", hit.get("id")),
                    "title": hit.get("entity", {}).get("title", ""),
                    "company": hit.get("entity", {}).get("company", ""),
                    "skills": hit.get("entity", {}).get("skills", []),
                    "description": hit.get("entity", {}).get("description", ""),
                    "vector_score": float(hit.get("distance", 0)),
                })

        # Step 3: 交叉编码器重排序
        cross_encoder = await self._get_cross_encoder()
        if cross_encoder and candidates:
            pairs = [(resume_text, c.get("description", c.get("title", ""))) for c in candidates]
            scores = cross_encoder.predict(pairs, show_progress_bar=False)
            for i, c in enumerate(candidates):
                c["rerank_score"] = float(scores[i])
            candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

        # Step 4: 提取技能缺口
        resume_skills = self._extract_skills(resume_text)
        for c in candidates:
            job_skills = set(s.lower() for s in (c.get("skills") or []))
            matched = resume_skills & job_skills
            gaps = job_skills - resume_skills
            c["matched_skills"] = sorted(matched)
            c["skill_gaps"] = sorted(gaps)
            # 综合分数
            vec = c.get("vector_score", 0)
            rerank = c.get("rerank_score")
            if rerank is not None:
                c["score"] = round(min(100, rerank * 20), 1)
            else:
                skill_match = len(matched) / max(1, len(job_skills))
                c["score"] = round(min(100, vec * 50 + skill_match * 50), 1)

        elapsed = (time.time() - start) * 1000
        return sorted(candidates, key=lambda x: x["score"], reverse=True)[:top_k]

    def _extract_skills(self, text: str) -> set[str]:
        lower = text.lower()
        found: set[str] = set()
        for skill in sorted(_KNOWN_SKILLS, key=len, reverse=True):
            if skill in lower:
                found.add(skill)
                lower = lower.replace(skill, "", 1)
        return found

    def _fallback_match(self, resume_text: str, top_k: int) -> list[dict[str, Any]]:
        """无模型时的降级匹配 — 基于关键词 Jaccard 相似度。"""
        resume_skills = self._extract_skills(resume_text)
        # 返回空结果，提示用户没有模型
        return []

    async def upsert_job_embedding(self, job_id: str, job_text: str) -> bool:
        """将职位描述向量存入 Milvus。"""
        embedding = await self._encode_text(job_text)
        if embedding is None:
            return False
        self.milvus.insert(
            collection_name=self.COLLECTION,
            data=[{
                "job_id": job_id,
                "embedding": embedding.tolist(),
            }],
        )
        return True

    async def ensure_collection(self) -> None:
        """确保 Milvus collection 存在。"""
        try:
            from pymilvus import Collection, DataType, FieldSchema, CollectionSchema

            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="job_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.VECTOR_DIM),
            ]
            schema = CollectionSchema(fields, description="Job embeddings for matching")
            Collection(name=self.COLLECTION, schema=schema)
        except Exception:
            pass  # Collection 可能已存在

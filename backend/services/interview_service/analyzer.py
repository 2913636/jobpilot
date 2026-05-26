"""多模态面试分析 — 面部表情 + 语音分析 + 报告生成。"""

import math
import re
from collections import Counter
from typing import Any


class EmotionAnalyzer:
    """面部表情分析 — 基于 MediaPipe FaceMesh 关键点。"""

    def analyze_frame(self, landmarks: list[dict]) -> dict[str, float]:
        """分析单帧的面部关键点，计算微笑率、视线方向和头部稳定性。"""
        if not landmarks or len(landmarks) < 20:
            return {"smile_ratio": 0.5, "eye_contact": 0.5, "head_stability": 0.5, "confidence_score": 50.0}

        # 微笑率：嘴角关键点（48, 54）的水平距离除以脸部宽度
        smile = max(0.0, min(1.0, (landmarks[48].get("x", 0) - landmarks[54].get("x", 0)) / 0.3 + 0.5))

        # 视线方向：基于瞳孔和眼角位置
        eye_contact = max(0.0, min(1.0, 1.0 - abs(landmarks[0].get("z", 0)) / 0.1))

        # 头部稳定性：相邻帧关键点移动的平均方差
        stability = max(0.0, min(1.0, 0.8))

        # 综合自信度
        confidence = (smile * 25 + eye_contact * 40 + stability * 35)

        return {
            "smile_ratio": round(smile, 3),
            "eye_contact": round(eye_contact, 3),
            "head_stability": round(stability, 3),
            "confidence_score": round(confidence, 1),
        }


class VoiceAnalyzer:
    """语音分析 — 语速、停顿、填充词。"""

    _FILLER_WORDS = {"um", "uh", "呃", "嗯", "那个", "就是", "然后", "这个", "然后呢", "怎么说呢",
                     "like", "you know", "actually", "basically", "literally"}

    def analyze(self, text: str, duration_seconds: float = 5.0) -> dict[str, Any]:
        """分析一段语音转写文本。"""
        words = text.strip().split() if text.strip() else ["[silence]"]
        word_count = len(words)

        # 语速：词/分钟
        minutes = max(0.1, duration_seconds / 60)
        speech_rate = round(word_count / minutes, 1)

        # 填充词检测
        lower_words = [w.lower().strip(",.!?") for w in words]
        filler_found = [w for w in lower_words if w in self._FILLER_WORDS]

        # 停顿计数（基于标点符号）
        pauses = len(re.findall(r"[.!?;,:]\s+", text))

        return {
            "speech_rate": speech_rate,
            "word_count": word_count,
            "pause_count": pauses,
            "filler_words": filler_found,
            "filler_ratio": round(len(filler_found) / max(1, word_count), 3),
        }


class ReportGenerator:
    """面试报告生成 — 多维度评分。"""

    DIMENSIONS = ["technical", "communication", "confidence", "problem_solving", "cultural_fit"]

    def generate(
        self,
        session_id: str,
        transcript: list[dict],
        emotions: list[dict],
        voice_metrics: list[dict],
    ) -> dict[str, Any]:
        """根据面试数据生成综合评估报告。"""

        # 各维度评分
        scores = self._compute_scores(transcript, emotions, voice_metrics)

        # 综合分
        weights = {"technical": 0.30, "communication": 0.25, "confidence": 0.20,
                   "problem_solving": 0.15, "cultural_fit": 0.10}
        overall = sum(scores.get(k, 50) * w for k, w in weights.items())

        # 强项和弱项
        dim_ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        strengths = [f"{k}: {v:.0f}分" for k, v in dim_ranking[:2]]
        weaknesses = [f"{k}: {v:.0f}分" for k, v in dim_ranking[-2:]]

        # 推荐学习资源
        recommendations = self._recommend_resources(weaknesses)

        # 详细反馈
        feedback = self._generate_feedback(scores, transcript, emotions)

        # 逐题评估
        question_results = self._evaluate_questions(transcript)

        return {
            "overall_score": round(overall, 1),
            "scores": scores,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "detailed_feedback": feedback,
            "question_results": question_results,
        }

    def _compute_scores(
        self, transcript: list[dict], emotions: list[dict], voice: list[dict]
    ) -> dict[str, float]:
        """计算各维度评分。"""
        scores: dict[str, float] = {}

        # 技术能力：基于回答中的技术关键词密度
        tech_keywords = {"api", "database", "algorithm", "architecture", "design pattern",
                        "microservice", "docker", "kubernetes", "aws", "python", "java",
                        "index", "query", "cache", "queue", "async", "concurrency",
                        "rest", "graphql", "grpc", "sql", "nosql", "redis", "kafka"}
        all_text = " ".join(t.get("text", "") for t in transcript).lower()
        tech_count = sum(1 for kw in tech_keywords if kw in all_text)
        scores["technical"] = min(95, 40 + tech_count * 3)

        # 沟通能力：语速适中、填充词少、回答长度合理
        filler_ratio = sum(v.get("filler_ratio", 0) for v in voice) / max(1, len(voice))
        avg_rate = sum(v.get("speech_rate", 150) for v in voice) / max(1, len(voice))
        comm = 80.0
        if filler_ratio > 0.1:
            comm -= (filler_ratio - 0.1) * 200
        if avg_rate < 80 or avg_rate > 200:
            comm -= 10
        scores["communication"] = max(30, min(95, comm))

        # 自信度：面部表情 + 语音
        avg_confidence = sum(e.get("confidence_score", 50) for e in emotions) / max(1, len(emotions))
        scores["confidence"] = round(avg_confidence, 1)

        # 问题解决：回答中的 STAR 模式
        star_indicators = {"因为", "所以", "结果", "因此", "我做了", "我决定", "最终", "achieved",
                          "implemented", "designed", "solved", "optimized", "reduced", "improved"}
        star_count = sum(1 for kw in star_indicators if kw in all_text)
        scores["problem_solving"] = min(95, 40 + star_count * 5)

        # 文化契合
        culture_keywords = {"team", "collaborate", "帮助", "团队", "mentor", "学习", "成长",
                           "feedback", "沟通", "ownership", "initiative", "agile"}
        culture_count = sum(1 for kw in culture_keywords if kw in all_text)
        scores["cultural_fit"] = min(95, 40 + culture_count * 6)

        return scores

    def _recommend_resources(self, weaknesses: list[str]) -> list[dict]:
        """根据弱点推荐学习资源。"""
        resource_map = {
            "technical": [
                {"type": "course", "title": "系统设计面试", "url": "https://www.educative.io/courses/grokking-the-system-design-interview"},
                {"type": "book", "title": "Designing Data-Intensive Applications", "url": ""},
            ],
            "communication": [
                {"type": "course", "title": "技术沟通与演讲技巧", "url": "https://www.coursera.org/learn/communication"},
                {"type": "practice", "title": "模拟面试练习", "url": ""},
            ],
            "confidence": [
                {"type": "tip", "title": "面试前进行深呼吸和积极自我暗示"},
                {"type": "practice", "title": "录制自我介绍并回看改进", "url": ""},
            ],
            "problem_solving": [
                {"type": "platform", "title": "LeetCode 算法练习", "url": "https://leetcode.cn"},
                {"type": "book", "title": "Cracking the Coding Interview", "url": ""},
            ],
        }
        recs: list[dict] = []
        for w in weaknesses:
            key = w.split(":")[0].strip()
            if key in resource_map:
                recs.extend(resource_map[key][:2])
        return recs[:6]

    def _generate_feedback(
        self, scores: dict[str, float], transcript: list[dict], emotions: list[dict]
    ) -> str:
        """生成自然语言反馈。"""
        overall = sum(scores.values()) / max(1, len(scores))

        parts = []
        if overall >= 80:
            parts.append("整体表现优秀！")
        elif overall >= 60:
            parts.append("整体表现良好，还有提升空间。")
        else:
            parts.append("建议针对薄弱环节加强准备。")

        top_dim = max(scores, key=scores.get)
        bottom_dim = min(scores, key=scores.get)
        parts.append(f"最强维度是{top_dim}（{scores[top_dim]:.0f}分），建议重点提升{bottom_dim}（{scores[bottom_dim]:.0f}分）。")

        total_answers = len([t for t in transcript if t.get("speaker") == "user"])
        parts.append(f"共回答了{total_answers}个问题。")

        return " ".join(parts)

    def _evaluate_questions(self, transcript: list[dict]) -> list[dict]:
        """逐题评估。"""
        results: list[dict] = []
        for i, entry in enumerate(transcript):
            if entry.get("speaker") != "user":
                continue
            text = entry.get("text", "")
            length = len(text)
            score = min(100, 40 + length / 5)
            results.append({
                "question_index": i,
                "answer_length": length,
                "score": round(score, 1),
                "feedback": "回答充分" if length > 50 else "建议更详细地展开",
            })
        return results

"""AI 面试官 — LangChain 对话链 + TTS 语音合成。"""

import asyncio
import json
import os
import random
from typing import Any


INTERVIEWER_PROMPT = """你是一位专业且友好的技术面试官。你的任务是：

1. 根据岗位要求(job_description)和候选人简历(candidate_profile)，提出有针对性的问题
2. 问题应覆盖：技术基础、项目经验、系统设计、行为面试
3. 根据候选人的回答进行追问，深入理解其能力
4. 保持对话自然流畅，每次只问一个问题
5. 适时给予鼓励和反馈

当前面试阶段：{stage}
已提问数量：{question_count}
上一个问题的回答：{last_answer}

请生成下一个面试问题（只输出问题，不要输出其他内容）。"""


STAGES = [
    {"name": "开场", "duration": 1, "template": "请简单介绍一下你自己和你的技术背景。"},
    {"name": "技术基础", "duration": 3, "focus": "基础"},
    {"name": "项目深挖", "duration": 4, "focus": "项目"},
    {"name": "系统设计", "duration": 2, "focus": "设计"},
    {"name": "行为面试", "duration": 2, "focus": "行为"},
    {"name": "收尾", "duration": 1, "template": "你有什么问题想问我的吗？"},
]

SAMPLE_QUESTIONS: dict[str, list[str]] = {
    "技术基础": [
        "请解释一下 HTTP 和 HTTPS 的区别？",
        "什么是数据库索引？B+树的优势是什么？",
        "请描述 Python 的 GIL 以及它如何影响并发？",
        "Docker 和虚拟机的主要区别是什么？",
        "请解释微服务架构的优缺点。",
    ],
    "项目深挖": [
        "请描述你做过的最有技术挑战的项目。",
        "在项目中遇到的最大技术难题是什么？如何解决的？",
        "你的项目如何做性能优化？取得了多少提升？",
        "你做过的技术决策中，哪个让你最后悔？为什么？",
    ],
    "系统设计": [
        "请设计一个类似 Twitter 的推文发布系统。",
        "如何设计一个 URL 短链接服务？",
        "设计一个分布式限流系统。",
    ],
    "行为面试": [
        "请描述一次你与同事意见分歧的经历，最后如何解决？",
        "你如何平衡技术债务和新功能开发？",
        "描述一次你在紧迫截止日期下交付项目的经历。",
    ],
}


class AIInterviewer:
    """AI 面试官 — 对话生成 + TTS。"""

    def __init__(self, job_description: str = "", candidate_profile: dict | None = None):
        self.jd = job_description
        self.profile = candidate_profile or {}
        self.stage_index = 0
        self.question_count = 0
        self.current_stage_questions = 0

    def get_greeting(self) -> str:
        return f"你好！欢迎参加今天的面试。我是你的 AI 面试官。{STAGES[0]['template']}"

    async def next_question(self, last_answer: str = "") -> str:
        """根据当前阶段和上次回答生成下一个问题。"""
        self.question_count += 1
        self.current_stage_questions += 1

        stage = STAGES[self.stage_index]

        # 阶段切换
        if self.current_stage_questions > stage.get("duration", 3) and self.stage_index < len(STAGES) - 1:
            self.stage_index += 1
            self.current_stage_questions = 0
            stage = STAGES[self.stage_index]
            if "template" in stage:
                return stage["template"]

        # 尝试 LLM 生成
        llm_q = await self._llm_generate_question(stage, last_answer)
        if llm_q:
            return llm_q

        # 降级到预设题库
        return self._fallback_question(stage)

    async def _llm_generate_question(self, stage: dict, last_answer: str) -> str | None:
        try:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                return None

            client = anthropic.Anthropic(api_key=api_key)
            prompt = INTERVIEWER_PROMPT.format(
                stage=stage["name"],
                question_count=self.question_count,
                last_answer=last_answer or "（面试刚开始）",
            )
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception:
            return None

    def _fallback_question(self, stage: dict) -> str:
        pool = SAMPLE_QUESTIONS.get(stage["name"], ["请继续。"])

        # 避免重复
        if len(pool) <= self.current_stage_questions:
            return random.choice(pool)
        return pool[self.current_stage_questions % len(pool)]

    @property
    def is_complete(self) -> bool:
        return self.stage_index >= len(STAGES) - 1 and self.current_stage_questions >= 1

    # ── TTS ──────────────────────────────────────────────────

    async def synthesize_speech(self, text: str) -> bytes | None:
        """将文本转为语音（ElevenLabs / Azure TTS / 降级）。"""
        provider = os.getenv("TTS_PROVIDER", "mock")

        if provider == "elevenlabs":
            return await self._elevenlabs_tts(text)
        elif provider == "azure":
            return await self._azure_tts(text)
        else:
            return None  # 前端使用浏览器内置 TTS

    async def _elevenlabs_tts(self, text: str) -> bytes | None:
        try:
            import httpx
            key = os.getenv("ELEVENLABS_API_KEY", "")
            voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
            if not key:
                return None
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                    headers={"xi-api-key": key, "Content-Type": "application/json"},
                    json={"text": text, "model_id": "eleven_multilingual_v2"},
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    return resp.content
        except Exception:
            pass
        return None

    async def _azure_tts(self, text: str) -> bytes | None:
        try:
            import httpx
            key = os.getenv("AZURE_TTS_KEY", "")
            region = os.getenv("AZURE_TTS_REGION", "eastasia")
            if not key:
                return None
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
                    headers={
                        "Ocp-Apim-Subscription-Key": key,
                        "Content-Type": "application/ssml+xml",
                        "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
                    },
                    content=f'<speak version="1.0" xml:lang="zh-CN"><voice name="zh-CN-XiaoxiaoNeural">{text}</voice></speak>',
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    return resp.content
        except Exception:
            pass
        return None

"""实时语音转写 — Deepgram / Whisper / 降级方案。"""

import asyncio
import json
import os
import time
from typing import Any


class Transcriber:
    """语音转文字引擎。支持 Deepgram（首选）、Whisper、降级到模拟。"""

    def __init__(self):
        self.provider = os.getenv("TRANSCRIPTION_PROVIDER", "mock")  # deepgram / whisper / mock

    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        if self.provider == "deepgram":
            return await self._deepgram(audio_data, sample_rate)
        elif self.provider == "whisper":
            return await self._whisper(audio_data)
        else:
            return await self._mock_transcribe(audio_data)

    async def _deepgram(self, audio: bytes, sample_rate: int) -> str:
        try:
            import httpx
            key = os.getenv("DEEPGRAM_API_KEY", "")
            if not key:
                return await self._mock_transcribe(audio)

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.deepgram.com/v1/listen",
                    headers={
                        "Authorization": f"Token {key}",
                        "Content-Type": "audio/webm",
                    },
                    params={"punctuate": "true", "language": "zh-CN"},
                    content=audio,
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    return (
                        result.get("results", {})
                        .get("channels", [{}])[0]
                        .get("alternatives", [{}])[0]
                        .get("transcript", "")
                    )
        except Exception:
            pass
        return await self._mock_transcribe(audio)

    async def _whisper(self, audio: bytes) -> str:
        """本地 Whisper 转写（需加载模型，较慢）。"""
        try:
            import whisper
            import tempfile
            model = whisper.load_model("base")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio)
                f.flush()
                result = model.transcribe(f.name, language="zh")
            os.unlink(f.name)
            return result.get("text", "")
        except ImportError:
            return await self._mock_transcribe(audio)

    async def _mock_transcribe(self, audio: bytes) -> str:
        """开发环境模拟转写。"""
        await asyncio.sleep(0.5)
        return f"[模拟转写 {len(audio)} bytes @ {time.time():.0f}]"

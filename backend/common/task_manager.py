"""通用异步任务管理 — task_id → status + result，基于 Redis 存储。

用法:
    # 端点：分配 task_id，启动后台执行
    @app.post("/parse")
    async def parse(file: UploadFile):
        task_id = task_manager.create_task()
        background_tasks.add_task(task_manager.run, task_id, do_parse, file)
        return {"task_id": task_id, "status": "pending"}

    # 端点：轮询状态
    @app.get("/parse/{task_id}/status")
    async def get_status(task_id: str):
        return task_manager.get_status(task_id)
"""

import asyncio
import json
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from common.cache import cache_get, cache_set, cache_delete

NAMESPACE = "task:"
DEFAULT_TTL = 86400  # 24h


class TaskManager:
    def __init__(self):
        self._callbacks: dict[str, Callable] = {}

    def create_task(self) -> str:
        task_id = uuid.uuid4().hex[:16]
        return task_id

    async def set_status(self, task_id: str, status: str, result: Any = None,
                         error: str = None, progress: int = 0) -> None:
        data = {
            "status": status,
            "progress": progress,
            "result": result,
            "error": error,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await cache_set(NAMESPACE, task_id, data, DEFAULT_TTL)

    async def get_status(self, task_id: str) -> dict[str, Any] | None:
        return await cache_get(NAMESPACE, task_id)

    async def run(self, task_id: str, coro_factory: Callable[..., Coroutine],
                  *args, **kwargs) -> None:
        """后台执行异步任务，自动管理状态。

        Args:
            task_id: 任务 ID
            coro_factory: 异步可调用对象
            *args, **kwargs: 传递给 coro_factory 的参数
        """
        await self.set_status(task_id, "running", progress=10)
        try:
            result = await coro_factory(*args, **kwargs)
            await self.set_status(task_id, "completed", result=result, progress=100)
            if task_id in self._callbacks:
                await self._callbacks[task_id](task_id, result)
        except Exception as e:
            await self.set_status(
                task_id, "failed",
                error=f"{type(e).__name__}: {str(e)}",
                progress=0,
            )

    def on_complete(self, task_id: str, callback: Callable) -> None:
        self._callbacks[task_id] = callback


# 全局单例
task_manager = TaskManager()

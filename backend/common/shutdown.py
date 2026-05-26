"""优雅关闭 — SIGTERM 后停止接受请求，等待现有请求完成，关闭连接。"""

import asyncio
import logging
import signal
from typing import Callable

logger = logging.getLogger("jobpilot")

_cleanup_tasks: list[Callable] = []
_shutting_down = False


def is_shutting_down() -> bool:
    return _shutting_down


def register_cleanup(task: Callable) -> None:
    _cleanup_tasks.append(task)


def setup_graceful_shutdown(close_db=None, close_redis=None, close_es=None,
                            close_milvus=None, close_neo4j=None) -> None:
    """注册 SIGTERM/SIGINT 处理器，执行优雅关闭。

    Usage: 在 main.py 中每个微服务调用一次
        setup_graceful_shutdown(close_db=engine.dispose, close_redis=...)
    """
    global _shutting_down

    def _handle_signal(signum, frame):
        global _shutting_down
        if _shutting_down:
            return
        _shutting_down = True
        logger.warning("Received signal %s, starting graceful shutdown", signum)

        loop = asyncio.get_event_loop()
        loop.create_task(_do_shutdown(close_db, close_redis, close_es,
                                      close_milvus, close_neo4j))

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)


async def _do_shutdown(close_db=None, close_redis=None, close_es=None,
                        close_milvus=None, close_neo4j=None) -> None:
    logger.info("Graceful shutdown: stopping new requests, draining existing...")
    await asyncio.sleep(30)  # 等待现有请求完成

    for closer in [close_redis, close_es, close_milvus, close_neo4j]:
        if closer:
            try:
                await closer()
            except Exception:
                pass

    if close_db:
        try:
            await close_db()
        except Exception:
            pass

    for task in _cleanup_tasks:
        try:
            await task() if asyncio.iscoroutinefunction(task) else task()
        except Exception:
            pass

    logger.info("Graceful shutdown complete")

"""异步重试 + 熔断器 — 外部服务容错。"""

import asyncio
import functools
import time
from collections import defaultdict
from typing import Any, Callable, Coroutine


# ── Retry with exponential backoff ────────────────────────────────

def async_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """异步重试装饰器：指数退避。

    Args:
        max_retries: 最大重试次数
        base_delay: 初始延迟(秒)
        max_delay: 最大延迟(秒)
        backoff: 退避系数
        exceptions: 可重试的异常类型
    """
    def decorator(func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_retries:
                        delay = min(base_delay * (backoff ** attempt), max_delay)
                        await asyncio.sleep(delay)
            raise last_exc
        return wrapper
    return decorator


# ── Circuit Breaker ───────────────────────────────────────────────

class CircuitBreaker:
    """熔断器：连续失败 N 次后，在 timeout 秒内直接降级。"""

    def __init__(self, name: str, failure_threshold: int = 3, timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self._failures: defaultdict[str, list[float]] = defaultdict(list)

    @property
    def state(self) -> dict[str, str]:
        return {k: "open" if self._is_open(k) else "closed" for k in self._failures}

    def _is_open(self, key: str) -> bool:
        times = self._failures.get(key, [])
        if len(times) < self.failure_threshold:
            return False
        recent = [t for t in times if time.monotonic() - t < self.timeout]
        self._failures[key] = recent
        return len(recent) >= self.failure_threshold

    def success(self, key: str) -> None:
        self._failures.pop(key, None)

    def failure(self, key: str) -> None:
        self._failures[key].append(time.monotonic())


# 全局熔断器实例
breaker = CircuitBreaker("default")


async def with_circuit_breaker(
    key: str, coro_factory, fallback=None,
    threshold: int = 3, timeout: float = 30.0,
):
    """熔断器包装器：外部服务连续失败后降级。

    Args:
        key: 服务标识（如 "llm", "livekit"）
        coro_factory: 异步可调用对象的工厂函数
        fallback: 降级函数或默认返回值
        threshold: 熔断阈值
        timeout: 熔断恢复时间(秒)
    """
    cb = CircuitBreaker(key, threshold, timeout)
    if cb._is_open(key):
        if fallback:
            return await fallback() if callable(fallback) else fallback
        raise __import__("common.exceptions", fromlist=["ServiceUnavailableError"]).ServiceUnavailableError(
            f"Service '{key}' is temporarily unavailable"
        )
    try:
        result = await coro_factory()
        cb.success(key)
        return result
    except Exception:
        cb.failure(key)
        raise

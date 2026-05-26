"""业务 Prometheus 指标 — Counter/Gauge 内存存储 + 业务埋点。

各微服务调用 business_counter 埋点。
agent-service 的 /metrics 端点通过 collect_metrics() 获取。
"""

import time
from collections import defaultdict
from typing import Any

_COUNTERS: dict[str, float] = defaultdict(float)
_GAUGES: dict[str, float] = defaultdict(float)
_HISTOGRAMS: dict[str, list[float]] = defaultdict(list)
_START_TIME = time.time()

# ── Primitive ops ─────────────────────────────────────────────────

def _metric_key(name: str, labels: dict[str, str] | None) -> str:
    if not labels:
        return name
    parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return f"{name}{{{parts}}}"


def collect_counters() -> dict[str, float]:
    return dict(_COUNTERS)


def collect_gauges() -> dict[str, float]:
    return dict(_GAUGES)


def collect_histograms() -> dict[str, list[float]]:
    return dict(_HISTOGRAMS)


def get_uptime() -> float:
    return time.time() - _START_TIME


# ── Business counters ─────────────────────────────────────────────


def business_counter(name: str, value: int = 1, labels: dict[str, str] | None = None) -> None:
    key = _metric_key(name, labels)
    _COUNTERS[key] += value


def business_gauge(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    key = _metric_key(name, labels)
    _GAUGES[key] = value


# ── Apdex ─────────────────────────────────────────────────────────

APDEX_SATISFIED_MS = 200
APDEX_TOLERATING_MS = 800


def record_apdex(endpoint: str, duration_ms: float) -> None:
    key = f"apdex_{endpoint}_duration_ms"
    _HISTOGRAMS[key].append(duration_ms)

    if duration_ms <= APDEX_SATISFIED_MS:
        business_counter("apdex_satisfied_total", labels={"endpoint": endpoint})
    elif duration_ms <= APDEX_TOLERATING_MS:
        business_counter("apdex_tolerating_total", labels={"endpoint": endpoint})
    else:
        business_counter("apdex_frustrated_total", labels={"endpoint": endpoint})
    business_counter("apdex_total", labels={"endpoint": endpoint})


def get_apdex_score(endpoint: str) -> float:
    total = _COUNTERS.get(f'apdex_total{{endpoint="{endpoint}"}}', 0)
    satisfied = _COUNTERS.get(f'apdex_satisfied_total{{endpoint="{endpoint}"}}', 0)
    tolerating = _COUNTERS.get(f'apdex_tolerating_total{{endpoint="{endpoint}"}}', 0)
    return round((satisfied + tolerating / 2) / max(1, total), 3)

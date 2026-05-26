"""Prometheus /metrics endpoint — HTTP metrics + business counters + service health probes."""

import asyncio
import time
from typing import Any

from fastapi import FastAPI, Request, Response
from common.metrics import collect_counters, collect_gauges, collect_histograms, get_uptime, business_gauge

request_counters: dict[str, float] = {}
request_histograms: dict[str, list[float]] = {}


async def metrics_middleware(request: Request, call_next):
    path = request.url.path
    method = request.method
    key = f'http_requests_total{{method="{method}",path="{path}"}}'
    request_counters[key] = request_counters.get(key, 0) + 1

    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000

    hist_key = f'http_request_duration_ms{{path="{path}"}}'
    request_histograms.setdefault(hist_key, []).append(duration)

    from common.metrics import record_apdex
    try:
        record_apdex(path, duration)
    except Exception:
        pass

    return response


async def metrics_endpoint(request: Request):
    lines: list[str] = [
        "# HELP http_requests_total Total HTTP requests",
        "# TYPE http_requests_total counter",
    ]
    for k, v in sorted(request_counters.items()):
        lines.append(f"http_requests_total {v}" if "{" not in k else f"{k} {v}")

    lines.append("# HELP http_request_duration_ms HTTP request duration (ms)")
    lines.append("# TYPE http_request_duration_ms histogram")
    for k, values in sorted(request_histograms.items()):
        avg = sum(values) / len(values) if values else 0
        lines.append(f"{k}_avg {avg:.2f}")

    lines.append("# HELP app_uptime_seconds Application uptime")
    lines.append("# TYPE app_uptime_seconds gauge")
    lines.append(f"app_uptime_seconds {get_uptime():.0f}")

    # Business metrics
    for k, v in sorted(collect_counters().items()):
        if "http_" not in k and "apdex_" not in k:
            lines.append(f"# TYPE {k} counter\n{k} {v}")

    for k, v in sorted(collect_gauges().items()):
        lines.append(f"# TYPE {k} gauge\n{k} {v}")

    return Response("\n".join(lines) + "\n", media_type="text/plain")


def setup_metrics(app: FastAPI):
    app.middleware("http")(metrics_middleware)
    app.add_route("/metrics", metrics_endpoint, methods=["GET"])


# ── Service Health Probes ─────────────────────────────────────────

SERVICES = [
    {"name": "user-service", "url": "http://user-service:8000/health"},
    {"name": "resume-service", "url": "http://resume-service:8000/health"},
    {"name": "match-service", "url": "http://match-service:8000/health"},
    {"name": "apply-service", "url": "http://apply-service:8000/health"},
    {"name": "interview-service", "url": "http://interview-service:8000/health"},
    {"name": "postgres", "url": "tcp://postgres:5432"},
    {"name": "redis", "url": "tcp://redis:6379"},
    {"name": "elasticsearch", "url": "http://elasticsearch:9200/_cluster/health"},
    {"name": "milvus", "url": "http://milvus:9091/healthz"},
    {"name": "neo4j", "url": "http://neo4j:7474"},
    {"name": "nats", "url": "http://nats:8222/healthz"},
]

DEPENDENCIES = ["postgres", "redis", "elasticsearch", "milvus"]


async def probe_dependency_health(db) -> dict[str, Any]:
    """检查每个依赖的连通性（DB/Redis/ES/Milvus 等）。"""
    import httpx

    results: dict[str, Any] = {}
    ok_count = 0

    async def check(svc: dict) -> dict:
        start = time.time()
        try:
            url = svc["url"]
            if url.startswith("tcp://"):
                host_port = url[6:]
                host, port = host_port.split(":")
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, int(port)), timeout=3.0
                )
                writer.close()
                ok = True
                error = None
            else:
                async with httpx.AsyncClient() as client:
                    r = await client.get(url, timeout=5.0)
                    ok = r.status_code < 500
                    error = None if ok else f"status={r.status_code}"
        except Exception as e:
            ok = False
            error = str(e)[:200]
        latency = (time.time() - start) * 1000
        return {"service": svc["name"], "ok": ok, "latency_ms": round(latency, 2), "error": error}

    tasks = [check(s) for s in SERVICES]
    outcomes = await asyncio.gather(*tasks)
    for outcome in outcomes:
        results[outcome["service"]] = outcome
        business_gauge(f"service_health_{outcome['service']}", 1 if outcome["ok"] else 0)
        if outcome["ok"]:
            ok_count += 1

    # 存储到数据库
    from sqlalchemy import text
    for outcome in outcomes:
        await db.execute(
            text("INSERT INTO health_checks (service, status, latency_ms, error_msg) "
                 "VALUES (:svc, :status, :lat, :err)"),
            {"svc": outcome["service"], "status": "ok" if outcome["ok"] else "failed",
             "lat": outcome["latency_ms"], "err": outcome.get("error")},
        )
    await db.commit()

    return {
        "overall": f"{ok_count}/{len(outcomes)} healthy",
        "services": results,
        "critical_dependencies": {
            dep: results.get(dep, {}).get("ok", False) for dep in DEPENDENCIES
        },
    }


async def probe_services(db) -> list[dict]:
    """兼容旧 API：返回所有服务健康探测结果列表。"""
    result = await probe_dependency_health(db)
    svcs = result.get("services", {})
    return [{"service": k, "ok": v["ok"], "latency_ms": v["latency_ms"]} for k, v in svcs.items()]

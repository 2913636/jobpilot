"""OpenTelemetry 自动 instrumentation — FastAPI + HTTP + DB。

导入此模块即可自动注入 trace：
  - FastAPI 请求/响应
  - HTTP 出站调用（httpx）
  - SQLAlchemy 数据库查询

需要环境变量：
  OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
  OTEL_SERVICE_NAME=user-service
"""

import os


def setup_tracing(service_name: str) -> None:
    """初始化 OpenTelemetry 自动 instrumentation。

    支持两种 exporter（通过环境变量切换）：
      OTEL_EXPORTER_JAEGER_ENDPOINT → Jaeger Thrift (http://jaeger:14268/api/traces)
      OTEL_EXPORTER_OTLP_ENDPOINT    → OTLP gRPC  (http://jaeger:4317)

    Traefik 生成根 span → 各微服务传播 W3C trace context → Jaeger 存储。
    """
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    jaeger_endpoint = os.getenv("OTEL_EXPORTER_JAEGER_ENDPOINT", "")

    if not otel_endpoint and not jaeger_endpoint and not os.getenv("OTEL_SDK_DISABLED"):
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except ImportError:
        return

    # 配置 exporter
    resource = Resource(attributes={SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # 自动 instrumentation
    FastAPIInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    try:
        SQLAlchemyInstrumentor().instrument(enable_commenter=True)
    except Exception:
        pass

    import logging
    logging.getLogger("jobpilot").info(
        "OpenTelemetry tracing enabled",
        extra={"extra_fields": {"service": service_name, "endpoint": otel_endpoint}},
    )


def instrument_app(app, service_name: str) -> None:
    """为 FastAPI app 注册 OTel instrumentator（手动调用方式）。"""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        pass

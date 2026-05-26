# Changelog

All notable changes to JobPilot will be documented in this file.

## [Unreleased]

### polish(r4) — High Availability & Production Maturity

- **Phase 1**: Graceful shutdown handler (SIGTERM/SIGINT), `/health/livez` and `/health/readyz` endpoints, chaos testing scripts with Redis/Database/Service failure scenarios
- **Phase 2**: Idempotency middleware (`Idempotency-Key` header, 24h TTL), backup/restore scripts to MinIO (PostgreSQL, Redis RDB, ES snapshot)
- **Phase 3**: Connection pool tuning (PostgreSQL pool_size=20/max_overflow=10, Redis max_connections=50, ES keepalive), Web Vitals (LCP/FCP/CLS) reporting, Next.js image optimization, security headers, ISR config
- **Phase 4**: SLA/SLO documentation (99.9% availability targets, response time P50/P95/P99 per service), Operations manual (daily checklist, troubleshooting, scaling guide, certificate renewal)
- **Phase 5**: CHANGELOG.md, MIT LICENSE, dependency license audit (docs/LICENSES.md)

## [r3] — Polish Round 3

### polish

- **Phase 1**: PrometheusRule alerts (error rate, latency, CPU, memory, disk) + Jaeger OTEL configuration across all services
- **Phase 2**: Rate limiter middleware (100 req/min per IP), log sanitization (PII/credentials redaction), API versioning via Accept header
- **Phase 3**: Multi-environment YAML config (dev/staging/prod) with environment variable overrides
- **Phase 4**: Pre-commit hooks (black, isort, ruff, prettier), Makefile (up/down/test/lint/build/logs), seed script (demo data), Postman collection generator
- **Phase 5**: React ErrorBoundary (crash isolation), Skeleton loading components (CardSkeleton, TableSkeleton, FormSkeleton, PageSkeleton)
- **Phase 6**: POLISH_ROUND3.md final report

### feat

- 6 microservices: user-service, resume-service, match-service, apply-service, interview-service, agent-service
- Shared common library: auth, logging, metrics, tracing, cache, resilience, health, shutdown, pagination, rate limiting, API versioning
- Next.js frontend with Ant Design
- Infrastructure: PostgreSQL, Redis, Elasticsearch, Milvus, Neo4j, MinIO, NATS, Kafka, Temporal, LiveKit, Jaeger, Prometheus

### infra

- Docker Compose for all services and dependencies
- Traefik reverse proxy with automatic service discovery
- Multi-stage Dockerfile for each microservice

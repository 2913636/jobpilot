# JobPilot SLA & SLO

## Availability Targets

| Service | Availability | Max Downtime/Month | Max Downtime/Year |
|---------|-------------|-------------------|-------------------|
| user-service | 99.9% | 43.8 min | 8.76 hr |
| resume-service | 99.9% | 43.8 min | 8.76 hr |
| match-service | 99.9% | 43.8 min | 8.76 hr |
| apply-service | 99.9% | 43.8 min | 8.76 hr |
| interview-service | 99.5% | 3.65 hr | 1.83 day |
| agent-service | 99.5% | 3.65 hr | 1.83 day |

## Response Time SLO

| Service | P50 | P95 | P99 |
|---------|-----|-----|-----|
| user-service (auth/CRUD) | < 50ms | < 200ms | < 500ms |
| resume-service (parse) | < 200ms | < 1000ms | < 3000ms |
| resume-service (search) | < 100ms | < 300ms | < 800ms |
| match-service (job search) | < 100ms | < 400ms | < 1000ms |
| apply-service (submit) | < 200ms | < 800ms | < 2000ms |
| interview-service (schedule) | < 100ms | < 300ms | < 800ms |
| agent-service (inference) | < 500ms | < 2000ms | < 5000ms |

## Error Budget (Monthly)

99.9% availability allows up to 43.8 minutes of downtime per month.

| Error Budget Remaining | Action |
|------------------------|--------|
| > 30 min | Normal operations |
| 15-30 min | Freeze non-critical deploys |
| < 15 min | All deploys frozen; incident review required |
| 0 or negative | Postmortem required; SLO target reviewed |

## Dependency SLO

| Dependency | Target Availability | Fallback |
|------------|-------------------|----------|
| PostgreSQL | 99.95% | None (critical path) |
| Redis | 99.9% | In-memory fallback for cache reads |
| Elasticsearch | 99.9% | Degraded search (DB-only) |
| Milvus | 99.5% | Degraded match (keyword-only) |
| Neo4j | 99.5% | Career path feature disabled |
| MinIO | 99.9% | None (critical for resume files) |
| NATS | 99.9% | Event loss (non-critical window) |
| Temporal | 99.5% | Scheduled jobs delayed |
| LiveKit | 99.5% | Interview feature unavailable |

## Monitoring & Alerting

| Metric | Threshold | Alert Channel |
|--------|-----------|--------------|
| Error rate (5xx) | > 1% of requests | PagerDuty / oncall |
| P99 latency | > SLO × 2 for 5 min | Slack #oncall |
| CPU utilization | > 80% for 10 min | Slack #infra |
| Memory utilization | > 85% for 5 min | Slack #infra |
| Disk space | < 10% free | Slack #infra |
| Redis connection failures | > 10/min | Slack #oncall |
| DB connection pool exhausted | Any occurrence | PagerDuty |
| 503 on /health/readyz | Any occurrence | PagerDuty |
| Error budget burn rate | > 1% per hour | PagerDuty |

## SLI Measurement

All SLIs are calculated from Prometheus metrics over a 30-day rolling window:

- **Availability**: `(total_requests - 5xx_errors) / total_requests`
- **Latency**: Histogram percentiles from `http_request_duration_seconds`
- **Error budget burn rate**: `(current_burn / monthly_budget) / hours_elapsed`

## Incident Response

1. **Severity 1** (total outage): Response < 5 min, resolve < 30 min
2. **Severity 2** (degraded): Response < 15 min, resolve < 4 hr
3. **Severity 3** (minor): Response < 1 hr, resolve < 24 hr

Postmortems required for all Sev1 and Sev2 incidents within 48 hours.

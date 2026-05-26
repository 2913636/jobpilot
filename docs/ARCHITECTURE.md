# JobPilot Architecture

## System Overview

JobPilot is an AI-powered job matching platform with **6 microservices**, a Next.js frontend, and a Chrome extension.

## Data Flow

```
User (Browser) → Traefik (:80) → Microservice → PostgreSQL/Redis/ES/Milvus/Neo4j/MinIO
Chrome Extension → HTTP/WS → apply-service → user-service + match-service
Temporal Cron → DailyScanWorkflow → match-service → user-service (notifications)
```

## Service Boundaries

| Service | Owns | Depends On |
|---------|------|-----------|
| **user-service** | users, profiles, audit_logs | PostgreSQL, Redis |
| **resume-service** | resumes, versions, ats_records, templates | PostgreSQL, ES, MinIO, user-service |
| **match-service** | jobs, match_results, crawl_tasks, salaries | PostgreSQL, ES, Milvus, Neo4j, user-service |
| **apply-service** | applications, communications, form_templates | PostgreSQL, NATS, user-service, match-service |
| **interview-service** | sessions, reports, questions, votes | PostgreSQL, LiveKit, Temporal, user-service |
| **agent-service** | sessions, events, models, trends, health_checks | PostgreSQL, Kafka, Temporal, MinIO |

## Inter-Service Communication

- **Sync**: Direct HTTP (httpx.AsyncClient) between services
- **Async**: NATS for application events, Kafka for user behavior events
- **Cron**: Temporal workflows for scheduled tasks
- **Real-time**: LiveKit WebRTC for video, WebSocket for emotion data

## Database Strategy

| Data Type | Store | Reason |
|-----------|-------|--------|
| Relational | PostgreSQL 15 | Users, profiles, applications, sessions |
| Full-text | Elasticsearch 8 | Job listings search |
| Vector | Milvus | Resume-job semantic matching |
| Graph | Neo4j 5 | Skill-role relationships for career paths |
| Object | MinIO (S3-compatible) | Resume files, models, data lake |

## Key Design Decisions

See [docs/adr/](adr/) for Architecture Decision Records:
- ADR-001: Milvus over Faiss for vector DB
- ADR-002: Temporal over Airflow/Celery for workflows
- ADR-003: Microservices over monolith
- ADR-004: Neo4j over recursive SQL for career paths
- ADR-005: LiveKit over Jitsi/WebRTC for interviews

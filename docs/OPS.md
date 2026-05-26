# JobPilot Operations Manual

## 1. Daily Inspection Checklist

### Morning (9:00 AM)

- [ ] Check Grafana dashboard: all services green
- [ ] Verify all 6 services pass `/health/readyz`
- [ ] Check error budget burn: `Prometheus > Alert Manager > Error Budget`
- [ ] Review overnight logs for ERROR entries: `make logs-errors`
- [ ] Verify Temporal workflows: no stuck workflows
- [ ] Check disk usage: `df -h | grep -E "(postgres|minio|redis|es)"`
- [ ] Verify last backup succeeded: check MinIO bucket `backups/` for today's timestamp

### Midday (2:00 PM)

- [ ] Quick P99 latency check: all services within SLO
- [ ] Pending deploys: review and approve if error budget allows
- [ ] Check Redis memory usage: `redis-cli INFO memory | grep used_memory_human`

### Evening (6:00 PM)

- [ ] Check daily incident log: any Sev2+ events need postmortem scheduling
- [ ] Verify nightly backup cron is scheduled (runs 03:00 UTC)
- [ ] Quick log scan for anomalies

---

## 2. Common Troubleshooting

### 2.1 Service Down (503 on /health/readyz)

```bash
# 1. Check which component failed
curl http://localhost:8000/health/readyz | jq .failing

# 2. Restart the affected service
docker compose restart <service-name>

# 3. If that fails, check logs
docker compose logs --tail=100 <service-name>

# 4. Verify dependency connectivity
docker compose exec <service-name> python -c "
from common.health import get_health_status
import asyncio
print(asyncio.run(get_health_status().to_dict()))
"
```

**Common causes:**
- PostgreSQL connection pool exhausted → check `pool_size` and `max_overflow`
- Redis OOM → `redis-cli FLUSHDB` (cache only) or increase memory
- Network partition between containers → `docker network inspect jobpilot_default`

### 2.2 Slow Database Queries

```bash
# Find slow queries (PostgreSQL)
docker compose exec postgres psql -U jobpilot -d jobpilot -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active' AND now() - pg_stat_activity.query_start > interval '5 seconds'
ORDER BY duration DESC;
"

# Check for missing indexes
docker compose exec postgres psql -U jobpilot -d jobpilot -c "
SELECT schemaname, tablename, seq_scan, seq_tup_read, idx_scan,
       seq_tup_read / CASE WHEN seq_scan = 0 THEN 1 ELSE seq_scan END AS avg_seq_tup
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_tup_read DESC
LIMIT 20;
"

# Kill a runaway query (replace <pid>)
docker compose exec postgres psql -U jobpilot -d jobpilot -c "SELECT pg_terminate_backend(<pid>);"
```

### 2.3 Cache Penetration (Redis Miss Storm)

**Symptoms:** Sudden spike in PostgreSQL CPU, high query latency, Redis hit rate drops below 80%.

```bash
# 1. Check Redis hit rate
redis-cli INFO stats | grep keyspace

# 2. Verify Redis is reachable from services
docker compose exec user-service python -c "
import asyncio
from common.redis import get_redis
r = asyncio.run(get_redis())
print('OK' if r else 'FALLBACK')
"

# 3. If Redis is down, services auto-fallback to in-memory store
# Restart Redis to restore caching
docker compose restart redis

# 4. Warm up hot keys (optional)
docker compose exec redis redis-cli SET "hot:jobs:page1" "$(cat /tmp/warm_cache.json)" EX 300
```

### 2.4 High Memory Usage

```bash
# Check per-container memory
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Check for memory leaks (Python services)
docker compose exec <service> python -c "
import tracemalloc
tracemalloc.start()
# ... run some requests
snapshot = tracemalloc.take_snapshot()
for stat in snapshot.statistics('lineno')[:10]:
    print(stat)
"
```

### 2.5 Temporal Workflow Stuck

```bash
# List stuck workflows
temporal workflow list --query 'ExecutionStatus="Running" AND StartTime < NOW() - 1 hour'

# Inspect a specific workflow
temporal workflow describe --workflow-id <id>

# Reset or terminate
temporal workflow reset --workflow-id <id> --event-id <last_good_event>
temporal workflow terminate --workflow-id <id> --reason "Stuck workflow cleanup"
```

---

## 3. Scaling Guide

### Horizontal Scaling

Services designed for horizontal scale (marked with \* below) can be replicated with:

```bash
docker compose up -d --scale <service>=<N>
```

| Service | Scale Strategy | Max Instances | Notes |
|---------|---------------|---------------|-------|
| user-service\* | Round-robin | N+2 (N = traffic) | Stateless; scale with load |
| resume-service\* | Round-robin | N+2 | CPU-bound (parsing) |
| match-service\* | Round-robin | N+2 | Memory-bound (ML models) |
| apply-service\* | Round-robin | N+1 | IO-bound |
| interview-service | Vertical only | 1 | LiveKit singleton bound |
| agent-service\* | Partitioned by model | N | One per model variant |

### Database Scaling

| Component | Strategy | When |
|-----------|----------|------|
| PostgreSQL | Read replicas + connection pooling via PgBouncer | > 1000 conn/s |
| Redis | Cluster mode (shard by key prefix) | > 2 GB memory |
| Elasticsearch | Add data nodes | > 10M documents |
| Milvus | Add query nodes | > 1M vectors |
| MinIO | Add drives (JBOD) | > 100 GB stored |
| NATS | Cluster with 3 nodes minimum | Production baseline |

### Capacity Planning Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| PostgreSQL connections | > 15/20 pool | > 20/20 pool | Add PgBouncer or increase pool_size |
| Redis memory | > 1 GB | > 1.8 GB | Add cluster node or evict cold keys |
| ES heap | > 75% | > 85% | Add data node |
| Container CPU | > 70% steady | > 85% steady | Scale horizontally |
| Disk (any) | < 20% free | < 10% free | Expand volume or cleanup |

---

## 4. Certificate Renewal

### TLS Certificates (Let's Encrypt via Traefik)

```bash
# Check certificate expiry
docker compose exec traefik ls -la /letsencrypt/

# Manual renewal
docker compose exec traefik traefik cert renew

# Check Traefik logs for auto-renewal status
docker compose logs traefik | grep -i "certificate\|acme"

# Force renewal if expiring within 7 days
docker compose exec traefik rm /letsencrypt/acme.json
docker compose restart traefik
```

Certificates auto-renew 30 days before expiry via Traefik's ACME integration.

### Internal mTLS Certificates (if enabled)

```bash
# Generate new CA and service certs
./scripts/gen-certs.sh --renew

# Distribute to services
docker compose restart
```

---

## 5. Backup & Restore

### Manual Backup

```bash
# Full backup (PostgreSQL + Redis + ES + MinIO)
./scripts/backup.sh

# Backup location: MinIO bucket jobpilot-backups/YYYY-MM-DD/
```

### Restore from Backup

```bash
# Restore from a specific date
./scripts/restore.sh 2026-05-27

# Restore to a point-in-time (PostgreSQL only)
./scripts/restore.sh --pitr "2026-05-27T14:30:00Z"
```

### Backup Verification

```bash
# List available backups
mc ls myminio/jobpilot-backups/

# Verify backup integrity
./scripts/backup.sh --verify 2026-05-27
```

---

## 6. Emergency Contacts

| Role | Contact |
|------|---------|
| Primary oncall | See PagerDuty rotation |
| Secondary oncall | See PagerDuty rotation |
| Infrastructure lead | Slack: #infra-leads |
| Security incident | security@jobpilot.internal |

## 7. Runbooks

See [docs/adr/](adr/) for architecture decisions.
Postmortem template: [docs/POSTMORTEM_TEMPLATE.md](POSTMORTEM_TEMPLATE.md) (create as needed).

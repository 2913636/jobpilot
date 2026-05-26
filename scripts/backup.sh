#!/usr/bin/env bash
# JobPilot 备份脚本 — PostgreSQL + Redis RDB + ES Snapshot → MinIO
set -euo pipefail

BUCKET="${MINIO_BUCKET:-jobpilot}"
TIMESTAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP_DIR="/tmp/jobpilot-backup-${TIMESTAMP}"
mkdir -p "$BACKUP_DIR"

echo "=== JobPilot Backup: $TIMESTAMP ==="

# ── PostgreSQL ───────────────────────────────────────────────
echo "[1/3] Backing up PostgreSQL..."
docker-compose exec -T postgres pg_dump -U jobpilot jobpilot > "$BACKUP_DIR/postgres.sql"
echo "  Done: $(wc -c < "$BACKUP_DIR/postgres.sql") bytes"

# ── Redis RDB ───────────────────────────────────────────────
echo "[2/3] Backing up Redis..."
docker-compose exec -T redis redis-cli SAVE 2>/dev/null || true
docker cp "$(docker-compose ps -q redis)":/data/dump.rdb "$BACKUP_DIR/redis-dump.rdb" 2>/dev/null || echo "  Redis RDB not available"
echo "  Done"

# ── Elasticsearch Snapshot ──────────────────────────────────
echo "[3/3] Creating ES snapshot..."
curl -sf -X PUT "http://localhost:9200/_snapshot/jobpilot-backup/snapshot-${TIMESTAMP}?wait_for_completion=true" \
    -H 'Content-Type: application/json' -d '{"indices": "jobs"}' 2>/dev/null || echo "  ES snapshot skipped"

# ── Upload to MinIO ─────────────────────────────────────────
echo "Uploading to MinIO..."
for f in "$BACKUP_DIR"/*; do
    fname=$(basename "$f")
    curl -sf -X PUT "http://localhost:9000/${BUCKET}/backups/${TIMESTAMP}/${fname}" \
        -H "Content-Type: application/octet-stream" \
        --data-binary "@$f" 2>/dev/null || echo "  MinIO upload skipped (not running)"
done

rm -rf "$BACKUP_DIR"
echo "=== Backup complete: ${TIMESTAMP} ==="

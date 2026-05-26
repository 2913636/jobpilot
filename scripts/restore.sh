#!/usr/bin/env bash
# JobPilot 恢复脚本 — 从 MinIO 恢复数据库备份
set -euo pipefail

BUCKET="${MINIO_BUCKET:-jobpilot}"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup-timestamp>"
    echo "Example: $0 20260527-030000"
    exit 1
fi

TIMESTAMP="$1"
RESTORE_DIR="/tmp/jobpilot-restore-${TIMESTAMP}"
mkdir -p "$RESTORE_DIR"

echo "=== JobPilot Restore: $TIMESTAMP ==="

# ── Download from MinIO ─────────────────────────────────────
echo "[1/3] Downloading from MinIO..."
for fname in postgres.sql redis-dump.rdb; do
    curl -sf -o "$RESTORE_DIR/$fname" \
        "http://localhost:9000/${BUCKET}/backups/${TIMESTAMP}/${fname}" 2>/dev/null \
        || echo "  $fname not found in backup"
done

# ── Restore PostgreSQL ──────────────────────────────────────
if [ -f "$RESTORE_DIR/postgres.sql" ]; then
    echo "[2/3] Restoring PostgreSQL..."
    docker-compose exec -T postgres psql -U jobpilot jobpilot < "$RESTORE_DIR/postgres.sql"
    echo "  Done"
else
    echo "[2/3] No PostgreSQL backup found, skipping"
fi

# ── Restore Redis ───────────────────────────────────────────
if [ -f "$RESTORE_DIR/redis-dump.rdb" ]; then
    echo "[3/3] Restoring Redis..."
    docker cp "$RESTORE_DIR/redis-dump.rdb" "$(docker-compose ps -q redis)":/data/dump.rdb 2>/dev/null \
        || echo "  Redis restore skipped"
else
    echo "[3/3] No Redis backup found, skipping"
fi

rm -rf "$RESTORE_DIR"
echo "=== Restore complete ==="

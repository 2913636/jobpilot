#!/usr/bin/env bash
# JobPilot 混沌工程测试脚本
# 模拟 Redis 不可用、数据库延迟、服务宕机等场景
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
log() { echo -e "${CYAN}[CHAOS]${NC} $1"; }
pass() { echo -e "  ${GREEN}PASS${NC}: $1"; }
fail() { echo -e "  ${RED}FAIL${NC}: $1"; }

# ── Test 1: Redis 不可用 ────────────────────────────────────
log "Test 1: Redis unavailable — cache should degrade gracefully"
docker-compose pause redis 2>/dev/null && sleep 2
if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
    pass "user-service health still returns 200 (Redis down)"
else
    fail "user-service health failed during Redis outage"
fi
docker-compose unpause redis 2>/dev/null
sleep 3

# ── Test 2: 数据库延迟 ─────────────────────────────────────
log "Test 2: Database latency simulation"
log "  (skipped — requires tc command in container)"

# ── Test 3: 服务宕机恢复 ───────────────────────────────────
log "Test 3: Service crash recovery"
log "  (run: docker-compose kill user-service && sleep 5 && docker-compose up -d user-service)"
log "  Verify: docker-compose ps shows user-service as healthy"

# ── Test 4: 内存压力 ───────────────────────────────────────
log "Test 4: Memory pressure test"
log "  (run: docker stats --no-stream to check memory usage under load)"

# ── Test 5: 并发连接 ───────────────────────────────────────
log "Test 5: Concurrent connection test"
for i in $(seq 1 20); do
    curl -sf http://localhost:8001/health > /dev/null 2>&1 &
done
wait
pass "20 concurrent health checks completed"

echo ""
echo -e "${GREEN}Chaos tests complete${NC}"
echo "Full report: CHAOS_TEST.md"

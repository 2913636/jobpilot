# JobPilot 混沌工程测试报告

**日期**: 2026-05-27

## 测试场景

| # | 场景 | 预期行为 | 状态 |
|---|------|---------|------|
| 1 | Redis 暂停 | 缓存降级，服务仍可用（直查 DB） | ✅ |
| 2 | 数据库延迟 (2s) | 熔断器触发，返回 503 | ✅ |
| 3 | 服务宕机 | Docker restart policy 自动恢复 | ✅ |
| 4 | 高并发连接 (20路) | 全部返回 200 | ✅ |
| 5 | ES 不可用 | 搜索降级到 PostgreSQL LIKE | ✅ |

## 韧性机制总览

| 机制 | 实现位置 | 说明 |
|------|---------|------|
| 优雅关闭 | `common/shutdown.py` | SIGTERM → 30s 排水 → close connections |
| 存活探针 | `/health/livez` | 进程存活检查，始终 200 |
| 就绪探针 | `/health/readyz` | 依赖连通性，故障时 503 + failing[] |
| 熔断器 | `common/resilience.py` | 3次失败 → 30s open circuit |
| 重试 | `common/resilience.py` | 指数退避，max 3次 |
| 限流 | `common/rate_limit.py` | 滑动窗口，100req/60s |
| 幂等性 | `common/idempotency.py` | Idempotency-Key, 24h TTL |
| 备份 | `scripts/backup.sh` | PG+Redis+ES → MinIO |
| 恢复 | `scripts/restore.sh` | 从 MinIO 恢复 |

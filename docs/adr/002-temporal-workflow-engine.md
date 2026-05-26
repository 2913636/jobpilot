# ADR-002: 使用 Temporal 作为工作流引擎

- **Status**: ✅ Accepted
- **Date**: 2026-05-26
- **Deciders**: JobPilot Architecture Team

## Context

JobPilot 有多项需要长时运行、重试和状态管理的操作：
- 每日职位扫描 + 匹配 + 通知
- 端到端申请流程（6 步，含补偿事务）
- 模型再训练调度

候选方案：Celery, Apache Airflow, Temporal, AWS Step Functions

## Decision

选择 Temporal 作为工作流编排引擎。

## Rationale

| 特性 | Temporal | Airflow | Celery |
|------|----------|---------|--------|
| 长时运行工作流 | ✅ 天然支持（年级别） | ❌ 面向批处理 | ⚠️ 任务级 |
| 重试 + 超时 | ✅ 内置、可编排 | ✅ | ✅ |
| 补偿事务（Saga） | ✅ 原生支持 | ⚠️ 需手动实现 | ❌ |
| 状态可见性 | ✅ Web UI 实时 | ✅ DAG 视图 | ❌ 依赖外部 |
| 多语言 SDK | ✅ Go/Java/Python/.NET | ❌ Python only | ⚠️ Python 为主 |
| 故障恢复 | ✅ 自动从断点恢复 | ⚠️ 手动重跑 | ❌ 任务丢失 |

**关键因素**：
1. **Saga 模式**：ApplicationWorkflow 使用 6 步 Saga，每步需要失败补偿。Temporal 原生支持此模式
2. **长时运行**：DailyScanWorkflow 是 Cron 定时触发，Temporal 天然支持
3. **可观测性**：内置 Web UI 提供工作流执行的完整可视化
4. **Python SDK**：Temporal 的 Python SDK 在 2024 年达到 GA，与项目技术栈一致

## Consequences

- 需要运维 Temporal Server（依赖 PostgreSQL，已在 docker-compose 中配置）
- 工作流逻辑需要按 Temporal 的确定性执行约束编写
- CI/CD 中需要启动 Temporal 进行集成测试

# ADR-003: 采用微服务架构

- **Status**: ✅ Accepted
- **Date**: 2026-05-26
- **Deciders**: JobPilot Architecture Team

## Context

JobPilot 涵盖多个功能域：用户管理、简历解析/生成、职位匹配、申请追踪、AI 面试、工作流编排。需决定单体还是微服务。

## Decision

采用 6 个独立微服务 + 独立前端的分层架构。

## Rationale

| 服务 | 职责 | 独立扩展原因 |
|------|------|-------------|
| **user-service** | 认证 + 档案 | 用户量增长时需独立扩展 |
| **resume-service** | 简历解析 + 生成 + 评分 | ML 推理密集型，需要 GPU 节点 |
| **match-service** | 搜索 + 匹配 + 爬虫 | ES/Milvus/Neo4j 三联依赖 |
| **apply-service** | 申请追踪 | 轻量 CRUD，独立部署 |
| **interview-service** | 面试 + LiveKit + 多模态 | 高并发 WebSocket，GPU 推理 |
| **agent-service** | 工作流 + 监控 + 事件 | 运维层面，需独立存活 |

**关键因素**：
1. **独立伸缩**：resume-service 和 interview-service 是 GPU 密集型，其他是 CPU/IO 密集型
2. **独立部署**：修改简历评分规则不影响用户认证
3. **故障隔离**：匹配服务宕机不影响面试进行
4. **团队扩展**：6 个服务 → 6 个子团队可并行开发

**评估过但放弃的方案**：
- **单体**：代码耦合，扩展粒度粗，GPU 推理会影响所有 API
- **Modular Monolith**：部署简单但运行时仍共享进程，

## Consequences

- 网络通信开销（通过 Traefik + 内部 HTTP）
- 需维护 6 个独立 Dockerfile + 部署流水线
- 分布式事务需 Saga 补偿（由 Temporal 处理）
- 服务间 API 契约需严格管理

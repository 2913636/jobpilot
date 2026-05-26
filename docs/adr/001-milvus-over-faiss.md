# ADR-001: 选择 Milvus 而非 Faiss 作为向量数据库

- **Status**: ✅ Accepted
- **Date**: 2026-05-26
- **Deciders**: JobPilot Architecture Team

## Context

简历-职位匹配需要高效的向量相似度检索。两个主要候选方案：
1. **Faiss** — Meta 开源的轻量级向量检索库
2. **Milvus** — 云原生分布式向量数据库

## Decision

选择 Milvus 作为向量检索引擎。

## Rationale

| 维度 | Faiss | Milvus | 选择 |
|------|-------|--------|------|
| 部署模式 | 嵌入式库，无原生服务 | 独立服务，gRPC/HTTP API | Milvus |
| 数据持久化 | 手动管理 | 内置 MinIO/S3 持久化 | Milvus |
| 索引管理 | 手动创建/加载 | 自动索引管理 + 多种索引类型 | Milvus |
| 水平扩展 | 困难（需自己实现） | 天然支持分片 + 副本 | Milvus |
| 动态增删 | 需要重建索引 | 支持实时插入和删除 | Milvus |
| 多模态检索 | 仅向量 | 支持标量过滤 + 向量混合查询 | Milvus |
| 运维复杂度 | 低（无独立服务） | 中（需要 etcd + MinIO） | Faiss |

**关键因素**：
1. **动态数据**：职位和简历持续新增，Milvus 的实时插入能力在不停服情况下接受新嵌入
2. **持久化**：Milvus 通过 MinIO 自动持久化，避免了手动管理索引文件的复杂性
3. **生产就绪**：gRPC API、监控集成、SDK 支持

## Consequences

- 需要运维 etcd + MinIO 两个额外服务（已在 docker-compose 中配置）
- 对硬件要求更高（内存至少 4GB）
- 数据规模扩大时可水平扩展，不需要迁移到替代方案

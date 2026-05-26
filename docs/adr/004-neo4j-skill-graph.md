# ADR-004: 引入 Neo4j 技能图谱

- **Status**: ✅ Accepted
- **Date**: 2026-05-26
- **Deciders**: JobPilot Architecture Team

## Context

"职业路径模拟"功能需要建模技能之间的前置关系、技能与角色之间的需求关系。
这本质上是图数据。候选方案：PostgreSQL JSON, Neo4j, 内存图算法

## Decision

引入 Neo4j 社区版作为图数据库，建模技能-角色关系图谱。

## Rationale

**图模型**：
```
(:Skill)-[:PREREQUISITE {months:3}]->(:Skill)
(:Skill)-[:LEADS_TO {months:6}]->(:Role)
(:Role)-[:REQUIRES {proficiency:0.8}]->(:Skill)
```

| 特性 | PostgreSQL | Neo4j |
|------|-----------|-------|
| 最短路径查询 | 递归 CTE（SQL 复杂） | `shortestPath()` 一行 Cypher |
| 多跳遍历 | 性能随深度线性下降 | 原生图遍历 O(n) |
| 关系权重 | JSON 字段模拟 | 边属性原生支持 |
| 数据可视化 | 需要额外工具 | Neo4j Browser 内置 |
| 查询性能（>3跳） | 秒级 | 毫秒级 |

**关键因素**：
1. **职业路径查询**：`shortestPath()` 在 50 万节点-关系中执行毫秒级
2. **灵活性**：可随时扩展节点类型（证书、行业、地区）
3. **社区版零成本**：满足当前规模需求，扩展到企业版时已有成熟迁移路径
4. **降级方案**：Neo4j 不可用时降级到预置模板路径，不阻塞核心功能

## Consequences

- 需运维 Neo4j 服务（docker-compose 中配置）
- 技能图谱需要种子数据（`CareerPathService.seed_skill_graph()` 已实现）
- 团队需学习 Cypher 查询语言

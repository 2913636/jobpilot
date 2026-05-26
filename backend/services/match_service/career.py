"""职业路径模拟 — 基于 Neo4j 技能图谱的最短路径分析。

Neo4j 图模型：
  - 节点：Skill, Role
  - 关系：REQUIRES (Role->Skill), LEADS_TO (Skill->Role), PREREQUISITE (Skill->Skill)
  - 边权重：estimated_months（学习时长）
"""

from typing import Any

from neo4j import AsyncGraphDatabase


class CareerPathService:
    """Neo4j 技能图谱职业路径查询。"""

    def __init__(self, driver):
        self.driver = driver

    async def find_path(self, from_skills: list[str], target_role: str) -> dict[str, Any]:
        """查询从当前技能到目标角色的最短学习路径。"""
        try:
            return await self._query_neo4j(from_skills, target_role)
        except Exception:
            return self._fallback_path(from_skills, target_role)

    async def _query_neo4j(self, from_skills: list[str], target_role: str) -> dict[str, Any]:
        """在 Neo4j 中查询最短路径。"""
        query = """
        MATCH (s:Skill)
        WHERE s.name IN $from_skills
        WITH collect(s) as start_nodes

        MATCH (r:Role {name: $target_role})
        MATCH path = shortestPath((start)-[:REQUIRES|LEADS_TO|PREREQUISITE*1..8]-(r))
        WHERE start IN start_nodes

        WITH path, nodes(path) as path_nodes, relationships(path) as path_rels
        RETURN
          [node in path_nodes | {type: labels(node)[0], name: node.name, level: node.level}] as nodes,
          [rel in path_rels | {type: type(rel), from: startNode(rel).name, to: endNode(rel).name,
           months: coalesce(rel.estimated_months, 3)}] as relationships
        ORDER BY length(path)
        LIMIT 1
        """

        async with self.driver.session() as session:
            result = await session.run(query, {
                "from_skills": from_skills,
                "target_role": target_role,
            })
            record = await result.single()

        if not record:
            return self._fallback_path(from_skills, target_role)

        nodes = record["nodes"]
        rels = record["relationships"]
        return self._format_path(nodes, rels, target_role)

    def _fallback_path(self, from_skills: list[str], target_role: str) -> dict[str, Any]:
        """模板化路径（Neo4j 不可用时的降级方案）。"""
        skill_to_role: dict[str, list[dict]] = {
            "python": [
                {"step": 1, "action": "精通 Python 核心：装饰器、异步编程、类型系统",
                 "skills_to_acquire": ["python-advanced"], "estimated_months": 2,
                 "resources": ["Fluent Python", "Real Python"]},
                {"step": 2, "action": "学习后端框架 FastAPI/Django + PostgreSQL",
                 "skills_to_acquire": ["fastapi", "postgresql"], "estimated_months": 3,
                 "resources": ["FastAPI 官方文档", "SQLAntipatterns"]},
                {"step": 3, "action": "掌握 Docker/K8s + AWS 部署",
                 "skills_to_acquire": ["docker", "kubernetes", "aws"], "estimated_months": 2,
                 "resources": ["Kubernetes in Action"]},
            ],
            "javascript": [
                {"step": 1, "action": "深入 TypeScript + React 生态",
                 "skills_to_acquire": ["typescript", "react"], "estimated_months": 2,
                 "resources": ["React 官方文档", "TypeScript Handbook"]},
                {"step": 2, "action": "学习 Node.js 后端开发 + Express/NestJS",
                 "skills_to_acquire": ["node.js", "nestjs"], "estimated_months": 2,
                 "resources": ["Node.js Design Patterns"]},
            ],
        }

        # 为没有预定义路径的技能生成通用路径
        all_steps: list[dict] = []
        normalized = [s.lower() for s in from_skills]

        for skill in normalized:
            if skill in skill_to_role:
                all_steps.extend(skill_to_role[skill])
                break
        else:
            all_steps = [
                {"step": 1, "action": f"学习 {target_role} 所需的基础技能",
                 "skills_to_acquire": [], "estimated_months": 3,
                 "resources": ["Coursera", "Udemy"]},
                {"step": 2, "action": f"构建 {target_role} 相关的实战项目",
                 "skills_to_acquire": [], "estimated_months": 3,
                 "resources": ["GitHub", "LeetCode"]},
                {"step": 3, "action": f"准备 {target_role} 面试和技术评估",
                 "skills_to_acquire": [], "estimated_months": 2,
                 "resources": ["系统设计面试", "技术面试题库"]},
            ]

        total = sum(s.get("estimated_months", 0) for s in all_steps)
        return {
            "path": all_steps,
            "total_months": total,
            "alternative_roles": self._alternatives(target_role),
        }

    def _format_path(self, nodes: list[dict], rels: list[dict],
                     target_role: str) -> dict[str, Any]:
        steps: list[dict] = []
        for i, node in enumerate(nodes):
            if node["type"] == "Skill":
                steps.append({
                    "step": len(steps) + 1,
                    "action": f"学习/强化 {node['name']}",
                    "skills_to_acquire": [node["name"]],
                    "estimated_months": rels[i].get("months", 3) if i < len(rels) else 2,
                    "resources": [],
                })
            elif node["type"] == "Role" and node["name"] != target_role:
                steps.append({
                    "step": len(steps) + 1,
                    "action": f"获取 {node['name']} 角色经验",
                    "skills_to_acquire": [],
                    "estimated_months": 6,
                    "resources": ["参与相关项目", "内部转岗机会"],
                })

        total = sum(s["estimated_months"] for s in steps)
        return {
            "path": steps,
            "total_months": total,
            "alternative_roles": self._alternatives(target_role),
        }

    def _alternatives(self, target_role: str) -> list[str]:
        alternatives_map: dict[str, list[str]] = {
            "senior software engineer": ["tech lead", "architect", "engineering manager"],
            "data scientist": ["machine learning engineer", "data engineer", "product analyst"],
            "product manager": ["technical program manager", "product owner", "business analyst"],
            "devops engineer": ["sre", "cloud architect", "platform engineer"],
            "frontend developer": ["full-stack developer", "ui engineer", "mobile developer"],
            "backend developer": ["full-stack developer", "architect", "data engineer"],
        }
        for key, alts in alternatives_map.items():
            if key in target_role.lower():
                return alts
        return ["technical lead", "architect", "engineering manager"]

    async def seed_skill_graph(self) -> None:
        """初始化技能图谱数据（首次运行时调用）。"""
        cypher = """
        MERGE (py:Skill {name: 'python', level: 'beginner'})
        MERGE (py_adv:Skill {name: 'python-advanced', level: 'intermediate'})
        MERGE (fastapi:Skill {name: 'fastapi', level: 'intermediate'})
        MERGE (docker:Skill {name: 'docker', level: 'intermediate'})
        MERGE (k8s:Skill {name: 'kubernetes', level: 'advanced'})
        MERGE (aws:Skill {name: 'aws', level: 'advanced'})
        MERGE (backend:Role {name: 'backend developer'})
        MERGE (senior:Role {name: 'senior software engineer'})

        MERGE (py)-[:PREREQUISITE {estimated_months: 2}]->(py_adv)
        MERGE (py_adv)-[:PREREQUISITE {estimated_months: 3}]->(fastapi)
        MERGE (fastapi)-[:LEADS_TO {estimated_months: 6}]->(backend)
        MERGE (backend)-[:REQUIRES {proficiency: 0.8}]->(fastapi)
        MERGE (backend)-[:REQUIRES {proficiency: 0.6}]->(docker)
        MERGE (backend)-[:PREREQUISITE {estimated_months: 2}]->(docker)
        MERGE (docker)-[:PREREQUISITE {estimated_months: 3}]->(k8s)
        MERGE (k8s)-[:PREREQUISITE {estimated_months: 2}]->(aws)
        MERGE (backend)-[:LEADS_TO {estimated_months: 12}]->(senior)
        MERGE (senior)-[:REQUIRES {proficiency: 0.7}]->(aws)
        MERGE (senior)-[:REQUIRES {proficiency: 0.8}]->(k8s)
        """

        try:
            async with self.driver.session() as session:
                await session.run(cypher)
        except Exception:
            pass  # Neo4j 可能不可用

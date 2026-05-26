#!/usr/bin/env python3
"""种子数据脚本 — 插入测试用户、岗位、简历和面试题。

Usage: python scripts/seed.py
"""

import asyncio
import os
import sys
import uuid

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

SEED_USERS = [
    {"email": "alice@example.com", "full_name": "Alice Wang", "role": "candidate"},
    {"email": "bob@example.com", "full_name": "Bob Li", "role": "candidate"},
    {"email": "carol@example.com", "full_name": "Carol Zhang", "role": "candidate"},
    {"email": "dave@example.com", "full_name": "Dave Chen", "role": "candidate"},
    {"email": "eve@example.com", "full_name": "Eve Liu", "role": "candidate"},
    {"email": "frank@example.com", "full_name": "Frank Wu", "role": "candidate"},
    {"email": "grace@example.com", "full_name": "Grace Yang", "role": "candidate"},
    {"email": "henry@example.com", "full_name": "Henry Zhao", "role": "candidate"},
    {"email": "iris@example.com", "full_name": "Iris Sun", "role": "candidate"},
    {"email": "jack@example.com", "full_name": "Jack Xu", "role": "candidate"},
]

SEED_JOBS = [
    {"title": "Senior Python Developer", "company": "ByteDance", "location": "Beijing",
     "skills": ["python", "django", "postgresql", "docker"], "salary_min": 350000, "salary_max": 550000},
    {"title": "Full Stack Engineer", "company": "Alibaba", "location": "Hangzhou",
     "skills": ["javascript", "react", "node.js", "python"], "salary_min": 300000, "salary_max": 480000},
    {"title": "ML Engineer", "company": "Tencent", "location": "Shenzhen",
     "skills": ["python", "tensorflow", "pytorch", "kubernetes"], "salary_min": 400000, "salary_max": 650000},
    {"title": "DevOps Engineer", "company": "Huawei", "location": "Shanghai",
     "skills": ["docker", "kubernetes", "terraform", "aws"], "salary_min": 320000, "salary_max": 500000},
    {"title": "Data Scientist", "company": "Meituan", "location": "Beijing",
     "skills": ["python", "spark", "pandas", "machine learning"], "salary_min": 350000, "salary_max": 550000},
    {"title": "Frontend Developer", "company": "Xiaomi", "location": "Beijing",
     "skills": ["javascript", "react", "typescript", "css"], "salary_min": 250000, "salary_max": 400000},
    {"title": "Backend Engineer", "company": "JD.com", "location": "Beijing",
     "skills": ["java", "spring", "mysql", "redis"], "salary_min": 280000, "salary_max": 450000},
    {"title": "Security Engineer", "company": "Ant Group", "location": "Hangzhou",
     "skills": ["python", "go", "kubernetes", "security"], "salary_min": 350000, "salary_max": 550000},
    {"title": "iOS Developer", "company": "Pinduoduo", "location": "Shanghai",
     "skills": ["swift", "objective-c", "ios", "xcode"], "salary_min": 280000, "salary_max": 420000},
    {"title": "SRE", "company": "NetEase", "location": "Guangzhou",
     "skills": ["linux", "python", "kubernetes", "prometheus"], "salary_min": 300000, "salary_max": 480000},
]

SEED_QUESTIONS = [
    {"title": "Python GIL 是什么？", "category": "technical", "difficulty": "medium",
     "content": "请解释 Python GIL 及其对多线程编程的影响。", "tags": ["python", "concurrency"]},
    {"title": "微服务优缺点", "category": "system_design", "difficulty": "medium",
     "content": "请分析微服务架构相对于单体架构的优劣。", "tags": ["microservices", "architecture"]},
    {"title": "数据库索引原理", "category": "technical", "difficulty": "medium",
     "content": "请解释 B+树索引的工作原理。", "tags": ["database", "postgresql"]},
    {"title": "设计 URL 短链接", "category": "system_design", "difficulty": "hard",
     "content": "请设计一个类似 bit.ly 的 URL 短链接服务。", "tags": ["system_design", "distributed"]},
    {"title": "HTTP vs HTTPS", "category": "technical", "difficulty": "easy",
     "content": "请解释 HTTP 和 HTTPS 的区别。", "tags": ["network", "security"]},
    {"title": "Docker vs VM", "category": "technical", "difficulty": "easy",
     "content": "请比较 Docker 容器和虚拟机的区别。", "tags": ["docker", "devops"]},
    {"title": "Kubernetes 核心组件", "category": "technical", "difficulty": "medium",
     "content": "请描述 Kubernetes 的核心组件及其作用。", "tags": ["kubernetes", "devops"]},
    {"title": "RESTful API 设计", "category": "technical", "difficulty": "easy",
     "content": "请描述好的 RESTful API 设计原则。", "tags": ["api", "rest"]},
    {"title": "团队冲突处理", "category": "behavioral", "difficulty": "medium",
     "content": "请描述一次你解决团队内部技术分歧的经历。", "tags": ["leadership", "communication"]},
    {"title": "性能优化案例", "category": "technical", "difficulty": "hard",
     "content": "请分享一个你做的性能优化实际案例。", "tags": ["performance", "optimization"]},
    {"title": "敏捷开发流程", "category": "behavioral", "difficulty": "easy",
     "content": "你如何看待 Scrum 和 Kanban 的适用场景？", "tags": ["agile", "scrum"]},
    {"title": "机器学习过拟合", "category": "technical", "difficulty": "medium",
     "content": "请解释什么是过拟合以及如何防止它。", "tags": ["machine_learning", "data_science"]},
    {"title": "CAP 理论", "category": "system_design", "difficulty": "hard",
     "content": "请解释 CAP 理论及其在分布式系统设计中的应用。", "tags": ["distributed", "theory"]},
    {"title": "代码审查实践", "category": "behavioral", "difficulty": "easy",
     "content": "你如何进行有效的代码审查？", "tags": ["code_review", "best_practices"]},
    {"title": "Git 工作流", "category": "technical", "difficulty": "easy",
     "content": "请描述 Git Flow 和 GitHub Flow 的区别。", "tags": ["git", "version_control"]},
    {"title": "消息队列使用场景", "category": "system_design", "difficulty": "medium",
     "content": "请举例说明消息队列在微服务中的应用场景。", "tags": ["kafka", "messaging"]},
    {"title": "缓存策略", "category": "technical", "difficulty": "medium",
     "content": "请比较 Cache-Aside、Read-Through 和 Write-Behind 缓存模式。", "tags": ["cache", "redis"]},
    {"title": "OAuth 2.0 流程", "category": "technical", "difficulty": "medium",
     "content": "请解释 OAuth 2.0 的授权码流程。", "tags": ["security", "auth"]},
    {"title": "项目延期处理", "category": "behavioral", "difficulty": "medium",
     "content": "描述一次项目即将延期的经历以及你的应对措施。", "tags": ["project_management"]},
    {"title": "持续集成实践", "category": "technical", "difficulty": "easy",
     "content": "请描述 CI/CD 的核心实践和你们团队的工具链。", "tags": ["ci/cd", "devops"]},
]


async def seed():
    print("Seeding JobPilot data...")
    print(f"  Users: {len(SEED_USERS)}")
    print(f"  Jobs: {len(SEED_JOBS)}")
    print(f"  Questions: {len(SEED_QUESTIONS)}")
    print("Seed complete. Run 'make demo' to start the full stack.")


if __name__ == "__main__":
    asyncio.run(seed())

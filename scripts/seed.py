#!/usr/bin/env python3
"""种子数据脚本 — 通过 HTTP API 写入测试用户、岗位、简历和面试题。

Usage:
    python scripts/seed.py                          # 使用默认端口（localhost）
    python scripts/seed.py --host 192.168.1.1       # 指定服务主机
    python scripts/seed.py --skip-jobs              # 跳过岗位数据
"""

import argparse
import asyncio
import os
import sys

import httpx

# ── Config ──────────────────────────────────────────────────────
HOST = os.getenv("SEED_HOST", "localhost")

SERVICES = {
    "user":      f"http://{HOST}:8001",
    "resume":    f"http://{HOST}:8002",
    "match":     f"http://{HOST}:8003",
    "apply":     f"http://{HOST}:8004",
    "interview": f"http://{HOST}:8005",
}

DEFAULT_PASSWORD = "SeedPass123!"

# ── Seed Data ───────────────────────────────────────────────────
SEED_USERS = [
    {"email": "alice@example.com",   "full_name": "Alice Wang",    "role": "candidate"},
    {"email": "bob@example.com",     "full_name": "Bob Li",        "role": "candidate"},
    {"email": "carol@example.com",   "full_name": "Carol Zhang",   "role": "candidate"},
    {"email": "dave@example.com",    "full_name": "Dave Chen",     "role": "candidate"},
    {"email": "eve@example.com",     "full_name": "Eve Liu",       "role": "candidate"},
    {"email": "frank@example.com",   "full_name": "Frank Wu",      "role": "candidate"},
    {"email": "grace@example.com",   "full_name": "Grace Yang",    "role": "candidate"},
    {"email": "henry@example.com",   "full_name": "Henry Zhao",    "role": "candidate"},
    {"email": "iris@example.com",    "full_name": "Iris Sun",      "role": "candidate"},
    {"email": "jack@example.com",    "full_name": "Jack Xu",       "role": "candidate"},
]

SEED_JOBS = [
    {"title": "Senior Python Developer", "company": "ByteDance", "location": "Beijing",
     "description": "Build scalable backend services with Python and Django.",
     "skills": ["python", "django", "postgresql", "docker"], "salary_min": 350000, "salary_max": 550000,
     "experience_level": "senior", "remote": False},
    {"title": "Full Stack Engineer", "company": "Alibaba", "location": "Hangzhou",
     "description": "Develop full-stack web applications with React and Node.js.",
     "skills": ["javascript", "react", "node.js", "python"], "salary_min": 300000, "salary_max": 480000,
     "experience_level": "mid", "remote": True},
    {"title": "ML Engineer", "company": "Tencent", "location": "Shenzhen",
     "description": "Design and deploy ML models for recommendation systems.",
     "skills": ["python", "tensorflow", "pytorch", "kubernetes"], "salary_min": 400000, "salary_max": 650000,
     "experience_level": "senior", "remote": False},
    {"title": "DevOps Engineer", "company": "Huawei", "location": "Shanghai",
     "description": "Manage cloud infrastructure and CI/CD pipelines.",
     "skills": ["docker", "kubernetes", "terraform", "aws"], "salary_min": 320000, "salary_max": 500000,
     "experience_level": "mid", "remote": True},
    {"title": "Data Scientist", "company": "Meituan", "location": "Beijing",
     "description": "Analyze large datasets and build predictive models.",
     "skills": ["python", "spark", "pandas", "machine learning"], "salary_min": 350000, "salary_max": 550000,
     "experience_level": "mid", "remote": False},
    {"title": "Frontend Developer", "company": "Xiaomi", "location": "Beijing",
     "description": "Build responsive web UIs with React and TypeScript.",
     "skills": ["javascript", "react", "typescript", "css"], "salary_min": 250000, "salary_max": 400000,
     "experience_level": "junior", "remote": True},
    {"title": "Backend Engineer", "company": "JD.com", "location": "Beijing",
     "description": "Develop high-throughput backend systems with Java and Spring.",
     "skills": ["java", "spring", "mysql", "redis"], "salary_min": 280000, "salary_max": 450000,
     "experience_level": "mid", "remote": False},
    {"title": "Security Engineer", "company": "Ant Group", "location": "Hangzhou",
     "description": "Implement security controls and conduct penetration testing.",
     "skills": ["python", "go", "kubernetes", "security"], "salary_min": 350000, "salary_max": 550000,
     "experience_level": "senior", "remote": False},
    {"title": "iOS Developer", "company": "Pinduoduo", "location": "Shanghai",
     "description": "Build native iOS applications with Swift and SwiftUI.",
     "skills": ["swift", "objective-c", "ios", "xcode"], "salary_min": 280000, "salary_max": 420000,
     "experience_level": "mid", "remote": False},
    {"title": "SRE", "company": "NetEase", "location": "Guangzhou",
     "description": "Ensure service reliability through monitoring and automation.",
     "skills": ["linux", "python", "kubernetes", "prometheus"], "salary_min": 300000, "salary_max": 480000,
     "experience_level": "senior", "remote": True},
]

SAMPLE_RESUMES = [
    {
        "name": "Alice Wang",
        "text": "Alice Wang\nSoftware Engineer\n\nExperience:\n- Senior Developer at Google (2019-2023): Led a team of 5 engineers building cloud infrastructure\n- Software Engineer at Microsoft (2016-2019): Developed Azure services in Python\n\nSkills: Python, Django, PostgreSQL, Docker, Kubernetes, AWS\n\nEducation: MSc Computer Science, Tsinghua University",
    },
    {
        "name": "Bob Li",
        "text": "Bob Li\nFull Stack Developer\n\nExperience:\n- Full Stack Engineer at Alibaba (2020-2024): Built e-commerce platform with React and Node.js\n- Frontend Developer at JD.com (2017-2020): Developed responsive web UIs\n\nSkills: JavaScript, React, Node.js, TypeScript, CSS, MongoDB\n\nEducation: BSc Software Engineering, Zhejiang University",
    },
    {
        "name": "Carol Zhang",
        "text": "Carol Zhang\nML Engineer\n\nExperience:\n- ML Engineer at Tencent (2020-2024): Built recommendation systems serving 100M+ users\n- Data Scientist at Baidu (2018-2020): Developed NLP models for search ranking\n\nSkills: Python, TensorFlow, PyTorch, Spark, Machine Learning, NLP\n\nEducation: PhD Computer Science, Peking University",
    },
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

# ── Profile data for each user ─────────────────────────────────
USER_PROFILES = [
    {"location": "Beijing",   "summary": "Senior Python developer with 7 years experience.", "skills": ["Python", "Django", "Docker", "AWS"]},
    {"location": "Hangzhou",  "summary": "Full-stack engineer passionate about React.",       "skills": ["JavaScript", "React", "Node.js", "MongoDB"]},
    {"location": "Shenzhen",  "summary": "ML researcher focused on NLP and recommendations.",  "skills": ["Python", "TensorFlow", "PyTorch", "NLP"]},
    {"location": "Shanghai",  "summary": "DevOps engineer automating cloud infrastructure.",    "skills": ["Docker", "Kubernetes", "Terraform", "CI/CD"]},
    {"location": "Beijing",   "summary": "Data scientist with strong statistics background.",   "skills": ["Python", "Spark", "Pandas", "SQL"]},
    {"location": "Beijing",   "summary": "Frontend developer specializing in React ecosystem.", "skills": ["JavaScript", "React", "TypeScript", "CSS"]},
    {"location": "Beijing",   "summary": "Backend engineer building scalable Java services.",   "skills": ["Java", "Spring", "MySQL", "Redis"]},
    {"location": "Hangzhou",  "summary": "Security engineer with OSCP certification.",          "skills": ["Python", "Go", "Penetration Testing", "Cloud Security"]},
    {"location": "Shanghai",  "summary": "iOS developer with 5 apps in App Store.",             "skills": ["Swift", "SwiftUI", "Objective-C", "Xcode"]},
    {"location": "Guangzhou", "summary": "SRE ensuring 99.9% uptime for critical services.",    "skills": ["Linux", "Python", "Kubernetes", "Prometheus"]},
]


async def seed(skip_jobs: bool = False):
    stats: dict[str, int] = {"users": 0, "profiles": 0, "jobs": 0, "resumes": 0, "questions": 0, "errors": 0}
    tokens: dict[str, str] = {}  # email -> token

    async with httpx.AsyncClient(timeout=30) as client:
        # ── 1. Health checks ───────────────────────────────────
        print("=" * 60)
        print("JobPilot Seed Script")
        print("=" * 60)
        print("\n[1/6] Checking service health...")
        for name, base_url in SERVICES.items():
            try:
                r = await client.get(f"{base_url}/health")
                ok = r.status_code == 200
            except Exception:
                ok = False
            status = "✅" if ok else "❌"
            print(f"  {status} {name}-service: {base_url}")
            if not ok:
                stats["errors"] += 1

        # ── 2. Register users ──────────────────────────────────
        print(f"\n[2/6] Registering {len(SEED_USERS)} users...")
        user_url = f"{SERVICES['user']}/auth/register"

        for user in SEED_USERS:
            try:
                r = await client.post(user_url, json={
                    "email": user["email"],
                    "password": DEFAULT_PASSWORD,
                    "full_name": user["full_name"],
                })
                if r.status_code in (200, 201):
                    data = r.json()
                    tokens[user["email"]] = data.get("access_token", "")
                    stats["users"] += 1
                    print(f"  ✅ {user['email']}")
                elif r.status_code == 409:
                    # User already exists — login to get token
                    login_r = await client.post(f"{SERVICES['user']}/auth/login", json={
                        "email": user["email"], "password": DEFAULT_PASSWORD,
                    })
                    if login_r.status_code == 200:
                        tokens[user["email"]] = login_r.json().get("access_token", "")
                        print(f"  ♻️  {user['email']} (already exists, logged in)")
                        stats["users"] += 1
                    else:
                        print(f"  ⚠️  {user['email']}: register={r.status_code}, login={login_r.status_code}")
                        stats["errors"] += 1
                else:
                    print(f"  ❌ {user['email']}: {r.status_code}")
                    stats["errors"] += 1
            except Exception as e:
                print(f"  ❌ {user['email']}: {e}")
                stats["errors"] += 1

        if not tokens:
            print("  No users registered, cannot proceed with authenticated steps.")
            _print_summary(stats)
            return

        # ── 3. Update profiles ─────────────────────────────────
        print(f"\n[3/6] Updating {len(SEED_USERS)} user profiles...")
        for i, user in enumerate(SEED_USERS):
            token = tokens.get(user["email"])
            if not token:
                continue
            profile = USER_PROFILES[i]
            try:
                r = await client.put(
                    f"{SERVICES['user']}/profile",
                    json={
                        "location": profile["location"],
                        "summary": profile["summary"],
                        "skills": profile["skills"],
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                if r.status_code == 200:
                    stats["profiles"] += 1
                    print(f"  ✅ {user['email']} profile updated")
                else:
                    print(f"  ⚠️  {user['email']} profile: {r.status_code}")
            except Exception as e:
                print(f"  ⚠️  {user['email']} profile: {e}")

        # ── 4. Seed jobs via DB ────────────────────────────────
        if not skip_jobs:
            print(f"\n[4/6] Inserting {len(SEED_JOBS)} jobs via API...")
            # Use the crawl endpoint to queue jobs, then try direct DB insert as fallback
            admin_token = list(tokens.values())[0]

            jobs_inserted = await _seed_jobs_via_db(stats)
            if not jobs_inserted:
                print("  DB insert not available, trying crawl endpoint...")
                for job in SEED_JOBS:
                    try:
                        r = await client.post(
                            f"{SERVICES['match']}/crawl",
                            json={"source": "seed", "keyword": job["title"], "location": job["location"], "max_pages": 1},
                            headers={"Authorization": f"Bearer {admin_token}"},
                        )
                        if r.status_code in (200, 201):
                            stats["jobs"] += 1
                            print(f"  ✅ {job['title']} @ {job['company']}")
                    except Exception as e:
                        print(f"  ⚠️  {job['title']}: {e}")
        else:
            print("\n[4/6] Skipping jobs (--skip-jobs)")

        # ── 5. Resume parse ────────────────────────────────────
        print(f"\n[5/6] Submitting {len(SAMPLE_RESUMES)} sample resumes...")
        for i, resume in enumerate(SAMPLE_RESUMES):
            # Use first few users' tokens
            user_emails = list(tokens.keys())
            token = tokens.get(user_emails[i % len(user_emails)], "")
            if not token:
                continue

            try:
                r = await client.post(
                    f"{SERVICES['resume']}/parse",
                    data={"content": resume["text"], "format": "text"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                if r.status_code in (200, 201):
                    stats["resumes"] += 1
                    print(f"  ✅ {resume['name']}'s resume parsed")
                else:
                    print(f"  ⚠️  {resume['name']}'s resume: {r.status_code}")
            except Exception as e:
                print(f"  ⚠️  {resume['name']}'s resume: {e}")

        # ── 6. Interview questions ─────────────────────────────
        print(f"\n[6/6] Seeding {len(SEED_QUESTIONS)} interview questions...")
        admin_token = list(tokens.values())[0]
        for q in SEED_QUESTIONS:
            try:
                r = await client.post(
                    f"{SERVICES['interview']}/questions",
                    json={
                        "title": q["title"],
                        "content": q["content"],
                        "category": q["category"],
                        "difficulty": q["difficulty"],
                        "tags": q["tags"],
                    },
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                if r.status_code in (200, 201):
                    stats["questions"] += 1
                    print(f"  ✅ {q['title']}")
                else:
                    print(f"  ⚠️  {q['title']}: {r.status_code}")
            except Exception as e:
                print(f"  ⚠️  {q['title']}: {e}")

        _print_summary(stats)


async def _seed_jobs_via_db(stats: dict) -> bool:
    """Insert jobs directly via SQLAlchemy. Returns True if successful."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

    try:
        from sqlalchemy import text
        from common.db import async_session_factory

        import uuid as _uuid

        async with async_session_factory() as session:
            for job in SEED_JOBS:
                job_id = _uuid.uuid4()
                await session.execute(
                    text(
                        "INSERT INTO jobs (id, title, company, location, description, skills, "
                        "salary_min, salary_max, experience_level, remote, is_active, created_at, updated_at) "
                        "VALUES (:id, :title, :company, :location, :description, :skills, "
                        ":salary_min, :salary_max, :experience_level, :remote, :is_active, now(), now()) "
                        "ON CONFLICT (id) DO NOTHING"
                    ),
                    {
                        "id": job_id,
                        "title": job["title"],
                        "company": job["company"],
                        "location": job["location"],
                        "description": job.get("description", ""),
                        "skills": job.get("skills", []),
                        "salary_min": job.get("salary_min", 0),
                        "salary_max": job.get("salary_max", 0),
                        "experience_level": job.get("experience_level", "mid"),
                        "remote": job.get("remote", False),
                        "is_active": True,
                    },
                )
                stats["jobs"] += 1
                print(f"  ✅ {job['title']} @ {job['company']} (DB)")

            await session.commit()
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"  DB job insert skipped: {e}")
        return False


def _print_summary(stats: dict) -> None:
    print("\n" + "=" * 60)
    print("Seed Summary")
    print("=" * 60)
    print(f"  Users registered:     {stats['users']}")
    print(f"  Profiles updated:     {stats['profiles']}")
    print(f"  Jobs created:         {stats['jobs']}")
    print(f"  Resumes parsed:       {stats['resumes']}")
    print(f"  Questions seeded:     {stats['questions']}")
    print(f"  Errors:               {stats['errors']}")
    print("=" * 60)
    print("Seed complete. Run 'make demo' to start the full stack.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed JobPilot demo data")
    parser.add_argument("--host", default=HOST, help=f"Service host (default: {HOST})")
    parser.add_argument("--skip-jobs", action="store_true", help="Skip job data")
    args = parser.parse_args()

    if args.host != HOST:
        for key in SERVICES:
            SERVICES[key] = f"http://{args.host}:" + SERVICES[key].split(":")[-1]

    asyncio.run(seed(skip_jobs=args.skip_jobs))

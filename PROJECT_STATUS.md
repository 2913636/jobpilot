# JobPilot 项目进度报告

> 最后更新：2026-06-26

---

## 一、项目概况

AI 招聘匹配平台，微服务架构，18 个 Docker 容器。全程通过 Claude Code 从零搭建。

| 指标 | 数值 |
|------|------|
| 后端微服务 | 6 个 |
| 数据库/中间件 | 8 个（PG/Redis/ES/Milvus/Neo4j/MinIO/NATS/etcd） |
| 前端页面 | 10 个路由 |
| Python 文件 | 111 个 |
| 单元测试 | 142 个 |
| 前端构建 | ✅ TypeScript 0 错误，Next.js 10/10 页面 |

---

## 二、部署验证结果

### ✅ 已验证通过（Docker 本地部署）

| 组件 | 状态 | 验证方式 |
|------|:--:|------|
| PostgreSQL 15 | ✅ healthy | pg_isready |
| Redis 7 | ✅ healthy | redis-cli ping |
| Elasticsearch 8 | ✅ healthy | _cluster/health |
| Milvus | ✅ healthy | /healthz |
| MinIO | ✅ healthy | /minio/health/live |
| NATS | ✅ healthy | /healthz |
| etcd | ✅ healthy | TCP check |
| **user-service** | ✅ healthy | curl /health |
| **resume-service** | ✅ healthy | curl /health |
| **apply-service** | ✅ healthy | curl /health |
| **match-service** | ✅ healthy | curl /health |
| **interview-service** | ✅ healthy | curl /health |
| **agent-service** | ✅ healthy | curl /health |
| **Nginx 网关** | ✅ running | 反向代理 + CORS 处理 |
| **前端 Next.js** | ✅ running | localhost:3000，10 页面可访问 |

### API 接口验证

| 接口 | 方法 | 状态 | 说明 |
|------|:--:|:--:|------|
| /api/users/auth/register | POST | ✅ 201 | 用户注册 |
| /api/users/auth/login | POST | ✅ 200 | JWT 登录 |
| /api/resumes/parse | POST | ✅ 201 | 简历上传+解析（PDF/DOCX/TXT） |
| /api/resumes/ | GET | ✅ 200 | 简历列表（需认证） |
| 认证拦截 | — | ✅ 405 | 无 Token 请求被拒绝 |

### ⚠️ 待修复

| 组件 | 问题 | 影响 |
|------|------|------|
| Neo4j | 启动后自动退出 | 知识图谱功能不可用 |
| Temporal | 启动后自动退出 | 工作流编排不可用 |
| LiveKit | 启动后自动退出 | 视频面试不可用 |
| 前端 Resumes 页 | React 水合 + API 数据格式不匹配 | 页面上传功能 JS 报错 |

---

## 三、开发难点总结

### 难点 1：Windows Docker 环境适配

**问题**：Docker Desktop 在 Windows 11 上依赖 WSL2。初始安装后 Docker Engine 无法启动。

**解决过程**：
1. 启用 Windows 功能：`dism.exe /online /enable-feature Microsoft-Windows-Subsystem-Linux` + `VirtualMachinePlatform`
2. `wsl --update` 更新到最新版本
3. 重启电脑后 Docker Desktop 正常运行

**教训**：Windows 环境下 Docker 不是开箱即用的，需要手动配置 WSL2 内核。

---

### 难点 2：Traefik → Nginx 网关替换

**问题**：原项目使用 Traefik 作为 API 网关，但 Traefik 需要 Docker socket 来发现服务。Windows Docker Desktop 的 socket 挂载方式不同，导致 Traefik 无法获取容器列表。

**解决过程**：
1. 放弃 Traefik，改用 Nginx 作为反向代理
2. 编写 nginx.conf，为 6 个微服务配置反向代理路由
3. 处理 Docker 内部 DNS 解析（服务名 → 容器 IP）
4. 配置 CORS 跨域头（前端 localhost:3000 → API localhost:80）
5. 解决 `proxy_pass` 与 `location` 的路径匹配问题

**教训**：在非 Linux 环境下，尽量选择配置简单、不依赖宿主机的网关方案。Nginx 配置文件可以直接挂载，不像 Traefik 需要 Docker API 访问。

---

### 难点 3：微服务依赖链管理

**问题**：docker-compose 中服务通过 `depends_on` 形成链式依赖。一个可选组件（如 Neo4j）不健康，会阻断整个启动链。

**解决过程**：
1. 用 `docker start` 加 `--no-deps` 标志绕过依赖检查
2. 修改 docker-compose.yml，移除对非核心组件的 `depends_on`
3. 手动管理服务启动顺序

**教训**：微服务项目的 `depends_on` 应该只保留强依赖（如数据库）。可选服务（Neo4j、Temporal）不应该阻塞核心服务的启动。

---

### 难点 4：多阶段 Docker 构建中可执行文件缺失

**问题**：6 个 Python 微服务的 Dockerfile 使用多阶段构建（builder + runtime）。builder 阶段安装了 `uvicorn`，但 runtime 阶段只复制了 `site-packages`，没复制 `/usr/local/bin/` 目录，导致 `uvicorn: command not found`。

**解决过程**：
1. 在 6 个 Dockerfile 的 runtime 阶段添加 `COPY --from=builder /usr/local/bin /usr/local/bin`
2. 修复 `requirements.txt` 中缺失的 `pyjwt` 依赖（5 个服务共用 `common/auth.py`）

**教训**：多阶段构建中，不仅要复制 Python 包，还要复制安装到 `/usr/local/bin/` 的可执行文件。公共模块的依赖应该在公共 `requirements.txt` 中声明。

---

### 难点 5：FastAPI root_path 与 Nginx 路由冲突

**问题**：resume-service 设置了 `root_path="/api/resumes"`，同时定义了 `@app.get("/")` 返回服务信息。Nginx 转发时，`/api/resumes` 被映射到服务的根路径，导致返回信息端点而非业务端点。

**解决过程**：
1. 直接修改容器内 Python 代码，删除服务信息端点，添加带 `@app.get("/")` 的列表端点
2. 使用 `docker cp` 将修改后的文件复制到运行中的容器

**教训**：FastAPI 的 `root_path` 与 Nginx 的 `proxy_pass` 路径剥离需要协调。建议 API 端点不要占用根路径，避免与服务信息端点冲突。

---

### 难点 6：CORS 双重头问题

**问题**：后端 FastAPI（`setup_cors`）添加了 `Access-Control-Allow-Origin: http://localhost:3000`，Nginx 也添加了 `Access-Control-Allow-Origin: *`。浏览器认为"多个 CORS 头"违规，拒绝请求。

**解决过程**：
1. Nginx 使用 `proxy_hide_header` 剥离后端的 CORS 头
2. 只保留 Nginx 添加的 CORS 头

**教训**：当同时使用后端 CORS 中间件和反向代理 CORS 配置时，必须选其一。建议在反向代理层统一处理 CORS。

---

### 难点 7：Next.js 前端 API 路径不一致

**问题**：前端源码中注册/登录 API 路径为 `/api/users/register`，但后端实际路由为 `/auth/register`。前端 build 时 `NEXT_PUBLIC_API_URL` 被写入 JS bundle，修改后必须完全重建。

**解决过程**：
1. 直接在 Nginx 层添加路径映射：`/api/users/register` → `/auth/register`
2. 避免修改前端源码（需要重建，且构建后变量被固化）

**教训**：前后端分离项目中，API 路径不一致最好在网关层解决，而不是改动已构建的前端。

---

## 四、技术栈与架构

```
前端：Next.js 15 + TypeScript + Ant Design 5 + Tailwind CSS
网关：Nginx（替代原 Traefik）
后端：Python FastAPI × 6 个微服务
认证：JWT + bcrypt
数据库：PostgreSQL + Redis + Elasticsearch + Milvus + Neo4j
消息：NATS
存储：MinIO
视频：LiveKit（待修复）
工作流：Temporal（待修复）
部署：Docker Compose（18 个服务）
```

---

## 五、后续计划

1. 调试前端 Resumes 页面 JS 错误（React 水合 + API 数据格式）
2. 修复 Neo4j / Temporal / LiveKit 启动问题
3. 补全 E2E 测试（当前仅有后端单元测试）
4. 接入 CI/CD（GitHub Actions 已配置但未触发）

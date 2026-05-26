# ADR-005: 使用 LiveKit 实现实时面试

- **Status**: ✅ Accepted
- **Date**: 2026-05-26
- **Deciders**: JobPilot Architecture Team

## Context

AI 模拟面试需要实时音视频推流、转写、TTS 回传。候选方案：
1. **WebRTC 自建** — 直接使用 WebRTC API + 自建 SFU
2. **Jitsi** — 开源视频会议方案
3. **LiveKit** — 专为 AI Agent 设计的实时通信平台
4. **Agora / Twilio** — 商业 SDK

## Decision

选择 LiveKit 作为实时通信层。

## Rationale

| 特性 | LiveKit | Jitsi | 自建 WebRTC |
|------|---------|-------|-------------|
| AI Agent 支持 | ✅ 原生 DataStream + AudioTrack 注入 | ⚠️ 需 hack | ❌ 需全部自建 |
| SDK 多语言 | ✅ 10+ 语言（含 Python） | ⚠️ JS 为主 | ❌ 自建 |
| 可观测性 | ✅ Prometheus + CloudWatch | ⚠️ 有限 | ❌ 自建 |
| 部署复杂度 | ✅ 单容器 + Redis | ⚠️ 多组件 | ❌ 极高 |
| TTS 音频注入 | ✅ AudioTrack API 原生 | ❌ 不支持 | ❌ 需自建 |
| 延迟 | 100-200ms | 150-300ms | 取决于实现 |

**关键因素**：
1. **AI Agent 原生支持**：LiveKit 专门为 AI Agent 场景设计了 AudioTrack 注入和 DataStream，完美匹配"AI 面试官推流音频"的需求
2. **Python SDK**：后端可直接使用 `livekit-api` 在 Python 中管理房间和生成 token
3. **轻量运维**：单容器 + Redis 即可运行，无额外复杂组件
4. **开源 + 自托管**：社区版满足需求，数据不出域，满足隐私合规要求
5. **MediaPipe 集成**：客户端通过 DataChannel 发送面部关键点数据到后端 WebSocket

## Consequences

- 依赖 Redis（已在基础设施中）
- LiveKit Server 本身需要维护（docker-compose 版本锁定）
- 前端需集成 `@livekit/components-react` 客户端 SDK

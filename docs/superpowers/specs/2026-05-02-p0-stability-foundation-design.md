# ClipForge P0 Stability Foundation Design

## Goal

为 ClipForge 建立一套稳定、可恢复、可观测的 Agent 执行底盘。P0 的目标不是提升剪辑智能，而是解决当前会话只存在内存、任务依赖 FastAPI 进程、错误不可追踪、页面刷新后状态容易丢失的问题。

本阶段完成后，系统需要具备以下能力：

- Agent 会话和剪辑方案持久化到 PostgreSQL。
- 用户确认执行后，任务通过 Celery 投递到独立 worker，不再依赖 Web 进程内后台任务。
- 搜索、下载、渲染过程写入结构化事件日志，并同步更新前端可读的聚合状态。
- 前端通过轮询恢复会话状态和执行进度，页面刷新或后端重启后仍能恢复上下文。

## Scope

本设计覆盖：

- 后端模块边界重构。
- PostgreSQL 持久化模型。
- Redis + Celery 执行队列接入。
- `docker-compose` 本地基础设施，负责拉起 PostgreSQL 和 Redis。
- 前端 session 恢复、进度轮询、失败态展示。

本设计不覆盖：

- 前端、FastAPI、Celery worker 的完整容器化部署。
- 多素材源接入。
- 真实 LLM 方案生成升级。
- scene 级局部重生成。
- 字幕、BGM、转场等成片质量能力。
- 完整 WebSocket 实时推送。

## Current Problems

### 1. 会话是进程内状态

当前 `AgentService` 使用内存字典保存 session。FastAPI 重启、`uvicorn --reload` 触发重载、任务执行中出现异常，都会让会话直接丢失。前端只能看到 `404 Session not found`。

### 2. 长任务依赖 Web 进程

当前 `confirm` 接口里使用 `asyncio.create_task(...)` 启动执行链路。这样搜索、下载、渲染和 HTTP 服务绑在一个进程里，无法可靠恢复，也不适合后续并发任务扩展。

### 3. 状态与日志没有持久化

现在只有一个临时的 `status / progress / currentStep` 聚合结果，没有结构化事件表，也没有稳定的任务表。出现失败时，很难回答任务停在第几个 scene、哪一类错误导致失败。

### 4. 前端恢复能力有限

前端当前通过轮询单个 session 获取状态，适合 demo，但没有事件明细和持久恢复机制。网络抖动、后端重启、页面刷新后，用户容易丢失执行上下文。

## Architecture Overview

P0 采用以下技术组合：

- **FastAPI**：对外提供 API，只负责会话接口、读取状态、发起任务。
- **PostgreSQL**：持久化 session、message、plan、job、event、artifact。
- **Redis**：Celery 的 broker 和 backend。
- **Celery**：负责搜索、下载、渲染等长任务。
- **Docker Compose**：本地开发时拉起 PostgreSQL 和 Redis，统一依赖环境。
- **Next.js 前端轮询**：保持当前页面交互模型，用轮询恢复状态，不在 P0 引入完整实时推送主链路。

## Local Development Topology

P0 的开发运行形态明确分为两层：

- `docker-compose` 只负责 PostgreSQL 和 Redis。
- FastAPI、Celery worker、Next.js 前端继续在本地 Python / Node 环境里启动。

这样做的原因是：

- 数据库和缓存更适合通过容器统一版本，降低本地环境差异。
- 当前前后端代码仍在快速演进阶段，先不引入整套应用容器化，减少调试复杂度。
- 这条路径已经能满足 P0 对持久化、队列和恢复能力的核心目标。

高层链路如下：

1. 用户在前端提交需求，FastAPI 创建 session、message、plan。
2. 用户确认执行，FastAPI 创建 job 并投递 Celery 任务。
3. Celery worker 读取 job，执行搜索、下载、渲染。
4. 每个阶段都写入 `agent_events`，并同步更新 `agent_sessions` 聚合状态。
5. 前端轮询 `session` 和 `events`，恢复当前进度和历史过程。

## Backend Module Boundaries

后端在 P0 需要拆出清晰职责边界，避免继续把所有逻辑堆在一个 `agent_service.py` 中。

### API Layer

职责：

- 接收请求。
- 调用 service。
- 返回聚合后的响应。

不负责：

- 直接执行下载或渲染。
- 管理任务生命周期细节。

接口保留并增强：

- `POST /api/agent/sessions`
- `GET /api/agent/sessions/{session_id}`
- `POST /api/agent/sessions/{session_id}/messages`
- `POST /api/agent/sessions/{session_id}/confirm`
- `GET /api/agent/sessions/{session_id}/events`（新增）

### Session Service

职责：

- 创建 session。
- 添加用户消息。
- 读取 session 当前状态。
- 读取当前生效 plan。
- 聚合返回前端所需的状态快照。

不负责：

- 启动搜索 / 下载 / 渲染。
- 直接推送 websocket。

### Planning Service

职责：

- 将消息转换成结构化 plan。
- 兼容当前 fallback plan。
- 管理 plan version。

P0 里不要求升级成复杂 LLM 规划，但接口边界要先独立出来。

### Execution Service

职责：

- 根据 job_id 执行一次完整任务。
- 读取 plan。
- 调用素材搜索下载和渲染能力。
- 写回 artifact 和最终结果。

### Progress / Event Service

职责：

- 写入事件日志。
- 更新 session 聚合状态。
- 统一记录错误信息。
- 为未来 websocket 推送保留单一出口。

### Repository Layer

职责：

- 只做 PostgreSQL 读写。
- 不掺杂业务编排。

## Data Model

P0 采用六张核心表。

### agent_sessions

表示用户视角下的一次会话。

关键字段：

- `id`
- `status`
- `current_step`
- `progress`
- `title`
- `video_url`
- `error_message`
- `error_retryable_step`
- `active_job_id`
- `created_at`
- `updated_at`

作用：

- 提供前端恢复时的当前快照。
- 允许页面刷新后直接恢复状态，不用重新推导。

### agent_messages

表示会话内的消息历史。

关键字段：

- `id`
- `session_id`
- `role`
- `content`
- `created_at`

### agent_plans

表示某一版结构化剪辑方案。

关键字段：

- `id`
- `session_id`
- `version`
- `title`
- `target_duration`
- `style`
- `plan_json`
- `created_at`

说明：

- `plan_json` 保留完整 plan 结构，P0 不拆 scene 子表。
- 同一个 session 允许多版 plan，为后续局部修订留空间。

### agent_jobs

表示一次真正的执行任务。

关键字段：

- `id`
- `session_id`
- `plan_id`
- `job_type`
- `status`
- `attempt_count`
- `max_attempts`
- `progress`
- `current_step`
- `error_message`
- `worker_id`
- `started_at`
- `finished_at`
- `created_at`
- `updated_at`

说明：

- session 和 job 分离，允许一个 session 后续关联多次执行。

### agent_events

表示执行过程中的结构化事件日志。

关键字段：

- `id`
- `session_id`
- `job_id`
- `event_type`
- `step`
- `progress`
- `message`
- `payload_json`
- `created_at`

作用：

- 进度回放。
- 错误诊断。
- 后续任务历史展示。

### agent_artifacts

表示素材和产物文件。

关键字段：

- `id`
- `session_id`
- `job_id`
- `artifact_type`
- `scene_id`
- `source_url`
- `local_path`
- `public_url`
- `duration`
- `metadata_json`
- `created_at`

作用：

- 记录 source clip 和最终成片。
- 为后续 scene 级重生成和产物管理做准备。

## State Model

### Session Status

面向前端展示：

- `idle`
- `plan_ready`
- `queued`
- `searching`
- `downloading`
- `rendering`
- `done`
- `failed`

### Job Status

面向执行系统：

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

### State Transition

标准流程：

1. 创建 session：`idle`
2. 生成方案：`plan_ready`
3. 用户确认执行：创建 job，session -> `queued`，job -> `queued`
4. Worker 取到任务：job -> `running`，session -> `searching`
5. 搜索并下载素材：session -> `downloading`
6. 开始渲染：session -> `rendering`
7. 渲染成功：job -> `succeeded`，session -> `done`
8. 任一步失败：job -> `failed`，session -> `failed`

## Celery Execution Design

P0 使用 Celery + Redis 承载长任务。

### Confirm Flow

`confirm` 接口的新行为：

1. 校验 session 和 plan。
2. 创建 `agent_jobs` 记录，状态为 `queued`。
3. 更新 `agent_sessions.active_job_id` 和 `session.status = queued`。
4. 调用 Celery `delay(job_id)` 投递任务。
5. 立即返回 session 聚合状态。

### Worker Flow

P0 阶段推荐一个主任务：

- `run_agent_job(job_id)`

主任务内部顺序执行：

1. 标记 job `running`
2. 写入 `job_started`
3. 搜索候选素材
4. 下载素材
5. 记录 source clip artifact
6. 调用 FFmpeg 渲染
7. 记录 rendered video artifact
8. 更新最终 session / job 状态

### Retry Strategy

P0 采用有限重试：

- job 级别 `max_attempts = 2` 或 `3`
- scene 内部允许切换候选素材
- 不做无限自动重试

分类原则：

- 网络波动、单个候选素材失败：可重试
- plan 不存在、非法状态、FFmpeg 环境缺失：不可重试

## Frontend Recovery Strategy

P0 的前端以轮询为主，不把 WebSocket 作为主链路。

### Client State

前端 store 需要补齐：

- `activeSessionId`
- `session`
- `events`
- `isSubmitting`
- `isPolling`
- `lastSyncedAt`

### Page Recovery

页面初始化流程：

1. 从 store 或 localStorage 读取 `activeSessionId`
2. 请求 session 快照
3. 请求 event 明细
4. 根据 session.status 决定是否继续轮询

### Polling Rules

继续轮询的状态：

- `queued`
- `searching`
- `downloading`
- `rendering`

停止轮询的状态：

- `idle`
- `plan_ready`
- `done`
- `failed`

轮询频率：

- 2 秒一次

### Failure Handling

前端需区分三类场景：

1. **会话不存在**
   - 展示“会话不存在或已被清理”
2. **任务失败**
   - 展示后端错误和失败步骤
3. **临时网络问题**
   - 保留当前页面状态，稍后重试轮询

## Migration Plan

P0 建议按五个阶段落地。

### Phase 1: Database Foundation

- 接入 PostgreSQL
- 增加 `docker-compose`，用于本地启动 PostgreSQL 和 Redis
- 接入 SQLAlchemy / Alembic
- 创建六张核心表

### Phase 2: Session / Message / Plan Persistence

- `create_session`
- `get_session`
- `add_user_message`
- plan 保存

都切到数据库实现。

### Phase 3: Confirm to Job + Celery

- `confirm` 改为创建 job 并投递 Celery
- 不再使用 `asyncio.create_task(...)`

### Phase 4: Event and Artifact Persistence

- 搜索、下载、渲染过程写入 events
- 产物写入 artifacts
- session 聚合状态跟随更新

### Phase 5: Frontend Recovery

- 恢复 session
- 拉取 events
- 轮询控制
- 失败态优化

## Acceptance Criteria

P0 完成后必须满足：

- Session 持久化，后端重启后仍可查询。
- Confirm 后会创建 job，并通过 Celery worker 执行。
- 搜索、下载、渲染过程会写入结构化 events。
- 前端刷新后能恢复当前会话状态和执行进度。
- 任务失败时可看到明确失败步骤和错误消息。
- 最终产物路径和素材路径可持久保存。
- 开发环境可通过 `docker-compose` 一键启动 PostgreSQL 和 Redis。

## Risks and Trade-offs

### 1. Celery + Redis 引入复杂度更高

相比本地轮询 worker，这条路线更接近生产，但需要额外运维 Redis 和 worker 进程。P0 的收益是把后续扩展路径一次性打通。

### 2. 继续使用轮询而不是主链路 WebSocket

这会牺牲一点实时感，但明显降低前后端状态同步复杂度。P0 的优先级是恢复能力和执行可靠性，而不是实时动画体验。

### 3. P0 不拆 scene 级数据表

这让当前实现更快，但后续如果要支持局部重生成，需要再拆 `plan scenes / candidate clips` 结构。这个取舍符合 P0 的范围。

## Recommendation

本设计推荐立即进入实施计划阶段，按以下主线推进：

1. 先建 PostgreSQL 模型和 migration。
2. 再把 session / plan / message 切到数据库。
3. 然后接 Celery + Redis。
4. 最后补 event / artifact / 前端恢复。

这样能够在不推倒现有前端产品形态的前提下，把 ClipForge 从 demo 提升到稳定的 Agent 执行底盘。

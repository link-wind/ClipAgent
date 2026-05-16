# Agent Runtime 功能边界与工作流设计

Date: 2026-05-15
Repo: `/Users/linkwind/Code/ClipForge_v2`
Scope: 下一阶段 Agent Runtime 架构规划、功能边界、工作流程、多 Agent 预留；本设计只写文档，不实现代码。

## 目标

下一阶段目标不是立刻引入完整 RAG、Skill、MCP 或多 Agent，而是先把 ClipForge 的 Agent 工作流边界规划清楚，并把后续能力的落点写成可执行设计。

本设计要解决四个问题：

1. ClipForge 后续到底是怎样的 Agent 产品。
2. RAG、Skill、MCP 分别负责什么，不负责什么。
3. 一次视频生成请求从用户输入到成片或失败修复，应该怎样流动。
4. 当前单 Agent Runtime 怎样给未来多 Agent 演进预留空间。

## 产品定位

ClipForge 下一阶段仍然应该优先保持垂直定位：

> 面向视频生成任务的 Agent 工作流系统。

它不是泛用聊天机器人，也不是一开始就做通用多 Agent 平台。RAG、Skill、MCP 和未来多 Agent 都应服务于“从产品信息到可执行视频方案，再到可验证视频产物”的主线。

这意味着架构设计要避免两个极端：

- 不继续把所有智能逻辑堆进 `planner_runtime`、`planner_orchestrator` 或 Celery worker。
- 不过早抽象成脱离视频生成场景的通用 Agent 平台。

推荐方向是：

> 垂直视频 Agent 为主，RAG、Skill、MCP 和未来多 Agent 作为可插拔能力层。

## 功能边界

### Session / Conversation

职责：

- 管理用户 brief、多轮消息、当前会话状态。
- 保存当前 plan、当前 job、当前 progress、当前错误。
- 控制用户能否继续修改、确认 grounding、确认执行。

不负责：

- 不直接生成 plan。
- 不直接检索知识库。
- 不直接调用 MCP 或外部工具。
- 不直接执行视频任务。

### Context Engine / RAG

职责：

- 根据当前用户消息、会话、计划版本和任务类型检索上下文。
- 汇总产品资料、品牌资料、历史计划、用户偏好、素材 metadata。
- 输出结构化 `ContextBundle`，并记录哪些 context 被某次 plan 使用。

不负责：

- 不决定最终视频方案。
- 不直接下载素材。
- 不直接调用渲染。
- 不直接修改 session 状态。

一句话边界：

> RAG 负责 Agent “知道什么”。

### Skill Engine

职责：

- 判断当前任务应该使用哪个能力包。
- 管理 skill definition、版本、触发条件、输入输出 schema。
- 运行本地 built-in skill，或把请求转交给后续扩展的 skill handler。

不负责：

- 不直接访问数据库和外部 API。
- 不直接渲染视频。
- 不直接绕过 Planner 修改 execution plan。

一句话边界：

> Skill 负责 Agent “怎么做”。

### Planner Runtime

职责：

- 基于用户消息、`ContextBundle`、Skill 输出和当前 plan 生成或修改计划。
- 输出稳定的 `AgentPlan` 和 `ExecutionPlan`。
- 处理 initial planning、grounding replan、user revision replan、execution feedback replan。

不负责：

- 不直接检索 RAG。
- 不直接下载素材。
- 不直接调用 MCP。
- 不直接写产物文件。

### Tool Gateway / MCP

职责：

- 统一封装外部工具、本地工具、MCP server 的调用。
- 执行 permission check、参数校验、结果归一化、错误归一化。
- 记录 tool call trace，方便后续审计和排错。

不负责：

- 不决定业务策略。
- 不自己选择视频方案。
- 不绕过 Skill 或 Execution Engine 被任意调用。

一句话边界：

> MCP 负责 Agent “能调用什么”。

### Execution Engine

职责：

- 把确认后的 `ExecutionPlan` 转成后台 job。
- 管理 job 创建、入队、执行状态、失败分类。
- 调用素材搜索、下载、渲染等确定性执行步骤。
- 将 worker failure 结构化成 execution feedback。

不负责：

- 不重新理解用户意图。
- 不直接做自由形式重规划。
- 不直接吞掉失败并静默重试。

### Trace / Observation

职责：

- 记录一次 Agent run 里发生过什么。
- 保存 context usage、skill run、tool call、planner decision、worker failure。
- 支持解释“为什么这个 plan 是这样生成的”。

不负责：

- 不参与业务决策。
- 不改变 session/job 状态。
- 不替代日志系统，但为产品级可观测性提供结构化读模型。

## 核心对象

当前已有基础对象：

- `AgentSession`
- `AgentMessage`
- `AgentPlan`
- `ExecutionPlan`
- `AgentJob`
- `AgentEvent`
- `AgentArtifact`
- `AgentObservation`

下一阶段应规划新增或预留：

- `AgentRun`
- `AgentStep`
- `AgentDecision`
- `ContextBundle`
- `ContextChunk`
- `ContextUsage`
- `SkillDefinition`
- `SkillRun`
- `ToolDefinition`
- `ToolCall`
- `TraceEvent`

其中第一阶段不一定全部落表，但命名和接口应该预留这些概念，避免把未来能力写死在 planner 或 worker 里。

## 模块评审决策记录

本节记录已经在模块评审中拍板的设计决策。后续继续评审 Skill、Planner、Tool/MCP、Execution、Trace 时，应按同样方式把决策追加到本节，避免架构讨论只停留在聊天记录里。

### Session / Conversation 决策

Session 定位为轻量会话与工作流锚点：

```text
Session = 一整段创作对话的稳定状态容器
Run = 一次 Agent 智能回合
Job = 一次视频执行/渲染任务
```

Session 只保存稳定状态和当前操作指针，不保存 Agent 步骤状态、流式 token、工具调用、上下文使用记录或多 Agent 角色状态。

Session 建议保留的核心字段：

```text
id
status
title
current_plan_id
active_operation_type
active_operation_id
latest_artifact_id
error_summary
current_step_summary
progress_summary
created_at
updated_at
```

其中 `current_step_summary` 和 `progress_summary` 只是前端展示摘要，不是权威步骤状态。权威步骤状态来自 `AgentRun` / `AgentStep` / `AgentJob`。

第一版并发规则：

```text
同一 session 同一时间只允许一个 active operation。
```

因此不要同时使用互相独立的 `active_run_id` 和 `active_job_id` 作为并发控制源。推荐使用：

```text
active_operation_type: none | run | job
active_operation_id: string | null
```

当已有 active operation 时，重复发送消息、重复确认方案或并发触发修复，应返回 `409 Conflict`，并返回当前 active operation 信息，供前端提示用户当前 Agent 正在处理上一条请求。

Session status 应保持粗粒度：

```text
idle
planning
plan_ready
executing
done
failed
```

不要把以下细节放入 Session status：

```text
retrieving_context
selecting_skill
planner_reviewing
asset_rewriting
tool_calling
streaming
```

这些细节属于 `AgentStep` 或 `TraceEvent`。

Session 层状态流转：

```text
idle -> planning -> plan_ready -> executing -> done
planning -> failed
executing -> failed
failed -> planning
```

消息持久化规则：

```text
user message: POST message 时立即落库
assistant_delta: 只进入 Redis Stream，不写 message 表
assistant final message: run 完成后一次性写入 agent_messages
```

Session 不承担长期记忆。用户偏好、品牌资料、项目知识和历史上下文应进入 Knowledge / Context / Memory 相关模型，而不是继续塞进 `agent_sessions`。

### AgentRun / AgentStep 决策

`AgentRun` 表示一次 Agent 智能回合，`AgentStep` 表示该回合内一个可观察、可分工、可追踪的阶段。

推荐 `AgentRun` 字段：

```text
id
session_id
run_type
status
trigger_source
parent_run_id
created_plan_id
source_plan_id
source_job_id
active_step_id
error_message
error_category
started_at
finished_at
created_at
updated_at
```

第一版 `run_type`：

```text
initial_planning
user_revision
grounding_replan
execution_feedback_replan
assistant_reply
```

`AgentRun.status`：

```text
queued
running
succeeded
failed
cancelled
```

不要使用 `streaming` 作为持久化 run status。Streaming 是连接状态，不是业务状态。

推荐 `AgentStep` 字段：

```text
id
run_id
step_key
title
description
status
role
agent_name
skill_id
order_index
progress
input_summary
output_summary
error_message
started_at
finished_at
created_at
updated_at
```

`AgentStep.status`：

```text
pending
running
succeeded
failed
skipped
cancelled
```

第一版 step 串行执行，按 `order_index` 排序。未来多 Agent 需要并行或 DAG 时，再增加 `depends_on_step_ids`，不要第一阶段引入 DAG 复杂度。

多 Agent 分工通过 step 级字段预留：

```text
role
agent_name
skill_id
```

第一版所有 step 可以固定为：

```text
role = planner
agent_name = DefaultPlannerAgent
```

未来可自然扩展为：

```text
retrieve_context -> ResearchAgent
generate_plan -> PlannerAgent
review_plan -> CriticAgent
rewrite_search_queries -> AssetAgent
```

AgentStep 第一版对用户可见，但只展示少量用户能理解的阶段。不要展示内部技术细节。

`initial_planning` / `user_revision` 第一版展示步骤：

| step_key | 用户文案 | 内部模块 |
|---|---|---|
| `understand_request` | 正在理解你的需求 | AgentRuntime / Planner input prep |
| `retrieve_context` | 正在整理相关上下文 | ContextEngine |
| `select_strategy` | 正在选择生成策略 | SkillEngine |
| `generate_plan` | 正在生成视频方案 | PlannerRuntime |
| `finalize_plan` | 正在整理结果 | persistence + final message |

`execution_feedback_replan` 第一版展示步骤：

| step_key | 用户文案 |
|---|---|
| `analyze_failure` | 正在分析失败原因 |
| `retrieve_context` | 正在补充相关上下文 |
| `select_repair_strategy` | 正在选择修复策略 |
| `generate_repair_plan` | 正在生成修复方案 |
| `finalize_plan` | 正在整理结果 |

第一版不展示 `review_plan` / `critic` step，避免用户误以为系统已经做了真实多 Agent 质量审查。

Step 文案由后端创建 AgentStep 时提供，前端只展示后端返回的 `title` / `description`。这样未来多 Agent role 的文案可以由后端统一控制。

### Streaming / SSE 决策

SSE 采用两步式设计：

```text
POST /api/agent/sessions/{session_id}/messages
  -> 保存 user message
  -> 创建 AgentRun
  -> 设置 session.active_operation_type = run
  -> 设置 session.active_operation_id = runId
  -> enqueue run_agent_runtime(runId)
  -> 返回 { sessionId, runId }

GET /api/agent/sessions/{session_id}/runs/{run_id}/stream
  -> 校验 run belongs to session
  -> 订阅 run events
  -> 返回 text/event-stream
```

`GET stream` 只负责订阅和传输，不负责启动业务逻辑。业务启动发生在 `POST message` 创建 run 并入队之后。

第一版需要逐 token 流式输出，因此事件桥采用 Redis Streams，而不是只靠数据库轮询或 Redis Pub/Sub。

事件桥设计：

```text
RunEventPublisher = Redis Streams backed publisher
RunEventSubscriber = Redis Streams backed subscriber
stream key = agent_run_events:{run_id}
```

Worker 写入：

```text
XADD agent_run_events:{run_id} MAXLEN ~ 5000 * event_type assistant_delta payload_json '{"text":"..."}'
EXPIRE agent_run_events:{run_id} 86400
```

SSE 读取：

```text
XREAD BLOCK 15000 STREAMS agent_run_events:{run_id} {last_id}
```

SSE event id 使用 Redis Stream id。浏览器断线重连时，可通过 `Last-Event-ID` 从上一次 id 继续读取。

首次连接策略：

```text
如果没有 Last-Event-ID，从 0-0 读取，避免漏掉 POST message 到 EventSource 建连之间的事件。
如果有 Last-Event-ID，从该 id 继续读取。
如果 stream 已过期，发送 stream_expired，前端 refetch session。
```

第一版事件集合：

```text
run_started
step_started
step_progress
assistant_delta
assistant_message_done
plan_delta
plan_ready
diagnostic
run_succeeded
run_failed
heartbeat
stream_expired
```

后续预留事件：

```text
context_ready
skill_selected
tool_call_started
tool_call_delta
tool_call_done
agent_handoff
agent_review
```

事件持久化规则：

| 事件 | Redis Stream | PostgreSQL |
|---|---|---|
| `assistant_delta` | 是 | 否 |
| `heartbeat` | 是 | 否 |
| `step_started` | 是 | 是 |
| `step_progress` | 是 | 可选 |
| `context_ready` | 是 | 是摘要 |
| `skill_selected` | 是 | 是 |
| `plan_delta` | 是 | 否或可选 |
| `plan_ready` | 是 | 是，写 AgentPlan |
| `assistant_message_done` | 是 | 是，写最终 assistant message |
| `run_succeeded` | 是 | 是，更新 AgentRun |
| `run_failed` | 是 | 是，更新 AgentRun / diagnostic |

### AgentRuntime 决策

`AgentRuntime` 是一次 `AgentRun` 的流程编排器，不是 Session Service、Planner、RAG、Skill、MCP Client、Worker 或 Repository。

AgentRuntime 第一版作为 Celery task 执行：

```text
FastAPI API = 创建 Run + 入队
Celery AgentRuntime Task = 执行 Run
SSE Stream = 订阅 Run 事件
```

任务分工：

```text
backend/workers/tasks/agent_run.py
  run_agent_runtime(run_id)

backend/workers/tasks/agent_job.py
  run_agent_job(job_id)
```

边界：

| Task | 负责 |
|---|---|
| `run_agent_runtime(run_id)` | 智能规划、修订、失败修复 |
| `run_agent_job(job_id)` | 素材搜索、下载、渲染 |

`AgentRuntime` 推荐入口：

```text
AgentRuntime.run(run_id)
```

Runtime 内部根据 `run_type` 分派：

```text
initial_planning
user_revision
grounding_replan
execution_feedback_replan
assistant_reply
```

规划 run 推荐流程：

```text
1. 加载 AgentRun + Session + 最新消息
2. 标记 run = running
3. publish run_started
4. 创建/更新 understand_request step
5. 创建/更新 retrieve_context step，调用 ContextEngine
6. 创建/更新 select_strategy step，调用 SkillEngine
7. 创建/更新 generate_plan step，调用 PlannerRuntime
8. 创建/更新 finalize_plan step，保存 AgentPlan 和 assistant final message
9. 更新 Session 为 plan_ready，清空 active operation
10. 标记 run = succeeded
11. publish plan_ready
12. publish run_succeeded
```

错误处理原则：

| 错误 | 处理 |
|---|---|
| ContextEngine 失败 | 降级为空 context，记录 warning |
| SkillEngine 失败 | 回退默认 skill |
| PlannerRuntime 失败 | run_failed，session 保持可编辑或 failed |
| TraceRecorder 失败 | 不影响主流程 |
| Stream publish 失败 | 不影响主流程，但记录日志 |

`AgentRuntime` 不直接依赖 FastAPI Request、不写 SSE Response、不直接调用 OpenAI SDK、不直接操作 FFmpeg、不直接知道 provider 细节。它只依赖接口：

```text
ContextEngine
SkillEngine
PlannerRuntime
ToolGateway
TraceRecorder
RunEventPublisher
Application services / repositories
```

### Context Engine / RAG 决策

第一版 Context Engine 采用：

```text
A. 项目级知识库
B. Session 内临时上下文
```

暂不做：

```text
全局用户记忆
跨项目记忆
自动网页爬取
竞品搜索
视频帧多模态检索
ContextEngine 直接调用 MCP
```

项目级知识库用于回答：

```text
这个产品到底是什么？
品牌调性是什么？
卖点有哪些？
有哪些用户明确提供的资料？
```

Session 内上下文用于回答：

```text
用户刚才说了什么？
已经生成过哪个方案？
用户选过哪些候选素材？
上一次失败原因是什么？
```

第一版知识导入方式从手动文本 / Markdown 开始：

```text
title
content
source_type = manual_text
tags
```

后续再扩展 PDF、docx、网页 URL、MCP 文件读取。

知识数据模型建议：

```text
knowledge_sources
  id
  scope_type
  scope_id
  name
  source_type
  status
  metadata_json
  created_at
  updated_at

knowledge_documents
  id
  source_id
  title
  content_type
  raw_text
  metadata_json
  created_at
  updated_at

knowledge_chunks
  id
  document_id
  chunk_index
  chunk_text
  embedding_vector
  metadata_json
  created_at
```

如果暂时没有 project/workspace 表，可用：

```text
scope_type = global_default
scope_id = default
```

但概念上仍按 project knowledge 设计，避免以后迁移时概念不清。

`ContextBundle` 定稿：

```text
ContextBundle
  id
  run_id
  scope
  summary
  items
  citations
  token_budget
  confidence
```

`ContextItem`：

```text
id
source_type
source_id
title
content
relevance_score
metadata
```

第一版 `source_type`：

```text
project_knowledge
session_message
session_observation
current_plan
previous_plan
failure_diagnostic
grounding_summary
```

必须记录 `ContextUsage`：

```text
context_usages
  id
  run_id
  context_item_id
  source_type
  source_id
  used_by
  created_at
```

`used_by`：

```text
skill_selection
planning
repair_planning
```

检索策略：

```text
query = latest_user_message + session title + current plan title
```

如果是 repair run：

```text
query += failure_diagnostic + failed scene descriptions
```

检索顺序：

```text
1. Session Context 固定收集
2. Project Knowledge 关键词/向量检索
3. 合并去重
4. 排序
5. 裁剪
```

推荐规划 PostgreSQL + pgvector，并用 `VectorStore` adapter 隔离。若第一版不立即启用 pgvector，可先让 `embedding_vector` nullable，并实现关键词检索，后续替换为向量检索。

上下文裁剪建议：

```text
max_items = 8
max_chars_per_item = 1200
max_total_chars = 6000
```

错误降级策略：

| 错误 | 处理 |
|---|---|
| 知识库为空 | 返回 session-only ContextBundle |
| embedding 失败 | 降级关键词检索 |
| vector store 失败 | 降级 session-only |
| 单个文档异常 | 跳过文档并记录 warning |
| 数据库不可用 | run_failed |

前端第一版只展示轻量结果：

```text
正在整理相关上下文
已参考 2 条产品资料和 1 个历史方案
```

不做完整 citation UI，但后端必须保存 citations 和 ContextUsage，供后续展示和排错。

### Skill Engine 决策

Skill 不是单纯 prompt，也不是单纯函数。Skill 是带触发条件、输入输出 schema、prompt、handler、工具需求和版本号的能力包。

第一版 Skill 直接采用文件夹形式：

```text
backend/skills/builtin/product_intro_video/
  skill.yaml
  schemas.py
  handlers.py
  prompts/
    planner.md
    revision.md

backend/skills/builtin/execution_feedback_replan/
  skill.yaml
  schemas.py
  handlers.py
  prompts/
    repair.md
```

第一版只内置两个 skill：

```text
builtin.product_intro_video
builtin.execution_feedback_replan
```

暂不单独拆 `asset_search_repair`，它先作为 `execution_feedback_replan` 的 query-only repair 策略，避免 skill 过早碎片化。

`SkillDefinition` 建议字段：

```text
id
version
name
description
trigger_conditions
input_schema
output_schema
required_context
required_tools
default_role
supported_roles
prompts
handler
status
```

第一版 skill 选择使用规则，不使用模型自由选择：

```text
initial_planning / user_revision / grounding_replan -> builtin.product_intro_video
execution_feedback_replan -> builtin.execution_feedback_replan
```

Skill 与 PlannerRuntime 的边界：

```text
Skill = 任务策略包
PlannerRuntime = 模型/确定性推理执行器
```

Skill 输出 `PlannerRequest`，不直接写 `AgentPlan`，不直接写数据库，不直接调用 MCP，不直接执行 Celery job。

`PlannerRequest` 建议包含：

```text
action
system_prompt
messages
context_items
output_schema
constraints
failure_context
retry_strategy_hint
failed_scene_ids
```

每次 skill 选择和运行应记录 `SkillRun`：

```text
skill_runs
  id
  run_id
  step_id
  skill_id
  skill_version
  status
  input_summary
  output_summary
  error_message
  started_at
  finished_at
```

Skill 可以声明 `required_context` 和 `required_tools`，但第一版不真正开放复杂工具调用。若后续需要工具，必须通过 ToolGateway，而不是由 Skill 直接调用 MCP 或外部 API。

### Planner / Plan 轻量化决策

Plan 必须保持轻量。Plan 是当前这次创作的可编辑草案，不是知识库、trace、历史记录、多 Agent 编排图或工具调用计划总表。

Plan 只回答三件事：

```text
做什么
怎么拍/怎么剪
worker 怎么执行
```

Plan body 只保留用户可读、可编辑、可执行的信息。

`AgentPlan` 轻量字段：

```text
title
goal
summary
style
scenes
```

`PlanScene` 轻量字段：

```text
id
description
keywords
duration
searchQuery
```

`ExecutionPlan` 也保持薄层：

```text
title
targetDuration
style
scenes
```

`ExecutionPlan.scenes`：

```text
id
description
keywords
searchQuery
duration
```

以下内容不进入 plan body：

```text
understanding
strategy
openIssues
replanHistory
grounding 过多细节
tool requirements
skill selection 结果
agent roles
model reasoning
trace
confidence 细分
```

这些内容分别进入：

```text
AgentRun
TraceEvent
Planner metadata
AgentObservation
SkillRun
ContextUsage
ToolCall
```

计划内容和计划元数据必须分离。

Plan body：

```text
title
goal
summary
style
scenes
```

Plan metadata 放数据库记录，不塞入 plan body：

```text
version
parent_plan_id
trigger_type
planner_mode
planner_model
change_summary
source_run_id
created_at
```

核心边界：

```text
Plan = 最终可编辑草案
Trace = 生成过程记录
```

这意味着用户看到的是简洁方案；为什么生成这个方案、用了哪些上下文、哪个 skill 影响了输出、模型是否 fallback，都进入 Trace / Run / SkillRun / ContextUsage。

### Tool Gateway / MCP 决策

ToolGateway 是统一工具出口。Skill、Planner 和未来 Agent role 不能直接调用 MCP 或外部工具，必须经过 ToolGateway。

第一版 ToolGateway 以项目知识和素材检索为主，MCP 只预留 adapter，不作为主线。

第一版工具重点：

```text
项目知识读取
素材 metadata 检索
运行配置读取
失败诊断读取
历史方案读取
```

暂不做：

```text
动态 MCP server 安装
复杂外部工具市场
用户自定义工具
写操作工具大规模开放
工具编排 DAG
```

第一版工具清单建议：

```text
read_project_knowledge
search_project_knowledge
read_knowledge_document
search_asset_metadata
inspect_asset_providers
read_fixture_library
read_runtime_settings
read_last_failure_diagnostic
read_plan_history
```

`ToolDefinition` 建议字段：

```text
id
name
description
category
input_schema
output_schema
permissions
source_type
status
mcp_server_id
tool_name
timeout_ms
retry_policy
```

第一版权限分三层：

```text
system
project
session
```

第一版大多数工具应是：

```text
scope = project 或 session
mode = read_only
```

每次工具调用都要记录 `ToolCall`：

```text
tool_calls
  id
  run_id
  step_id
  tool_id
  status
  arguments_json
  result_summary
  result_ref
  error_message
  started_at
  finished_at
```

结果很大时，不要把大 payload 塞进 `ToolCall`，应保存为 artifact、observation 或 knowledge document，并在 `ToolCall.result_ref` 中保存引用。

ToolGateway 和 ContextEngine 的边界：

```text
ContextEngine = 组装上下文
ToolGateway = 执行工具调用
```

未来如果需要外部资料，流程应是：

```text
ToolGateway 调 MCP 或外部工具
  -> 结果保存为 KnowledgeDocument / Observation
  -> ContextEngine 再检索和组装
```

不要让 ContextEngine 直接调用 MCP。

MCP 作为 ToolGateway 的后端适配之一预留：

```text
ToolGateway
  -> LocalToolAdapter
  -> MCPToolAdapter
```

### Execution Engine 决策

ExecutionEngine 负责执行已经确认的计划。它是确定性执行层，不是智能大脑。

核心边界：

```text
AgentRuntime = 智能规划 / 修订 / 修复方案
ExecutionEngine = 执行方案 / 生成产物 / 报告失败
```

用户确认 plan 时创建 `AgentJob`，不创建 `AgentRun`：

```text
POST /sessions/{session_id}/confirm
  -> 校验 session.status = plan_ready
  -> 校验没有 active_operation
  -> 读取 current_plan
  -> 创建 AgentJob
  -> session.active_operation_type = job
  -> session.active_operation_id = jobId
  -> session.status = executing
  -> enqueue run_agent_job(jobId)
  -> 返回 session snapshot
```

`AgentJob` 建议字段：

```text
id
session_id
plan_id
job_type
status
progress
current_step
error_message
worker_id
attempt_count
max_attempts
source_run_id
repair_run_id
auto_repair_count
started_at
finished_at
created_at
updated_at
```

`source_run_id` 表示哪个 AgentRun 生成了这个 plan/job；`repair_run_id` 表示这个 job 失败后由哪个 repair run 处理。

Job 和 Run 必须分离：

```text
Run = Agent 智能回合
Job = 视频执行任务
```

Worker 不直接重规划。Worker 只负责结构化失败事实，ExecutionEngine 再根据失败类别决定是否创建 `execution_feedback_replan` run。

搜索类失败可以自动 repair 并自动重跑一次，但只限 query-only repair：

```text
search/query-only failure
  -> 自动创建 execution_feedback_replan run
  -> repair run 只允许改 searchQuery / keywords
  -> repair run 成功后自动创建 replacement job
  -> 最多自动重跑 1 次
```

不自动修复的情况：

```text
缺少 API key
provider 权限失败
FFmpeg/render 失败
数据库/文件系统错误
需要改变整体视频结构
需要改变用户确认过的核心方案
```

这些情况应生成 diagnostic，等待用户处理或确认。

Repair 输出必须标明 `repair_scope`：

```text
query_only
plan_structure
configuration_required
system_error
```

只有：

```text
repair_scope = query_only
```

才允许自动 requeue。

自动 repair 次数不要放 Session，放在 Job 或 Run metadata：

```text
auto_repair_count <= 1
```

未来可独立建 `JobStep`，但第一阶段可以复用现有 step snapshot。长期建议：

```text
job_steps
  id
  job_id
  step_key
  title
  status
  progress
  error_message
  started_at
  finished_at
```

ExecutionEngine 直接依赖 media infrastructure 和 provider adapter，不通过通用 ToolGateway 调 FFmpeg。FFmpeg 是基础设施执行能力，不是 Agent 工具。

### Trace / Observation 决策

Observation 记录业务事实，TraceEvent 记录运行轨迹。

```text
Observation = 对业务有意义的事实记录
TraceEvent = Agent 运行过程中的详细事件
```

Observation 示例：

```text
用户提交了初始 brief
用户确认了 grounding candidates
worker 搜索失败，失败类别是 no_inventory
用户要求把风格改成商务感
```

TraceEvent 示例：

```text
ContextEngine 检索到 3 条知识
SkillEngine 选择 product_intro_video
PlannerRuntime 使用 gpt-4o-mini
ToolGateway 调用了 search_project_knowledge
Planner fallback 到 deterministic
```

第一版 Trace 只做后端记录，不做前端 Trace 面板。

第一版记录：

```text
context usage
skill selection
planner metadata
tool call summary
diagnostic
repair/requeue decision
role / agent_name
```

第一版不记录：

```text
assistant_delta
heartbeat
每个 token
完整 prompt
完整 LLM response
敏感 API key
超大工具返回结果
```

`TraceEvent` 建议字段：

```text
id
run_id
step_id
session_id
event_type
role
agent_name
summary
payload_json
created_at
```

第一版关键结构事件：

```text
run_started
step_started
context_ready
skill_selected
planner_completed
planner_fallback
plan_ready
diagnostic_created
repair_scope_decided
auto_requeue_created
run_succeeded
run_failed
```

Redis Stream 负责短期实时事件，TraceEvent 负责长期关键事件：

```text
Redis Stream = 短期实时事件
TraceEvent = 长期关键事件
```

Trace 不参与业务状态判断，不作为状态来源。业务状态来自 Session、Run、Step、Job。

自动 repair/requeue 决策必须记录：

```text
diagnostic_created
repair_scope_decided
auto_requeue_created
```

这样未来可以解释系统为什么自动重跑了一次。

### Knowledge / Project Knowledge 决策

Knowledge 模块负责管理项目级资料的导入、存储、切分、索引和状态。它是 RAG 的数据来源，但不是 RAG 本身。

```text
Knowledge = 平时管理可检索资料
ContextEngine = run 时检索和组装上下文
```

第一版做一个简单 `/knowledge` 页面，支持手动粘贴项目资料。

第一版 UI：

```text
资料列表
新增资料
编辑标题
粘贴 Markdown / 纯文本
保存
显示索引状态
删除 / 禁用资料（可选）
```

第一版不做：

```text
PDF 上传
docx 上传
网页 URL 抓取
文件夹同步
MCP 文件读取
复杂标签系统
多用户权限
高级检索 UI
```

第一版表单：

```text
title
content
tags 可选
```

保存后：

```text
create KnowledgeSource
create KnowledgeDocument
chunk content
index chunks
status = ready
```

如果 embedding 暂时没接：

```text
status = ready
search_mode = keyword
```

`/knowledge` 页面定位：

> 给当前视频项目添加产品/品牌资料，让 Agent 生成视频方案时能参考。

推荐导航文案使用：

```text
知识库
```

不要在用户界面叫 RAG。

Knowledge 状态：

```text
pending
indexing
ready
failed
disabled
```

第一版 chunk 策略：

```text
按段落切
每 chunk 约 500-1000 中文字
保留标题和 tags 到 metadata
```

不要自动把所有聊天内容写入知识库。短文本继续作为 session context；只有用户明确选择“保存为资料”时才进入 Knowledge。

### Multi-Agent 预留决策

当前阶段不实现多 Agent 调度，只在 Run / Step / Trace / Skill / ToolCall 层预留。

未来可能的 Agent roles：

```text
SupervisorAgent
ResearchAgent
PlannerAgent
AssetAgent
DirectorAgent
RenderAgent
CriticAgent
```

当前阶段预留字段：

```text
AgentStep.role
AgentStep.agent_name
SkillDefinition.default_role
SkillDefinition.supported_roles
TraceEvent.role
TraceEvent.agent_name
ToolCall.run_id
ToolCall.step_id
```

第一版所有步骤都可以是：

```text
role = planner
agent_name = DefaultPlannerAgent
```

未来逐步演进：

```text
Phase 1: 单 AgentRuntime，所有 step role = planner
Phase 2: Trace 中展示 role / agent_name，但仍单 Agent 执行
Phase 3: ResearchAgent 独立负责 retrieve_context
Phase 4: AssetAgent 独立负责 search query repair
Phase 5: CriticAgent 独立负责 plan review
Phase 6: SupervisorAgent 编排多个 role
```

多 Agent 的最小单位是 Step，不是 Session：

```text
Session
  -> AgentRun
      -> AgentStep(role=researcher)
      -> AgentStep(role=planner)
      -> AgentStep(role=critic)
```

Skill 是能力包，Agent 是角色，不要混用：

```text
Agent = 角色/执行者
Skill = 能力包/策略包
```

一个 Agent 可以使用多个 Skill，一个 Skill 也可以被不同 Agent 使用。

当前阶段不要做：

```text
Supervisor graph
agent-to-agent chat
multi-agent message bus
parallel step DAG
agent marketplace
role-based autonomous routing
critic review loop
```

## 主工作流

完整视频生成主线：

```text
1. 用户输入 brief
   ↓
2. Session Manager 记录消息
   ↓
3. AgentRuntime 创建 AgentRun
   ↓
4. ContextEngine 检索上下文
   - 产品资料
   - 品牌规范
   - 历史 plan
   - 用户偏好
   - 素材库 metadata
   ↓
5. SkillEngine 选择 skill
   - builtin.product_intro_video
   - builtin.asset_search_repair
   - builtin.execution_feedback_replan
   ↓
6. PlannerRuntime 生成 AgentPlan + ExecutionPlan
   ↓
7. TraceRecorder 记录 context usage / skill selection / planner decision
   ↓
8. 用户确认或修改 plan
   ↓
9. ExecutionEngine 创建 Job
   ↓
10. Worker 执行
    - search assets
    - optional tool calls through ToolGateway
    - download assets
    - render video
   ↓
11. 成功则写 video artifact，失败则写 diagnostic
   ↓
12. 失败反馈进入 repair/replan workflow
```

第一阶段实现时，`ContextEngine` 可以返回空上下文，`SkillEngine` 可以默认选择 `builtin.product_intro_video`，`ToolGateway` 可以对未注册工具返回 `skipped`。关键是入口、数据形状和 trace 位置要先成立。

## 失败修复工作流

执行失败不应该由 worker 自己自由修复。Worker 的职责是把失败事实结构化，然后交回 AgentRuntime。

推荐流程：

```text
Worker failure
  ↓
ExecutionEngine normalizes diagnostic payload
  ↓
TraceRecorder records failure event
  ↓
ContextEngine adds failure context
  ↓
SkillEngine selects repair skill
  ↓
PlannerRuntime creates repaired plan version
  ↓
ExecutionEngine creates replacement job
```

这样可以保持两个原则：

- Worker 负责事实和执行。
- Planner/Skill 负责策略和修复方案。

## RAG 工作流

RAG 作为独立知识库工作流，不直接嵌在 planner 中。

```text
Add source / Upload document
  ↓
Parse document
  ↓
Chunk document
  ↓
Embed chunks
  ↓
Store chunks
  ↓
Retrieve during planning
  ↓
Record context usage
```

第一阶段只定义边界和接口，不接真实 vector store。

后续 RAG 相关对象：

- `KnowledgeSource`
- `KnowledgeDocument`
- `KnowledgeChunk`
- `ContextUsage`

最重要的是 `ContextUsage`：它记录某次 plan 使用了哪些 chunk，避免 RAG 成为不可解释的黑盒。

## Skill 工作流

Skill 应该是可版本化能力包，不是简单 prompt 文件夹。

```text
Register skill
  ↓
Define trigger conditions
  ↓
Define input/output schema
  ↓
Define prompts and handler
  ↓
SkillEngine selects skill
  ↓
Run skill
  ↓
Record SkillRun
```

初始 built-in skills：

- `builtin.product_intro_video`
- `builtin.asset_search_repair`
- `builtin.execution_feedback_replan`

后续可以增加：

- `builtin.brand_story_video`
- `builtin.social_caption_generation`
- `builtin.competitor_research`
- `builtin.director_review`

## Tool / MCP 工作流

MCP 不应该散落在业务 service 里调用，必须统一经过 `ToolGateway`。

```text
Register tool server
  ↓
Expose tool definitions
  ↓
Permission check
  ↓
ToolGateway.call_tool(...)
  ↓
Normalize result
  ↓
Record ToolCall
```

第一阶段只定义 `ToolGateway` 契约，不接真实 MCP client。

后续 MCP 相关对象：

- `ToolServer`
- `ToolDefinition`
- `ToolPermission`
- `ToolCall`

## 多 Agent 预留

本阶段不实现多 Agent 调度，但架构应允许未来演进。

未来可能拆分的 Agent roles：

- `SupervisorAgent`：决定一次 run 的步骤和角色分派。
- `ResearchAgent`：负责 RAG 检索和上下文整理。
- `PlannerAgent`：负责视频结构和场景计划。
- `AssetAgent`：负责素材搜索策略和 provider failure 修复。
- `DirectorAgent`：负责镜头连贯性、字幕和节奏审查。
- `RenderAgent`：负责渲染参数和产物检查。
- `CriticAgent`：负责 plan/output QA 和重规划建议。

当前阶段只预留以下概念：

- `AgentRun`
- `AgentStep`
- `AgentDecision`
- `TraceEvent.actor`
- `TraceEvent.role`

当前单 Agent 工作流可以被表示为：

```text
AgentRun
  Step 1: context
  Step 2: skill_selection
  Step 3: planning
  Step 4: execution_enqueue
```

未来多 Agent 工作流可以扩展为：

```text
AgentRun
  SupervisorAgent
    -> ResearchAgent
    -> PlannerAgent
    -> CriticAgent
    -> AssetAgent
    -> RenderAgent
```

避免现在做的内容：

- 不做 supervisor graph。
- 不做 agent-to-agent chat。
- 不做 multi-agent message bus。
- 不做 role-based autonomous routing。

## 推荐分阶段

### Phase 1: Agent Runtime Boundary

目标：不新增复杂能力，只建立架构边界和兼容模块。

内容：

- 增加 `backend/app/`、`backend/runtime/`、`backend/domain/`、`backend/infrastructure/`、`backend/workers/`。
- 增加 `AgentRuntime` facade。
- 增加 no-op `ContextEngine`。
- 增加 default `SkillEngine`。
- 增加 skipped `ToolGateway`。
- 增加 no-op `TraceRecorder`。
- API import 迁到 application boundary。
- 保持现有行为不变。

### Phase 2: Trace And Run Model

目标：让当前单 Agent 运行过程可解释、可观察。

内容：

- 设计 `AgentRun`、`AgentStep`、`AgentDecision`。
- 增加 `TraceEvent.actor` / `role` 预留字段。
- 记录 context、skill、planner、execution 的关键决策。
- 前端可以先不做完整 trace UI，但后端读模型要成立。

### Phase 3: RAG Foundation

目标：把产品资料、品牌资料、历史方案作为上下文接入 planning。

内容：

- 增加 knowledge source/document/chunk。
- 增加 embedding 和 vector store adapter。
- `ContextEngine` 从 no-op 变成 retrieval-backed。
- 记录 `ContextUsage`。

### Phase 4: Skill Foundation

目标：把 planning 和 repair 能力变成可注册、可版本化 skill。

内容：

- 增加 built-in skill package。
- 增加 `SkillDefinition`。
- 增加 `SkillRun`。
- 让 `SkillEngine` 从默认选择变成规则选择。

### Phase 5: MCP Foundation

目标：通过 ToolGateway 统一接入外部工具和 MCP server。

内容：

- 增加 MCP client adapter。
- 增加 tool server registry。
- 增加 permission check。
- 持久化 tool calls。

### Phase 6: Multi-Agent Evolution

目标：在 AgentRun/Trace/Skill/Tool 都稳定后，再引入多 Agent。

内容：

- 增加 agent role registry。
- 增加 supervisor planning。
- 增加 agent handoff 和 review。
- 只在明确需要时引入多 Agent 调度。

## 第一阶段验收标准

Phase 1 完成时，应满足：

- 所有当前 API 行为不变。
- 当前 planner tests 继续通过。
- 当前 job execution tests 继续通过。
- 新增架构边界测试能证明 package 和 import 方向成立。
- `ContextEngine`、`SkillEngine`、`ToolGateway`、`TraceRecorder` 可 import 且无副作用。
- README 或设计文档清楚说明 RAG、Skill、MCP、多 Agent 的未来落点。
- 没有真实引入 vector DB、MCP client 或多 Agent scheduler。

## 风险和约束

主要风险：

- 过早做通用平台，拖慢当前视频生成主线。
- 只改目录不改边界，导致 `services/` 逻辑继续膨胀。
- RAG、Skill、MCP 分别散落接入，后续难以审计和调试。
- 多 Agent 概念过早进入执行链，导致任务状态和失败处理复杂化。

控制策略：

- 第一阶段只做兼容边界和文档化架构。
- 所有新能力先通过 runtime facade 接入。
- 先 trace 单 Agent，再考虑多 Agent。
- Worker 只产生结构化事实，不自行做策略性修复。

## 自检

- 本设计聚焦功能边界、工作流和多 Agent 预留，没有进入代码实现。
- RAG、Skill、MCP 的职责边界明确且互不重叠。
- 多 Agent 被设计为未来演进方向，本阶段只预留 run/step/role/actor 概念。
- Phase 1 范围足够小，可以由一份实施计划落地。

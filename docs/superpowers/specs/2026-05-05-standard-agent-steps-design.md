# ClipForge Standard Agent Steps Design

## Background

ClipForge 现在已经有产品化的三页结构：Dashboard、方案沟通页、任务管理页。前端已经希望展示“后端正在做什么、每一步进度如何、每一步产出了什么结果”，但当前后端只提供了较薄的一组字段：

- `status`
- `progress`
- `currentStep`
- `events`
- `plan`
- `clips`
- `videoUrl`

这些字段能支撑基础状态展示，但不足以支撑产品页里稳定的步骤结果卡片。现在的方案沟通页仍有不少步骤内容由前端静态拼装，任务详情也主要展示事件列表，而不是结构化的每步产出。

下一阶段需要建立一套固定标准步骤协议，让后端把真实执行过程聚合成稳定的 `steps[]`，前端直接消费这套结构展示状态、进度和结果。

## Goals

1. 定义一套覆盖完整主流程的固定标准步骤。
2. 让后端在会话和任务响应里返回结构化 `steps[]`。
3. 让前端展示真实步骤状态和结果，不再硬编码核心步骤内容。
4. 保留 `events[]` 作为时间线和排障信息。
5. 让方案沟通页、任务管理页、任务详情弹窗使用同一套步骤语义。

## Non-Goals

- 本阶段不重新设计前端页面视觉方向。
- 本阶段不把步骤改成后端任意动态返回。
- 本阶段不引入新的复杂工作流引擎。
- 本阶段不实现多人协作、权限或审计体系。
- 本阶段不要求所有 AI 产出都是真模型生成；可以先用现有计划生成逻辑和 fallback 结果填充结构。

## Chosen Direction

采用 **固定标准步骤 + 事件时间线** 的设计。

后端围绕固定步骤 ID 聚合当前状态，每个步骤都有稳定字段：

- 步骤身份：`id`、`title`、`description`
- 执行状态：`status`、`progress`
- 用户可读摘要：`summary`
- 结构化结果：`result`
- 失败信息：`error`
- 时间信息：`startedAt`、`finishedAt`

`steps[]` 是产品界面消费的主数据，`events[]` 是任务详情和调试使用的过程日志。

## Standard Steps

标准步骤固定为 8 个，覆盖从用户输入到视频结果的完整流程。

| Step ID | Title | Page Usage | Responsibility |
| --- | --- | --- | --- |
| `understand_request` | 理解原始需求 | 方案沟通页 | 读取用户原始 prompt，提炼主题、受众、用途和初步意图。 |
| `extract_requirements` | 提炼目标与限制 | 方案沟通页 | 提炼时长、格式、风格、素材限制、输出目标等约束。 |
| `generate_options` | 生成方案方向 | 方案沟通页 | 生成多个可选方向，供用户选择主方向。 |
| `finalize_plan` | 生成最终执行方案 | 方案沟通页 | 根据用户选择生成最终方案、镜头拆分和可确认计划。 |
| `create_task` | 创建执行任务 | 任务页 / 详情弹窗 | 用户确认方案后创建后端 job，并返回队列信息。 |
| `search_assets` | 搜索素材 | 任务页 / 详情弹窗 | 根据最终方案搜索候选素材并记录搜索结果。 |
| `prepare_assets` | 准备素材 | 任务页 / 详情弹窗 | 下载、裁剪、整理素材，形成渲染输入。 |
| `render_video` | 渲染视频 | 任务页 / 详情弹窗 | 调用渲染流程，生成视频产物或失败原因。 |

## Step Status

步骤状态固定为：

```ts
type AgentStepStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped'
```

语义如下：

- `pending`: 步骤尚未开始。
- `running`: 步骤正在执行。
- `succeeded`: 步骤已完成，并且可以展示结果。
- `failed`: 步骤执行失败，`error` 必须有值。
- `skipped`: 步骤被明确跳过，例如用户取消或后端判定不需要执行。

## API Data Model

### Step ID

前后端共享同一组步骤 ID。

```ts
type AgentStepId =
  | 'understand_request'
  | 'extract_requirements'
  | 'generate_options'
  | 'finalize_plan'
  | 'create_task'
  | 'search_assets'
  | 'prepare_assets'
  | 'render_video'
```

### Step Error

```ts
interface AgentStepError {
  message: string
  retryable: boolean
  retryableStep?: AgentStepId
}
```

### Step Snapshot

```ts
interface AgentStep {
  id: AgentStepId
  title: string
  description: string
  status: AgentStepStatus
  progress: number
  summary: string
  result: Record<string, unknown> | null
  error: AgentStepError | null
  startedAt: string | null
  finishedAt: string | null
}
```

Rules:

- `progress` 取值范围为 `0..100`。
- `status === 'failed'` 时 `error` 必须有值。
- `status === 'succeeded'` 时 `summary` 应有可读内容。
- `result` 只存结构化数据，不存长篇展示文案。
- 没有真实数据时，后端返回 `pending` 或空 `result`，前端不自行伪造业务结果。

## Result Payloads

每个步骤的 `result` 使用固定结构。第一版保持轻量，避免一次性引入复杂嵌套。

### `understand_request.result`

```ts
interface UnderstandRequestResult {
  originalPrompt: string
  topic: string
  audience: string
  useCase: string
  intentSummary: string
}
```

### `extract_requirements.result`

```ts
interface ExtractRequirementsResult {
  targetDuration: number
  aspectRatio: string
  style: string
  tone: string
  constraints: string[]
}
```

### `generate_options.result`

```ts
interface GenerateOptionsResult {
  options: Array<{
    id: string
    name: string
    summary: string
    tags: string[]
    recommended: boolean
  }>
  selectedOptionId: string | null
}
```

### `finalize_plan.result`

```ts
interface FinalizePlanResult {
  title: string
  style: string
  targetDuration: number
  selectedOptionId: string | null
  scenes: Array<{
    id: number
    description: string
    keywords: string[]
    duration: number
    searchQuery: string
  }>
}
```

### `create_task.result`

```ts
interface CreateTaskResult {
  jobId: string
  sessionId: string
  queuedAt: string
  queueName: string
}
```

### `search_assets.result`

```ts
interface SearchAssetsResult {
  queries: string[]
  candidateCount: number
  selectedCount: number
}
```

### `prepare_assets.result`

```ts
interface PrepareAssetsResult {
  clips: Array<{
    sceneId: number
    sourceUrl: string
    publicUrl: string
    caption: string
    trimStart: number
    trimDuration: number
  }>
}
```

### `render_video.result`

```ts
interface RenderVideoResult {
  videoUrl: string
  format: string
  duration: number
  artifactId: string | null
}
```

## Response Model Changes

### Agent Session

`AgentSession` 增加：

```ts
steps: AgentStep[]
```

方案沟通页主要读取前四步：

- `understand_request`
- `extract_requirements`
- `generate_options`
- `finalize_plan`

### Agent Task Summary

`AgentTaskSummary` 增加：

```ts
currentStepId: AgentStepId | null
```

任务列表仍保持轻量，不返回完整 `steps[]`。

### Agent Task Detail

`AgentTaskDetail` 增加：

```ts
steps: AgentStep[]
```

任务详情弹窗展示完整 8 步，并继续展示 `events[]` 时间线。

### Dashboard

Dashboard 不需要完整 `steps[]`。它继续使用任务摘要、计数和最近任务列表，并可以读取 `currentStepId` 做更稳定的状态文案。

## Backend Architecture

新增一个步骤快照服务：

```text
backend/services/agent_step_snapshot_service.py
```

职责：

1. 定义标准步骤元数据。
2. 从 session、plan、job、events、artifacts 里聚合 `steps[]`。
3. 根据现有状态计算每步 `status` 和 `progress`。
4. 根据现有结构生成每步 `result`。
5. 根据错误信息填充失败步骤的 `error`。

建议服务方法：

```python
class AgentStepSnapshotService:
    def build_session_steps(self, session_record, message_rows, plan_row, event_rows) -> list[AgentStep]:
        ...

    def build_task_steps(self, session_record, job_record, plan_row, artifact_rows, event_rows) -> list[AgentStep]:
        ...
```

## Status Aggregation Rules

第一版聚合规则应保守、可解释：

1. 没有 session 时所有步骤为 `pending`。
2. 有用户消息后，`understand_request` 为 `succeeded`。
3. 有 plan 后，`extract_requirements`、`generate_options`、`finalize_plan` 为 `succeeded`。
4. session `status === 'planning'` 时，前四步中尚未完成的当前步骤为 `running`。
5. 有 job 后，`create_task` 为 `succeeded`。
6. job `status === 'queued'` 时，`search_assets` 为 `pending`。
7. 搜索事件存在时，`search_assets` 从 `running` 或 `succeeded` 推断。
8. clip artifact 存在时，`prepare_assets` 为 `succeeded`。
9. video artifact 或 `videoUrl` 存在时，`render_video` 为 `succeeded`。
10. job 或 session 失败时，使用 `retryableStep` 或最新失败事件映射到具体 step，其余后续步骤保持 `pending`。

这些规则不要求改变现有底层执行流程，只要求后端在读模型里补充稳定快照。

## Event Relationship

`events[]` 继续记录细粒度过程，例如：

- `job_queued`
- `search_started`
- `asset_found`
- `clip_downloaded`
- `render_started`
- `render_completed`
- `job_failed`

事件可以带 `step` 字段，但前端产品展示不直接依赖事件推断步骤。事件主要用于：

- 任务详情时间线。
- 失败排障。
- 后续日志和审计。

## Frontend Consumption

### Workspace Page

方案沟通页改为读取 `session.steps` 前四步。

页面规则：

- 步骤标题、状态、进度来自 `AgentStep`。
- 步骤完成后的结果来自 `AgentStep.result`。
- 方案方向区来自 `generate_options.result.options`。
- 最终方案区来自 `finalize_plan.result`。
- 前端保留选中态交互，但最终确认必须以服务端返回结果为准。

### Task Manager

任务列表读取：

- `status`
- `progress`
- `currentStep`
- `currentStepId`

任务详情弹窗读取：

- `steps[]`
- `events[]`
- `clips`
- `videoUrl`
- `error`

详情弹窗优先展示 `steps[]`，事件时间线作为次级信息。

## Error Handling

当某一步失败：

1. 当前步骤状态为 `failed`。
2. 当前步骤 `error.message` 显示失败原因。
3. `error.retryable` 标记是否允许重试。
4. `error.retryableStep` 指向可重试步骤。
5. 后续未执行步骤保持 `pending`。
6. 任务详情仍展示原始事件时间线，便于查看失败上下文。

如果后端无法确定具体失败步骤，默认映射到：

- 规划阶段失败：`finalize_plan`
- 搜索阶段失败：`search_assets`
- 下载或素材处理失败：`prepare_assets`
- 渲染失败：`render_video`

## Migration Strategy

分阶段实现：

1. 后端模型增加 `AgentStep`、`AgentStepError` 和 `currentStepId`。
2. 后端读取服务返回 `steps[]`，先基于现有 plan/job/events/artifacts 聚合。
3. 前端类型同步新增 `steps[]`。
4. 方案沟通页移除本地静态步骤定义，改为渲染 `session.steps`。
5. 任务详情弹窗改为优先展示 `task.steps`。
6. 保留旧字段 `status`、`progress`、`currentStep`，避免破坏 Dashboard 和已有组件。

## Verification

实现完成后至少验证：

1. 创建新会话后，`AgentSession.steps` 返回完整 8 步。
2. 有用户 prompt 时，`understand_request` 有真实 `originalPrompt`。
3. 有 plan 时，前四步包含可展示 `result`。
4. 确认方案创建任务后，任务详情返回完整 8 步。
5. 任务失败时，失败 step 有 `error`，后续步骤保持 `pending`。
6. 方案沟通页不再使用本地静态 A/B/C 方案作为主数据。
7. 任务详情弹窗优先展示 `steps[]`，事件时间线仍可查看。
8. 现有 Dashboard、任务列表、基础 API 测试不回退。

## Open Implementation Notes

- 这份设计不要求立刻改写底层执行服务，只要求读模型提供稳定步骤快照。
- 第一版可以从现有 fallback plan 中生成 `generate_options` 和 `finalize_plan` 的结构化结果。
- 后续若引入更强的 AI 规划服务，也必须输出到相同标准步骤协议。

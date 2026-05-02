# ClipForge Agent Workbench Design

## 背景

ClipForge 当前同时存在前端人工剪辑界面和初步 AI 剪辑代码，但两条链路没有真正打通。前端请求 `/api/ai/*`，后端实际运行在 FastAPI 中，缺少 Next 代理或 API route；后端模型存在导入错误，任务状态、素材路径、WebSocket 消息格式也不一致。新的目标是把产品明确收束为“对话式智能剪辑 Agent”，删除用户可见的人工剪辑页面，让用户通过对话提出目标、修改方案，并在确认后由 Agent 搜索素材、下载和渲染。

## 产品方向

第一版采用单页 Agent 工作台。

用户通过聊天输入剪辑目标，例如“做一个 30 秒科技产品发布短视频，节奏快一点”。Agent 生成结构化剪辑方案，用户可以继续用自然语言修改。只有当用户点击“确认并开始”后，系统才开始搜索公开视频素材、下载素材并渲染 MP4。

本阶段选择真实素材搜索下载路线，继续使用 `yt-dlp` 接入公开视频搜索/下载。由于真实素材链路天然不稳定，搜索失败、下载失败、素材缺失和渲染失败都必须成为显式状态，而不是简单抛出异常。

## 整体架构

前端 Next.js 只负责一个 Agent 工作台：对话输入、消息流、方案确认、任务进度、结果预览和下载。不再显示素材库、时间线、检查器、手动预览条和手动渲染按钮。

后端 FastAPI 负责智能剪辑编排：

```text
用户需求 -> Agent 生成剪辑计划 -> 用户确认 -> 搜索/下载素材 -> FFmpeg 渲染 -> 输出结果
```

前端所有 Agent API 统一走 `src/lib/agentApi.ts`。Next 配置添加 rewrite，把 `/api/agent/*` 代理到 FastAPI 的 `http://127.0.0.1:8000/api/agent/*`，把 `/ws/agent/*` 代理到后端 WebSocket。第一版如果 WebSocket 代理复杂，可以先使用轮询，但接口命名仍按 Agent 语义保留。

后端从零散全局 `tasks` 字典升级为轻量会话编排服务。第一版仍使用内存存储，避免引入数据库，但数据模型按后续持久化设计。

## Agent 状态机

会话状态包括：

- `idle`：等待用户输入需求。
- `planning`：Agent 正在分析目标并生成剪辑计划。
- `plan_ready`：计划已生成，等待用户确认或继续修改。
- `searching`：开始搜索公开视频素材。
- `downloading`：下载每个场景对应素材。
- `rendering`：FFmpeg 合成成片。
- `done`：展示视频预览、下载入口和本轮方案。
- `failed`：展示失败原因，允许重试当前步骤或回到方案修改。

第一版支持“确认前多轮修改，确认后跑完整任务”。渲染中途暂停和取消不进入本阶段范围。

## 前端页面设计

首页只渲染新的 `AgentWorkspace`。

顶部 Header 显示 `ClipForge Agent`、当前任务状态和后端连接状态。移除“手动剪辑 / AI 剪辑”模式切换，移除旧“渲染视频”按钮。

主区域为两栏：

左侧是对话区，显示用户消息、Agent 回复、错误提示和底部输入框。用户可以输入新需求，也可以在 `plan_ready` 阶段继续要求修改方案。

右侧是任务面板：

- “剪辑方案”：显示标题、风格、预计时长、场景列表、关键词和素材策略。
- “执行进度”：显示规划、搜索、下载、渲染、完成等步骤。
- “结果预览”：完成后显示视频播放器和下载按钮。

建议组件边界：

- `src/components/agent/AgentWorkspace.tsx`：页面总入口。
- `src/components/agent/AgentChat.tsx`：消息列表和输入框。
- `src/components/agent/PlanPanel.tsx`：结构化剪辑方案。
- `src/components/agent/ProgressPanel.tsx`：任务状态。
- `src/components/agent/ResultPanel.tsx`：视频预览和下载。
- `src/stores/useAgentStore.ts`：统一管理会话、消息、计划、状态和结果。
- `src/lib/agentApi.ts`：统一封装 HTTP、轮询和后续 WebSocket。

旧人工剪辑组件第一步不删除文件，只从首页下线，降低重构风险。后续 Agent 链路稳定后再删除 `timeline`、`materials`、`inspector`、`preview` 相关组件和旧 store。

## 后端 API 设计

新接口统一走 `/api/agent`。

### `POST /api/agent/sessions`

创建会话，可选带第一条用户需求。若带需求，后端进入 `planning`，生成计划后返回 `plan_ready` 会话。

### `POST /api/agent/sessions/{session_id}/messages`

追加用户消息。若当前未执行任务，Agent 基于已有计划和新消息重新生成或修改计划，返回更新后的 session。

### `POST /api/agent/sessions/{session_id}/confirm`

用户确认计划后，后台启动搜索、下载和渲染任务，立即返回当前 session。

### `GET /api/agent/sessions/{session_id}`

获取当前会话状态、消息、计划、clips、错误和结果 URL。前端第一版主要通过该接口轮询。

### `WS /ws/agent/{session_id}`

推送进度事件。第一版可以先保留服务端接口和前端扩展点，优先保证轮询稳定。

## 后端数据模型

核心模型：

- `AgentMessage`：`id, role, content, createdAt`。
- `PlanScene`：`id, description, keywords, duration, searchQuery`。
- `EditPlan`：`title, targetDuration, style, scenes`。
- `ClipInfo`：`sceneId, sourceUrl, localPath, publicUrl, startTime, duration`。
- `AgentSession`：`id, status, messages, plan, clips, videoUrl, error, retryableStep`。

GPT 输出必须要求 JSON，并用 Pydantic 校验为 `EditPlan`。不要再用自然语言逐行 split 来解析场景。

搜索下载服务返回 `ClipInfo` 模型列表，不在 dict 和 Pydantic 模型之间混用。

渲染服务使用 `localPath` 作为 FFmpeg 输入，前端只使用 `publicUrl` 和 `videoUrl`。所有下载、输出目录以 backend 目录为基准解析，避免 `downloads` 和 `backend/downloads` 两套路径。

## 错误处理

OpenAI API key 缺失时，后端返回明确错误，会话进入 `failed`，错误信息说明缺少配置。

模型返回无效 JSON 时，会话进入 `failed`，保留原始错误摘要，不让前端无限等待。

搜索失败时按场景记录失败原因。如果部分场景成功，可以继续渲染成功片段，并在 UI 中标记缺失场景。

下载失败时尝试下一个搜索结果；全部失败才让该场景失败。

渲染失败时保留已下载素材和计划，允许用户重试渲染。

任务失败统一进入 `failed`，并填充 `error` 和 `retryableStep`，前端据此显示“重试当前步骤”或“修改方案”。

## 测试策略

先用 Python `unittest` 覆盖后端：

- 后端模块可导入，避免当前 `Dict` 未导入导致启动失败。
- 创建会话并生成计划的响应结构。
- 追加用户消息后会话仍保持 `plan_ready`。
- 确认计划后状态进入执行流程。
- 下载结果转换为 `ClipInfo`，包含本地路径和公开 URL。
- 渲染服务使用本地路径而不是公开 URL。

前端第一阶段使用 `npx tsc --noEmit` 作为类型护栏，并为 `agentApi` 和 store 的纯逻辑保留可测试边界。若要完整 UI 测试，再引入 Vitest 和 React Testing Library。

实现 bugfix 时先写能复现当前问题的失败测试，再修代码。

## 迁移策略

新增 `.gitignore`，忽略 `.next`、`node_modules`、`.venv`、`tsconfig.tsbuildinfo`、下载产物和输出产物，避免构建缓存污染 diff。

首页改为只引用 `AgentWorkspace`。旧人工剪辑文件暂时保留但不再作为用户入口。

`/api/ai` 不继续扩展。新代码统一使用 `/api/agent`。如果发现旧前端调用残留，应迁移到 `agentApi`，而不是给 `/api/ai` 继续打补丁。

README 更新为 Agent 工作台启动方式：前端 `npm run dev`，后端 `uvicorn backend.main:app --reload` 或等效命令，并说明需要配置 `OPENAI_API_KEY` 和本机 FFmpeg。

## 非目标

本阶段不实现人工时间线编辑、多轨道编辑、转场特效、音频混音、任务取消、数据库持久化和用户账号系统。

本阶段不保证 YouTube 搜索下载在所有网络环境下稳定成功，但必须让失败以可理解的状态返回给用户。

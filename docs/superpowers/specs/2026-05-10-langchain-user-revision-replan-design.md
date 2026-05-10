## LangChain User Revision Replan Design

Date: 2026-05-10

## Context

ClipForge `master` 当前已经具备一条可运行的 model-driven planning 主链：

1. `planner_runtime.py` 默认返回 `LangChainPlannerRuntime`
2. initial planning 已由 LangChain 生成正式 `AgentPlan + ExecutionPlan`
3. `planner_graph.py`、`PlannerOrchestrator`、`AgentSessionService` 已打通 planner persistence、observation persistence 和 immutable plan versioning
4. grounding confirmation、user revision、execution feedback 三条 replan 链路已经存在，但目前都仍由 deterministic runtime 承担

其中，`user revision replan` 的 orchestration 路径已经成立：

- `AgentSessionService.add_user_message(...)` 会在已有 plan 的情况下走 revision replan
- `PlannerOrchestrator.persist_user_revision_replan(...)` 会持久化 observation 和新的 plan version
- `planner_graph.py` 已提供 `run_user_revision_replan(...)`

但当前 `backend/services/planner_runtime_langchain.py` 中的 `replan_after_user_revision(...)` 仍然只是直接委托给 deterministic runtime。

这意味着系统虽然已经支持：

- 用户在 `/workspace` 中继续发送修改意见
- 后端产生新的 immutable plan version

但“用户 revision 如何被理解并转成新的 plan”这一层，仍然不是真正的模型驱动。

## Problem

当前 revision path 的主要问题不是没有版本化，也不是没有 orchestration，而是：

1. user revision 的 planning intelligence 仍然停留在 deterministic 规则层
2. 当前 revision 只能对少量固定信号做启发式映射，难以承接更自然的产品修改表达
3. 如果直接让模型在 revision 阶段重吐完整 `AgentPlan + ExecutionPlan`，又会明显放大风险，容易破坏当前已稳定的 execution contract

所以这一阶段真正要解决的问题是：

> 让 `user revision replan` 变成真实的 LangChain structured replanning，同时保持当前 execution 面和 session contract 稳定。

## Goal

这一阶段的目标是：

> 把 `LangChainPlannerRuntime.replan_after_user_revision(...)` 升级为真正的模型驱动 revision runtime，并在失败时回退 deterministic revision replan。

这一阶段要做到：

1. `user revision replan` 不再直接委托 deterministic runtime
2. 模型根据 `current_agent/current_execution + revision_feedback` 输出结构化 revision patch
3. 后端将 patch merge 到当前 plan 的深拷贝上，而不是让模型自由重建 scene 结构
4. LangChain revision replan 失败时，自动回退到 deterministic revision replan
5. 外部 API contract 和 `/workspace` 的消息修改交互保持稳定

## Non-Goals

这一阶段明确不做：

- 不把 grounding replan 改成模型驱动
- 不把 execution feedback replan 改成模型驱动
- 不改 `OpenAIPlannerRuntime` 的 `NotImplemented` 状态
- 不改 `/api/agent/sessions/{id}/messages` 的外部 contract
- 不新增前端 UI 字段或新的恢复流程
- 不允许 revision replan 改变 scene 数量、scene id、scene duration 或 `ExecutionPlan.targetDuration`
- 不允许 revision replan 自动把整个 plan 改写成与原结构无关的新方案

这一阶段只解决：

> “用户说要修改方案时，planner 是否能真正用模型理解这些修改，并稳稳产出下一版计划。”

## Approaches Considered

### Approach A: Hybrid Revision Runtime

做法：

- 新增 revision 专用 structured output contract
- 模型只输出允许修改的 patch 字段
- 后端将 patch merge 回当前 `AgentPlan + ExecutionPlan`
- 若 LangChain 失败，则回退 deterministic revision replan

优点：

- 变化边界最稳
- 最符合当前 “保守重写” 的用户约束
- 能真正让 revision planning 变成模型驱动，而不是只做高层分类
- 不会冲击现有 scene topology 与 execution contract

缺点：

- 需要单独维护一套 revision structured contract
- merge/validation 逻辑会比 initial planning 多一层

这是推荐方案。

### Approach B: Full Contract Regeneration With Guard Rails

做法：

- 让模型重新输出完整 `AgentPlan + ExecutionPlan`
- 后端再校验 scene 数量、id、duration 和 targetDuration 是否与旧 plan 一致

优点：

- 形式上与 initial planning 更统一
- runtime 表面实现更直接

缺点：

- 模型自由度过高
- 后验修补和回退概率更高
- 稳定性明显弱于 patch 模式

这一阶段不推荐。

### Approach C: Patch Intent + Deterministic Projection

做法：

- 模型只输出高层 revision intent
- 后端再用 deterministic 规则把 intent 投影为具体 plan 修改

优点：

- 可控性最强
- 测试最简单

缺点：

- 模型价值偏弱
- 很容易重新退回 “规则驱动为主、模型做分类” 的中间状态

这一阶段不推荐作为主线。

## Recommended Direction

采用 **Approach A: Hybrid Revision Runtime**。

核心原则：

> initial planning 输出完整正式 contract；revision planning 只输出合法 patch；后端负责安全 merge 和 fallback。

这样可以在不破坏现有 session orchestration、plan persistence、execution contract 的前提下，让 user revision 真正进入模型驱动阶段。

## Scope Decisions

这一阶段的关键范围决策如下：

1. **revision runtime 只做保守重写**
   - 允许修改 summary、understanding、style、scene description、scene keywords、scene search query、open issues
   - 不允许改 scene 数量、scene id、scene duration、targetDuration

2. **显式 `sceneKeywordUpdates` 是硬约束**
   - 由 `AgentSessionService._extract_scene_keyword_updates(...)` 提取出的 scene 级关键词修改，优先级高于模型自由发挥
   - 模型可以围绕这些关键词调整 description 和 summary，但不能覆盖这些显式关键词

3. **LangChain 失败时回退 deterministic**
   - revision replan 与 initial planning 不同，用户更需要稳定得到“下一版计划”
   - 只要 LangChain 没产出可安全落地的 patch，就回退 deterministic runtime

4. **外部 contract 保持稳定**
   - `PlannerOrchestrator`、`planner_graph.py`、`AgentSessionService` 的外部入口不变
   - `/workspace` 仍通过同一条 `add_user_message(...)` 路径触发 revision replan

## Architecture

### Existing Layers Kept Stable

以下层保持稳定，不改变入口契约：

- `backend/services/planner_graph.py`
- `backend/services/planner_orchestrator.py`
- `backend/services/agent_session_service.py`
- plan persistence / observation persistence

这意味着：

- revision message 仍由 `AgentSessionService.add_user_message(...)` 触发
- observation 和 immutable vNext 仍由 `PlannerOrchestrator.persist_user_revision_replan(...)` 写入
- graph 仍通过 `run_user_revision_replan(...)` 进入 runtime

本阶段的主改动集中在 `backend/services/planner_runtime_langchain.py` 与 planner revision contract。

### Runtime Responsibilities

`LangChainPlannerRuntime.replan_after_user_revision(...)` 应承担：

1. 组装 revision prompt
2. 调用 revision 专用 structured output runnable
3. 解析和校验 revision patch
4. 将 patch merge 到 `current_agent/current_execution` 的深拷贝上
5. 若任一步失败，回退 deterministic delegate

`DeterministicPlannerRuntime.replan_after_user_revision(...)` 继续作为：

- fallback implementation
- regression reference
- 测试和无 key 场景下的稳定后门

### Prompt Input Shape

revision runtime 的模型输入应至少包含：

- 当前 `AgentPlan`
- 当前 `ExecutionPlan`
- 原始 revision message
- `sceneKeywordUpdates`
- 明确的硬约束说明

prompt 需要明确告诉模型：

- 不能新增或删除 scene
- 不能修改 scene id
- 不能修改 scene duration
- 不能修改 `ExecutionPlan.targetDuration`
- 若用户明确指定了 scene keywords，应将其视为强约束

## Structured Contract

### `RevisionScenePatch`

新增 revision patch contract：

- `id: int`
- `description: str = ""`
- `keywords: list[str] = []`
- `searchQuery: str = ""`

`description` 表示该 scene 的更新后描述。为了保持两个 plan 面的一致性，这个字段会同时投影到：

- `AgentScene.description`
- `ExecutionScene.description`

### `RevisionPlanningResult`

revision runtime 的 structured output 建议定义为：

- `summary: str = ""`
- `audience: str = ""`
- `styleHint: str = ""`
- `style: str = ""`
- `openIssues: list[dict] = []`
- `changeSummary: str`
- `scenePatches: list[RevisionScenePatch] = []`

这份 contract 有两个关键边界：

1. 它不允许模型重建整份 plan
2. 它只允许模型输出“本次 revision 允许改动的字段”

这样 runtime merge 才能天然满足“保守重写”约束。

## Merge Strategy

### Revision Result Merge

后端应先深拷贝当前 `current_agent/current_execution`，再应用 patch。

merge 行为建议固定为：

- `AgentPlan.summary` 可更新
- `AgentPlan.understanding.audience` 可更新
- `AgentPlan.understanding.styleHint` 可更新
- `AgentPlan.openIssues` 可更新
- `ExecutionPlan.style` 可更新
- `scenePatches[id].description` 同步更新对应 `AgentScene.description` 与 `ExecutionScene.description`
- `scenePatches[id].keywords` 更新对应 scene keywords
- `scenePatches[id].searchQuery` 更新对应 execution scene search query

同时保留：

- 原有 scene 数量
- 原有 scene id
- 原有 scene duration
- 原有 `ExecutionPlan.targetDuration`
- 未被 patch 的 scene 原值不变

### Explicit Scene Keyword Overrides

`sceneKeywordUpdates` 应被当作显式用户约束，而不是普通提示词。

对于带显式关键词更新的 scene：

- merge 后的 `keywords` 必须使用 `sceneKeywordUpdates[id]`
- merge 后的 `searchQuery` 应直接由这些关键词重建，例如 `" ".join(keywords)`
- 模型仍可更新该 scene 的 description，但不能覆盖显式关键词本身

这保证用户写下 `场景1：城市 车流 黄昏` 时，系统不会在 revision runtime 中把它弱化成建议。

### Replan History

每次 revision replan 完成后，都应向 `AgentPlan.replanHistory` 追加一条记录，至少包含：

- `triggerType: "user_revision"`
- `summary`
- `message`

这条记录继续作为 plan 内部的规划历史，而不是 runtime diagnostics 的主要落点。

## Validation Rules

`LangChainPlannerRuntime` 在 merge 前后都需要做轻量但严格的校验。

至少包括：

1. `scenePatches.id` 必须全部存在于当前 plan
2. patch 后的 `keywords` 不能为空
3. patch 后的 `searchQuery` 不能为空
4. merge 后的 agent/execution scene id 集合必须保持完全一致
5. merge 后的 scene 数量不得变化
6. merge 后的 scene duration 与 `targetDuration` 不得变化

这些校验的目标不是在用户面暴露更多错误，而是判断：

> LangChain 输出是否足够安全，可以进入落地 merge。

## Fallback Strategy

### Two-Stage Execution

revision replan 应采用两段式运行：

1. 先尝试 LangChain revision runtime
2. 只要没拿到可安全落地的 patch，就回退 deterministic revision runtime

### Fallback Triggers

以下情况都应触发 fallback：

- LLM 调用失败
- structured output 解析失败
- 返回字段缺失
- `scenePatches.id` 指向不存在的 scene
- patch 后 `keywords` 为空
- patch 后 `searchQuery` 为空
- merge 后触发 contract 校验失败

`sceneKeywordUpdates` 不一致不应单独报错，而应由 merge 层强制使用显式 scene keyword overrides。

### Runtime Trace

为了便于调试和回归确认，本阶段建议在 `session_record.planner_trace_json` 中保留最近一次 revision replan 的 runtime 痕迹，例如：

- `lastPlanningState`
- `triggerType`
- `revisionRuntime: "langchain" | "deterministic_fallback"`
- `fallbackUsed: bool`
- `fallbackReason: str`（仅 fallback 时存在）

这些字段是实现内的 trace，不要求进入新的前端显示 contract。

### User-Facing Behavior

对于用户而言，这条链路的目标是稳定产出下一版计划：

- LangChain 成功：直接生成模型驱动的 vNext
- LangChain 失败但 deterministic 成功：仍生成 vNext
- 两者都失败：才真正抛出 revision replan 失败

`changeSummary` 仍应保持用户友好，不需要暴露底层 runtime 名词。

## Testing Strategy

这一阶段不需要扩 UI 测试，重点覆盖 runtime merge 与 fallback。

### 1. `tests/test_planner_runtime.py`

新增 LangChain revision runtime focused tests，至少覆盖：

- 模型返回合法 `RevisionPlanningResult` 时，能够正确 merge 到当前 plan
- 未被 patch 的 scene 保持完全不变
- 显式 `sceneKeywordUpdates` 会覆盖模型返回的冲突关键词
- 模型返回非法 scene id 时触发 deterministic fallback
- 模型调用抛错或 structured output 失败时触发 deterministic fallback
- fallback 后仍返回合法 `next_agent / next_execution / change_summary`

### 2. `tests/test_planner_graph.py`

保持 graph 测试为轻量 wiring test：

- `run_user_revision_replan(...)` 在 LangChain runtime 下仍能返回 `replanning_complete`
- `triggerType` 仍是 `user_revision`
- `changeSummary` 会被带出

这一层不需要承载全部 fallback 细节。

### 3. `tests/test_agent_planner_phase3.py`

补强已有 phase3 integration test，覆盖：

- post-plan `add_user_message(...)` 仍会生成 vNext
- 新 plan version 的 `trigger_type` 为 `user_revision`
- `parent_plan_id` 正确指向前一版
- revision 后 plan 的风格、受众或 scene patch 确实落库
- `planner_trace_json` 能反映本次 revision runtime 来源

### 4. `tests/test_agent_persistence.py`

补 persistence contract 断言：

- `user_revision` observation 仍关联到旧 plan
- `current_plan_id` 指向新 plan
- fallback 场景下也会持久化 vNext，而不是静默放弃新版本

## Acceptance Criteria

这一阶段完成时，应满足：

1. `LangChainPlannerRuntime.replan_after_user_revision(...)` 不再直接委托 deterministic runtime
2. revision runtime 使用独立的 structured output contract，而不是复用 initial planning contract
3. revision runtime 只能修改允许变更的字段，不能改变 scene topology
4. 显式 `sceneKeywordUpdates` 在 merge 后得到严格保留
5. LangChain revision replan 失败时，会自动回退 deterministic revision replan
6. `/workspace` 与 `/api/agent/sessions/{id}/messages` 的外部行为保持稳定
7. focused runtime、graph、phase3、persistence 测试全部通过

## Resolved Decisions

这一阶段的几个关键结论是：

1. **revision runtime 采用 patch contract，而不是 full-plan regeneration**
2. **scene topology 保持不变，严格执行保守重写**
3. **显式 scene keyword syntax 是硬约束，不是软提示**
4. **LangChain revision replan 失败时回退 deterministic，而不是直接报错**
5. **runtime diagnostics 主要进入 `planner_trace_json`，而不是扩前端 contract**

这一步在整个 model-driven agent roadmap 里的位置，是：

> 让用户对 plan 的后续修改，真正进入模型驱动的 planning loop，同时不破坏当前已经稳定的执行面。

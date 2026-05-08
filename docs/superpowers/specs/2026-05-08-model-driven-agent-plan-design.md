# ClipForge Model-Driven Agent Plan Design

## Context

ClipForge `master` 当前已经具备一条完整、可运行的 grounded workflow：

1. 用户输入 plain-text brief
2. 系统搜索候选产品画面
3. 用户确认候选画面
4. 系统生成 grounded plan
5. 后端继续执行素材搜索、下载和渲染

这条链路已经具备 demo 和 beta 级的产品形状，但核心问题也很明确：

- 当前的 “plan” 更像执行前的结构化草稿，而不是 agent 持续维护的工作计划
- brief understanding、候选搜索词生成、grounded plan 生成，仍然主要依赖启发式和模板
- 搜索结果、用户确认、执行失败虽然都能产生系统反馈，但这些反馈还不会系统性回流到模型，形成 replan 闭环

换句话说，当前系统更像：

> 有状态机的 grounded workflow

而不是：

> 由模型持续维护计划、根据世界反馈不断重规划的 agent

## Problem

如果 ClipForge 的目标是“模型驱动的 agent plan”，当前架构存在 4 个根本缺口。

### 1. Plan 太薄

当前 `EditPlan` 更像执行层的剪辑施工单，只适合：

- 展示场景
- 提供关键词
- 驱动搜索和渲染

它不适合作为 agent 自己的工作记忆，因为里面缺少：

- planning goal
- understanding summary
- assumptions
- scene purpose
- evidence status
- fallback policy
- unresolved issues
- replan history

### 2. Planner 不是系统主脑

当前系统里没有一个独立的 planner loop 持续维护计划。

现在更接近：

- session service 推状态
- grounding service 提 query 和 candidate
- confirm 时拼 grounded plan

这意味着模型即使接进来，也很容易沦为“补一段理解摘要”或者“吐一版场景列表”，而不是真正拥有计划控制权。

### 3. Feedback 没有形成 planner 闭环

当前已经有三类重要反馈：

- grounding candidate search results
- user confirmation results
- execution/search/render failures

但这些反馈并没有被统一建模成 planner 的 observation 输入，也不会自动触发模型重规划。

### 4. 状态机和 planning 语义缠在一起

当前工作流里，“是否生成 plan”“是否确认 candidate”“是否失败”都已经有状态，但“正在 replan”“为什么 replan”“replan 后改了什么”还不是一等公民。

如果继续只在现有服务里加 prompt 调用，最终会得到一个：

- 看起来用了模型
- 实际仍由规则驱动主逻辑
- 且越来越难解释和维护

的混合系统。

## Goal

构建一套 **Model-Driven Agent Plan** 架构，让 ClipForge 的 `/workspace` 变成：

> 模型负责持续生成、维护、修订和重规划 plan；系统负责约束流程、执行计划、收集反馈，并把反馈再送回模型。

这套 agent 的推荐基础设施是：

- **LangChain**：模型调用、structured output、planner runtime 封装
- **LangGraph**：stateful orchestration、checkpoint、human-in-the-loop、replan graph

第一阶段要达成的产品体验是：

1. 用户提交 brief 后，系统先生成一版真正的 `AgentPlan`
2. 搜索候选和用户确认会触发模型重新规划，而不是固定模板补全
3. 执行期的搜索失败或素材不足，可以触发有限自动 replan
4. 用户能感知到 plan 是在被持续维护，而不是一次性生成后静止不动

## Non-Goals

这份设计明确不包含以下目标：

- 不直接构建完全通用的 tool-using autonomous agent runtime
- 不让模型接管 job lifecycle、队列调度或 worker control
- 不重写现有 search/download/render 执行链
- 不在第一阶段解决 hosted auth、billing、权限和部署体系
- 不承诺完全自动跳过用户对产品画面的确认
- 不把任意失败都交给模型无限循环重试

这里要做的是：

> 模型驱动的 planning loop

而不是：

> 模型驱动的一切

同时，这一阶段也不要求：

- 把现有 FastAPI + Celery 整体替换成 LangChain/LangGraph 自带运行时
- 把搜索、下载、渲染全部硬改成 LangChain tool-first 模式

## Approaches Considered

### Approach A: 继续增强当前 grounded planner v1

做法：

- 模型负责 brief understanding
- 模型负责 grounded plan generation
- 模型负责用户 revision
- 但搜索和执行失败不进入系统性 replan loop

优点：

- 最贴近当前架构
- 成本最低
- 落地快

缺点：

- 仍然更像 “model-assisted workflow”
- 没有真正的 plan maintenance loop
- 搜索/执行失败只会停在系统层，而不是变成规划反馈

这不是用户当前想要的终点。

### Approach B: 模型驱动 Agent Plan，带有限 replan loop

做法：

- 模型生成第一版 `AgentPlan`
- grounding feedback 回流给模型触发 replan
- user revision 回流给模型触发 replan
- execution feedback 回流给模型触发有限自动 replan
- orchestrator 继续掌控状态机和安全边界

优点：

- 真正把 plan 变成模型主导的核心资产
- 有 agent 感，但仍然保留系统可控性
- 可以复用现有执行链

缺点：

- 需要新增 plan version、observation、feedback adapter 等层
- 比 planner v1 明显更复杂

这是推荐方案。

### Approach C: 通用 tool-using runtime

做法：

- 模型直接决定工具调用顺序、重试策略、停止条件
- 搜索、确认、执行都变成 agent tool invocation

优点：

- 长期潜力最大
- 最像通用 agent

缺点：

- 当前代码和产品都没有准备好承受这一级复杂度
- 风险集中在 orchestration、safety、eval、debug 上
- 很容易冲散已经具备可演示性的 grounded workflow

这条路应该放在更后面。

## Recommended Direction

采用 **Approach B**：

> 构建一个以 `AgentPlan` 为中心、由 `LangChain + LangGraph` 驱动的 model-driven planning loop，让模型持续维护计划；同时保留 execution engine 和 user confirmation 这些稳定边界。

这条路径既能满足“模型驱动的 agent plan”，又能最大程度复用当前 `master` 上已经稳定的执行与持久化基础。

## Core Architecture

系统核心从现在的：

`brief -> grounding -> confirm -> grounded plan -> execute`

升级为：

`brief -> plan v1 -> grounding/search feedback -> replan v2 -> execute -> execution feedback -> replan/retry -> done`

这里最重要的变化不是多调用几次模型，而是：

> plan 不再是一锤子买卖，而是会随着 observation 持续演化的对象。

推荐技术分工：

- `LangChain`: planner LLM calls, structured output, prompt/runtime wrappers
- `LangGraph`: planning graph, replan transitions, checkpoint/resume, approval gates
- 现有后端服务: search providers, asset download, render execution, FastAPI, Celery

## Key Design Principles

### 1. 模型负责 plan，不负责流程

模型的职责：

- 理解 brief
- 生成 `AgentPlan`
- 根据 grounding feedback 重规划
- 根据 execution feedback 重规划
- 根据用户 revision 修改 plan

系统职责：

- 管状态机
- 管用户确认闸门
- 管 job lifecycle
- 管重试次数和自动推进上限

实现上对应为：

- planner action 尽量写成 LangChain structured calls
- workflow state 和节点跳转由 LangGraph graph 承载
- 执行 job 仍由当前服务和 Celery 承担

### 2. AgentPlan 与 ExecutionPlan 分层

真正的模型驱动 plan 不能只是一组 scene。

因此必须把：

- **AgentPlan**：模型维护的工作计划
- **ExecutionPlan**：执行层消费的稳定投影

分开。

### 3. Observation 是一等公民

搜索结果、确认结果、执行反馈不能只是散落在 message / event / artifact 里。

它们必须被结构化保存，并作为 planner loop 的正式输入。

### 4. Replan 是正式状态，不是隐式副作用

只要系统允许模型持续改 plan，就必须承认：

- 正在 replan
- 为什么 replan
- 本次改了什么

这些都应成为产品和数据层的一部分。

### 5. 自动 replan 有边界

第一阶段支持有限自动 replan，但：

- 不允许无限循环
- 不允许自动更换产品对象
- 不允许自动跳过用户确认
- 不允许模型自己修改工作流状态机

LangGraph 在这里的主要价值，是把这些边界显式固化在 graph 和 state transition 上，而不是散落在 prompt 和 if/else 里。

## Main Components

### 1. `LangGraph Planning Graph`

这是新的 planning 主骨架，负责定义：

- `collecting_brief -> planning`
- `planning -> awaiting_grounding_confirmation`
- `awaiting_grounding_confirmation -> replanning`
- `replanning -> ready_for_execution`
- `executing_search / executing_render`
- `execution feedback -> replanning | awaiting_user_decision | completed`

它应该承担：

- state schema
- node wiring
- conditional edges
- checkpoint / resume
- human approval gate

推荐它成为 planning workflow 的单一来源。

### 2. `AgentSessionOrchestrator`

这是总调度器和外部适配层，负责：

- 接 API 请求
- 组织 session 持久化
- 触发或恢复 LangGraph run
- 记录 message / current state / current plan version
- 对外返回 session response 聚合态

它不负责思考 plan 内容。

这层将由当前 `AgentSessionService` 演进而来。

### 3. `PlannerLoop`

这是新的 planning 核心，负责：

- `build_plan_from_brief`
- `replan_after_grounding`
- `replan_after_user_revision`
- `replan_after_execution_feedback`

输入是：

- 当前 `AgentPlan`
- 最新 observation
- 当前约束与上下文

输出是：

- 新版 `AgentPlan`
- 派生的 `ExecutionPlan`
- 本次 change summary

它更像 LangGraph 中的一组核心 node 行为，而不是一个独立接管整个流程的大而全 service。

### 4. `PlannerRuntime`

这是模型调用层，负责：

- prompt 组装
- OpenAI 请求
- schema 校验
- deterministic runtime
- tracing 和错误归类

这层推荐基于 LangChain 构建，而不是继续手写散落的 OpenAI 封装。

推荐职责包括：

- 使用 LangChain chat model wrapper
- 使用 LangChain structured output / schema binding
- 统一 planner action prompt 模板
- 统一 planner error wrapping
- 提供 deterministic runtime，与真实 runtime 共享输入输出 contract

建议拆成：

- `planner_runtime_openai.py`
- `planner_runtime_deterministic.py`

### 5. `FeedbackAdapters`

这是 planner loop 和现实执行世界之间的翻译层，负责把底层反馈整理成 planner 可消费的 observation：

- `GroundingFeedback`
- `CandidateConfirmationFeedback`
- `SearchExecutionFeedback`
- `RenderReadinessFeedback`

这层的目标是避免 planner 直接吃底层 provider / worker 的脏细节。

### 6. `ExecutionEngine`

执行层继续吃 `ExecutionPlan`，负责：

- 搜索素材
- 下载素材
- 渲染视频
- 产生 artifacts 和 execution feedback

这层优先复用当前：

- `AgentExecutionService`
- `search_service`
- `render_service`
- `agent_tasks.py`

第一阶段不要求把它改造成 LangChain tool-first execution。更稳妥的做法是：

- 保留现有后端执行服务
- 由 LangGraph 节点通过 orchestration adapter 调用这些服务
- 只把 planning loop 交给 LangChain/LangGraph

## Plan Model

### `AgentPlan`

这是一份给模型自己维护的工作计划，至少包含：

- `goal`
- `understanding`
- `constraints`
- `strategy`
- `scenes`
- `grounding`
- `openIssues`
- `replanHistory`

示意结构：

```python
class AgentPlan(BaseModel):
    title: str
    goal: str
    summary: str
    understanding: BriefUnderstanding
    constraints: PlanConstraints
    strategy: PlanStrategy
    scenes: list[AgentScene]
    grounding: GroundingState
    openIssues: list[PlanIssue] = Field(default_factory=list)
    replanHistory: list[ReplanRecord] = Field(default_factory=list)
```
```

### `AgentScene`

每个 scene 不能只包含 description 和 query，建议至少有：

- `purpose`
- `visualIntent`
- `searchIntent`
- `evidence`
- `fallbackPolicy`
- `status`

示意结构：

```python
class AgentScene(BaseModel):
    id: int
    purpose: str
    description: str
    visualIntent: str
    searchIntent: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    groundingCandidateIds: list[str] = Field(default_factory=list)
    duration: float
    fallbackPolicy: str = ""
    status: Literal["draft", "grounded", "blocked", "ready_for_execution"] = "draft"
```
```

### `ExecutionPlan`

执行层消费的稳定投影：

```python
class ExecutionPlan(BaseModel):
    title: str
    targetDuration: float
    style: str
    scenes: list[ExecutionScene]
```
```

```python
class ExecutionScene(BaseModel):
    id: int
    description: str
    keywords: list[str] = Field(default_factory=list)
    searchQuery: str
    duration: float
    groundingCandidateIds: list[str] = Field(default_factory=list)
```
```

原则上：

- `AgentPlan` 是脑内工作稿
- `ExecutionPlan` 是施工图

## Observation Model

这套架构里，observation 是 planner loop 的正式输入。

建议的 observation 类型包括：

- `user_message`
- `grounding_feedback`
- `candidate_confirmation`
- `search_feedback`
- `render_feedback`

示意结构：

```python
class AgentObservation(BaseModel):
    id: str
    sessionId: str
    relatedPlanVersion: int | None = None
    observationType: str
    payload: dict
    summary: str = ""
    createdAt: str
```
```

## Planner Actions

第一阶段的 planner actions 推荐固定为 4 个。

推荐实现方式：

- 使用 LangChain 统一封装成 structured planner calls
- 在 LangGraph 的不同节点中调用
- 每个 action 都有稳定 schema，而不是自由文本解析

### 1. `build_plan_from_brief`

输入：

- brief
- 历史 message 摘要
- 当前 session 约束

输出：

- `AgentPlan v1`
- `ExecutionPlan v1`

### 2. `replan_after_grounding`

输入：

- 当前 `AgentPlan`
- `GroundingFeedback`
- `CandidateConfirmationFeedback`

输出：

- grounded `AgentPlan v2`
- grounded `ExecutionPlan v2`

### 3. `replan_after_user_revision`

输入：

- 当前 `AgentPlan`
- 最新用户 revision

输出：

- 新 plan version

### 4. `replan_after_execution_feedback`

输入：

- 当前 `AgentPlan`
- `SearchExecutionFeedback` 或 `RenderReadinessFeedback`

输出：

- 调整后的 plan version
- 或需要用户决策的 recommendation

## Session States

推荐把主状态机定义为：

- `collecting_brief`
- `planning`
- `awaiting_grounding_confirmation`
- `replanning`
- `ready_for_execution`
- `executing_search`
- `executing_render`
- `awaiting_user_decision`
- `completed`
- `failed_terminal`

其中：

- `planning` 和 `replanning` 是明确状态
- `awaiting_user_decision` 用于自动推进风险过高的场景

推荐用 LangGraph state 显式承载这些状态字段，而不是只靠数据库聚合态和分散 service 推导。

## Replan Policy

### 自动 replan 的场景

第一阶段允许 4 类自动 replan：

1. grounding confirmed 后，scene 与 evidence 不匹配
2. 搜索反馈显示 scene 命中太差
3. 渲染前发现素材不足以支撑当前 plan
4. 用户提出的是普通 plan revision，而不是产品改向

### 必须停下来问用户的场景

以下情况进入 `awaiting_user_decision`：

1. 产品对象变化
2. 用户否定当前候选产品画面
3. 自动 replan 超过上限
4. 当前约束与可用素材发生高风险冲突

### 自动 replan 的硬边界

第一阶段建议写死：

- 单次 session 最多 2 次自动 replan
- 单个 scene 最多 1 次 query 重写
- 模型不能自动跳过用户确认
- 模型不能自动更换产品对象

## Persistence Strategy

### `agent_sessions`

继续保留，但只存当前聚合态，例如：

- 当前状态
- 当前 plan version id
- 当前 active job id
- 当前 progress / current step
- 最后错误

如果后续接 LangGraph checkpointer，`agent_sessions` 仍保留，但职责是产品层聚合态，不直接替代 LangGraph 的内部执行状态。

### `agent_plans`

演进成 **不可变 plan version 表**。

每个 version 记录：

- `sessionId`
- `version`
- `parentPlanId`
- `triggerType`
- `plannerMode`
- `plannerModel`
- `planJson`
- `executionPlanJson`
- `summary`
- `changeSummary`
- `status`

### `agent_observations`

新增表，用来保存：

- grounding feedback
- candidate confirmation
- execution feedback
- user revision observations

即使 LangGraph checkpointer 已保留运行态，这张表仍然值得保留，因为它服务的是产品可解释性、offline eval 和 replay，而不仅仅是框架恢复。

### `agent_jobs`

继续表示某个 plan version 的一次 execution attempt。

### `agent_events`

继续保存细粒度运行事件。

### `agent_artifacts`

继续保存 clip / video 等产物，但推荐明确关联：

- `sessionId`
- `jobId`
- `planVersionId`

## Migration Strategy

迁移推荐走双轨，不要大爆破重写。

### Phase 0: 先放进新 plan 形状

- 新增 `AgentPlan / ExecutionPlan / Observation / Feedback` 模型
- `agent_plans` 开始支持 version 语义
- 新增 `agent_observations`
- 在 `backend/requirements.txt` 引入 LangChain / LangGraph 依赖
- 搭起最小 LangGraph state schema 和 checkpointer 方案
- 保持旧 grounded workflow 继续可跑

### Phase 1: 模型接管初版 plan

- `create_session` 改由 LangGraph planning graph 驱动 `build_plan_from_brief`
- 初次搜索改吃 `ExecutionPlan v1`
- 旧 `parse_brief()` 退为 deterministic fallback

### Phase 2: grounding confirmation 触发 replan

- 用户确认候选后写 observation
- LangGraph 从 `awaiting_grounding_confirmation` 进入 `replanning`
- 在 replanning node 调 `replan_after_grounding`
- 产出 grounded plan v2

### Phase 3: 用户 revision 改成真正 replan

- 普通自然语言修改不再只是关键词补丁
- 改为写 observation 并触发 LangGraph replan node
- 生成新的 plan version

### Phase 4: execution feedback 触发有限自动 replan

- 搜索失败 / 素材不足回流给 planner
- 最多触发 1-2 次自动 replan
- 超限则进入 `awaiting_user_decision`

### Phase 5: 前端显式展示 plan 演化

- 展示当前 plan version
- 展示 replan 原因
- 展示 changed scenes / unresolved issues

## Testing Strategy

### 1. Planner model tests

验证：

- `AgentPlan`
- `ExecutionPlan`
- `AgentObservation`
- feedback models

### 2. Planner loop tests

验证：

- build plan
- grounding replan
- user revision replan
- execution feedback replan

并补充：

- LangChain structured output contract tests
- deterministic runtime 和 openai runtime 的一致性测试

### 3. Policy tests

验证：

- 哪些反馈会自动 replan
- 哪些会进入 `awaiting_user_decision`
- 自动 replan 上限是否生效

### 4. Persistence tests

验证：

- plan version 不可变
- observation 与 plan version 关联正确
- job 与 artifact 能关联到对应 plan version

必要时再补：

- LangGraph checkpoint resume 行为
- graph state 到 session 聚合态的映射正确性

### 5. Integration tests

验证完整链路：

- brief -> plan v1
- plan v1 -> grounding feedback -> plan v2
- plan v2 -> execution feedback -> plan v3 or awaiting_user_decision

## Acceptance Criteria

这套 model-driven agent plan 架构算完成，至少要满足：

1. 初版 plan 明确由模型生成，而不是规则模板主导
2. grounding confirmation 会触发模型 replan，而不是模板补完
3. 用户自然语言 revision 会生成新的 plan version
4. 至少一类 execution feedback 能触发自动 replan
5. 状态机仍由 orchestrator 掌控，模型不能越权改流程
6. 用户能从产品界面感知“plan 在演化”，而不是只看到静态结果

## Deferred Work

这一阶段之后才适合继续考虑：

- 更通用的 tool-using runtime
- 更复杂的 multi-turn memory
- planner quality 离线评估面板
- hosted beta 的账户/权限/配额体系
- 更高级的自动素材选择与直接 evidence binding

## One-Sentence Definition

Model-Driven Agent Plan 是 ClipForge 下一阶段的核心架构：基于 `LangChain + LangGraph` 让模型持续维护 `AgentPlan`，系统收集 grounding 与 execution feedback 并回流给模型重规划，而执行链和流程边界继续保持确定性与可控性。

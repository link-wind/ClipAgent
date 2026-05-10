# LangChain Initial Planner Design

Date: 2026-05-10

## Context

ClipForge 当前已经具备一条完整的 planner persistence 和 replanning 基础链路：

1. `PlannerOrchestrator` 负责持久化 plan version 与 observation
2. `planner_graph.py` 负责 LangGraph 编排入口
3. `planner_runtime.py` 负责按配置选择 planner runtime
4. deterministic runtime 已经支持：
   - initial planning
   - grounding replan
   - user revision replan
   - execution feedback replan

同时，仓库里已经引入了：

- `langchain`
- `langgraph`
- `langchain-openai`

并且已有一个占位版的 `planner_runtime_openai.py`，但它目前仍然全部 `NotImplemented`。

用户已经明确下一阶段目标是把 planner 往“模型驱动 agent plan”推进，并且希望优先使用 LangChain 来构造。

## Problem

当前 initial planning 仍完全由 deterministic 规则生成，这有三个明显限制：

1. 初始方案内容过于模板化，无法真实反映 brief 差异。
2. planner runtime 虽然有 LangGraph 外壳，但真正的 planning intelligence 仍然没有接上模型。
3. 如果后续直接把 grounding、revision、execution feedback 一起切到模型，会把 scope 放大得过快，难以稳定演示。

现在最需要解决的问题不是“把所有 planner 行为一次性模型化”，而是：

> 先把默认的 initial planning 主链切成模型驱动，并保留现有 replanning 入口稳定可用。

## Goal

这一阶段建立一个默认启用的 LangChain initial planner，使系统在创建带 prompt 的 session 时，能够通过模型直接产出完整的 `AgentPlan` 和 `ExecutionPlan`。

这一阶段要做到：

1. `build_plan_from_brief()` 由 LangChain planner 驱动
2. 默认 planner mode 切到 `langchain`
3. 模型直接输出完整 `AgentPlan + ExecutionPlan`
4. grounding / user revision / execution feedback 三条 replan 链路继续保持 deterministic
5. LangChain initial planning 失败时，不做 deterministic fallback，而是直接暴露 planning failure

## Non-Goals

这一阶段不做：

- 不把 grounding replan 改成模型驱动
- 不把 user revision replan 改成模型驱动
- 不把 execution feedback replan 改成模型驱动
- 不做多节点 planner graph 拆分
- 不做流式 planning
- 不做模型失败自动重试
- 不做 deterministic fallback
- 不新增 UI 恢复流程
- 不把 LangSmith、Tracing、Prompt Registry 变成这一阶段的硬依赖

## Approaches Considered

### Approach A: Hybrid LangChain Runtime

做一个真正可运行的 LangChain planner runtime，只把 `build_plan_from_brief()` 切到模型驱动，其余 `replan_*` 暂时委托 deterministic runtime。

优点：

- 变更边界最小
- 可复用现有 `planner_graph.py` 和 `PlannerOrchestrator`
- 最快得到“默认模型驱动 initial planning”主链
- 与长期方向一致，不需要引入中间草稿契约

缺点：

- 第一阶段是混合态 runtime
- prompt 与 structured output 校验会成为质量关键点

推荐。

### Approach B: Model Draft + Backend Projection

让模型先产出较轻的场景草稿，再由后端投影成正式 `ExecutionPlan`。

优点：

- 输出更容易控
- 容错性更高

缺点：

- 不是纯粹的模型驱动 planner
- 容易保留两套规划逻辑
- 后续扩展时边界会越来越拧巴

这一阶段不推荐。

### Approach C: Full LangGraph Multi-Node Planner

从第一阶段开始就把 initial planning 拆成多节点模型 graph，例如 brief understanding、scene drafting、execution projection、validation。

优点：

- 最接近长期架构
- 未来扩 grounding / revision 更自然

缺点：

- 第一阶段 scope 明显过大
- 调试、验证、提示词拆分成本偏高

暂不做。

## Recommended Direction

采用 **Approach A: Hybrid LangChain Runtime**。

核心原则：

> 先把默认的 initial planning 主链改成真实模型驱动，同时让其余 replanning 行为继续依赖已经稳定的 deterministic runtime。

## Scope Decisions

这一阶段的关键决策如下：

1. **仅 initial planning 模型驱动**
   - 只实现 `build_plan_from_brief()`
   - 其他 `replan_*` 保持 deterministic

2. **默认 planner mode 切为 `langchain`**
   - 配置默认值不再是 `deterministic`
   - 仍保留显式切回 deterministic 的能力，方便本地调试和回归测试

3. **模型失败直接暴露**
   - 不做 deterministic fallback
   - 不做自动重试

4. **模型直接输出正式契约**
   - 输出目标是完整 `AgentPlan + ExecutionPlan`
   - 不引入中间草稿结构作为对外 contract

## Architecture

### Existing Layers Kept Stable

以下层级在这一阶段保持稳定，不改入口契约：

- `backend/services/planner_graph.py`
- `backend/services/planner_orchestrator.py`
- `backend/services/planner_models.py`
- plan persistence / observation persistence 流程

这意味着：

- session service 仍然通过 `PlannerOrchestrator.persist_initial_plan(...)` 生成第一版 plan
- orchestrator 仍然调用 `run_initial_planning(...)`
- LangGraph 仍然通过 `_build_plan_node(...)` 触发 runtime

### Runtime Layout

建议将当前占位的 planner runtime 升级为真正的 LangChain runtime。

两种可接受实现方式：

1. 保留文件名 `planner_runtime_openai.py`，但内部实现为基于 LangChain 的 runtime
2. 新建 `planner_runtime_langchain.py`，再由 selector 指向它

推荐第二种命名，因为它更准确表达“框架层是 LangChain，而不是直接裸 OpenAI client”。

### Runtime Responsibilities

`LangChainPlannerRuntime` 负责：

- 初始化 `ChatOpenAI`
- 组装 initial planning prompt
- 调用 structured output
- 做初步 schema 解析
- 做 cross-field validation
- 返回正式 `AgentPlan` 与 `ExecutionPlan`

`DeterministicPlannerRuntime` 继续负责：

- `replan_after_grounding()`
- `replan_after_user_revision()`
- `replan_after_execution_feedback()`

`LangChainPlannerRuntime` 内部应持有一个 deterministic delegate，用于这三条 replan 路径直接转发，而不是重复实现。

### Runtime Selection

`backend/services/planner_runtime.py` 应继续作为统一 selector。

目标行为：

- 默认返回 `LangChainPlannerRuntime`
- 显式配置 `CLIPFORGE_PLANNER_MODE=deterministic` 时返回 `DeterministicPlannerRuntime`

这样既满足“默认模型驱动”，又保留了一个稳定的测试/诊断后门。

## Output Contract

### Structured Result Wrapper

建议新增一个很薄的 structured output wrapper，例如：

- `InitialPlanningResult`
  - `agentPlan: AgentPlan`
  - `executionPlan: ExecutionPlan`

模型输出直接对齐现有正式 planner models，而不是定义新的中间 schema。

### Why Full Contract Now

这一阶段选择让模型直接输出正式契约，而不是中间 draft，原因是：

1. 目标本身就是“模型驱动 planner”
2. 当前 `PlannerOrchestrator`、`planner_graph`、plan persistence 都已经围绕这两个对象工作
3. 如果引入中间结构，后端会继续保留一层 deterministic projection 逻辑，稀释模型 planner 的边界

## Prompt Design

### Prompt Shape

prompt 分为两层：

1. `system prompt`
2. `human prompt`

`human prompt` 只承载用户 brief，不混入 future-stage 的 grounding、revision、execution feedback 语义。

### System Prompt Requirements

system prompt 应至少明确以下规则：

- 你是一个短视频 planning assistant
- 必须输出 2 到 4 个 scenes
- 目标是产品介绍 / 产品亮点短片，而不是泛品牌广告文案
- `AgentPlan` 与 `ExecutionPlan` 的 scene 数量和 id 必须一致
- `searchQuery` 必须是适合素材检索的英文短语
- `keywords` 应该简短、可检索、数量克制
- scene 描述必须和 brief 相关，不要出现与产品无关的泛化镜头
- 时长应合理，总体接近目标短视频时长

### Model Settings

第一阶段建议保持低温度：

- `temperature=0` 或接近 0 的稳定设置

目标不是追求创意发散，而是先让输出结构稳定、可验证、可复现。

## Validation and Normalization

### Schema Validation

第一层校验由 Pydantic 完成：

- `AgentPlan`
- `ExecutionPlan`
- `InitialPlanningResult`

### Cross-Field Validation

除了 schema，还需要增加运行时一致性校验，至少包括：

1. `agentPlan.scenes` 与 `executionPlan.scenes` 数量一致
2. scene id 一一对应，且从 1 开始递增
3. 每个 `ExecutionScene.searchQuery` 非空
4. 每个 scene 至少保留 1 个有效关键词
5. 每个 scene 的 `duration` 大于 0
6. `title`、`goal`、`summary` 非空
7. `executionPlan.targetDuration` 不能明显小于 scene 时长总和

### Light Normalization Only

允许的标准化仅限于：

- trim 首尾空白
- 过滤空关键词
- 将 `searchQuery` 归一化为单空格分隔

这一阶段不应偷偷“补齐”模型漏掉的结构，也不应默默修正 scene id、duration 或 plan skeleton。

原则是：

> 模型要么直接给出可用计划，要么直接失败。

## Failure Semantics

### No Deterministic Fallback

LangChain initial planning 失败时：

- 不回退 deterministic plan
- 不自动重试
- 不返回一个“看起来成功但其实已降级”的 plan

### Session/API Behavior

在现有代码结构下，`AgentSessionService.create_session(prompt)` 若 planner 抛错，会整体 rollback 并向上抛出异常。

这一阶段保留该行为：

- API 返回 planning failure
- 不创建半成品 plan
- 不额外落一个 failed session 版本

这样能最大程度保持当前事务边界不变，并让模型链路问题真实暴露出来。

### Why Not Create Failed Sessions Yet

“创建 failed session 并允许恢复”是合理的长期方向，但它会额外引入：

- session failure persistence 语义
- 首次 planning 失败时的前端恢复路径
- create-session 事务边界调整

这些都不是 initial LangChain planner 第一阶段必须解决的问题。

## Testing Strategy

### 1. Runtime Unit Tests

聚焦 `LangChainPlannerRuntime.build_plan_from_brief()`：

- 模型 structured output 成功时，返回合法 `AgentPlan + ExecutionPlan`
- scene id 不一致时抛错
- 空 `searchQuery` 或空关键词时抛错
- 模型异常或 structured parse 异常时原样失败，不 fallback

这些测试不应依赖真实 OpenAI API，而应通过 fake runnable 或 mock structured output 完成。

### 2. Runtime Selector Tests

验证配置切换行为：

- 默认 mode 返回 `LangChainPlannerRuntime`
- `CLIPFORGE_PLANNER_MODE=deterministic` 时返回 `DeterministicPlannerRuntime`

### 3. API / Orchestration Contract Tests

聚焦现有 planning 链路是否被正确接上：

- patch LangChain runtime 成功产出固定 plan，验证 `create_session(prompt)` 返回 `plan_ready`
- patch LangChain runtime 抛错，验证 `create_session(prompt)` 失败且不产生 plan record
- 在 LangChain runtime 默认启用情况下，grounding / revision / execution feedback 仍然可以通过 deterministic delegate 继续工作

### 4. No Live-API Requirement in CI

测试不应要求 CI 或本地必须配置真实 `OPENAI_API_KEY`。

第一阶段测试目标是：

- 验证 planner contract
- 验证 runtime selection
- 验证 orchestration wiring

而不是验证外部模型服务可达性。

## Acceptance Criteria

当这一阶段完成时，应满足：

1. 默认 planner mode 为 `langchain`
2. 带 prompt 创建 session 时，initial plan 由 LangChain runtime 生成
3. 模型直接输出完整 `AgentPlan + ExecutionPlan`
4. grounding / user revision / execution feedback replan 仍然稳定可用
5. LangChain initial planning 失败时，系统直接暴露 failure，不回退 deterministic
6. selector、runtime、API contract 相关测试全部通过

## Out of Scope for This Phase

- grounding 模型重规划
- revision 模型重规划
- execution feedback 模型重规划
- planner trace 的细粒度 LLM diagnostics
- prompt 版本化平台
- LangSmith / tracing 产品化接入
- 多节点 planner subgraph

## Follow-Up

如果这一阶段稳定落地，下一阶段最自然的扩展顺序是：

1. 将 user revision replan 切为模型驱动
2. 再评估 grounding replan 是否需要模型参与
3. 最后再把 execution feedback replan 接入模型 runtime

这样可以保持每一步都沿着既有 planner contract 逐步扩展，而不是一次性重写整个规划系统。

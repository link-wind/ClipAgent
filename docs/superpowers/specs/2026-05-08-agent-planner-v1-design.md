# ClipForge Agent Planner v1 Design

## Context

`master` 现在已经有一条完整的 `/workspace` grounded workflow：

1. 用户输入 plain-text brief
2. 系统搜索候选产品画面
3. 用户确认候选画面
4. 系统生成 grounded plan
5. 后端继续执行素材搜索、下载和渲染

这条链路的产品形状已经成立，但“像 agent 的核心部分”还比较弱。当前真正决定理解质量的前半段，主要还是规则和模板：

- `backend/services/grounding_service.py` 负责 brief 解析、搜索词生成和候选聚合
- `backend/services/agent_session_service.py` 负责会话编排和 grounded plan 生成
- `backend/services/agent_service.py` 里仍保留了一套兼容性的内存版同构逻辑
- `backend/services/gpt_service.py` 虽然已接 OpenAI，但目前只服务旧的视频脚本拆解能力，并不是 `/workspace` 的主脑

结果是：产品已经有 agent-like workflow，但还没有一个真正的 planner brain。

## Problem

当前 `/workspace` 的主要短板不是没有流程，而是前半段的智能密度不够：

1. brief understanding 仍然依赖启发式提取，容易吃语义表达方式
2. search query 生成偏模板化，命中真实产品视觉素材的稳定性不够
3. grounded plan 还是“根据候选字段拼一个合理模板”，而不是基于 brief + confirmed candidates 的真正规划
4. plan revision 目前主要支持非常有限的结构化修改，缺少自然语言修订能力
5. 如果现在直接跳到“通用 tool-using agent”，会在执行链尚未稳固前把复杂度一下拉爆

所以，下一阶段最该做的不是更花的 UI，也不是完整通用 agent runtime，而是先把 `/workspace` 的 planner 做出来。

## Goal

构建 **Agent Planner v1**，把 `/workspace` 的前半段升级为模型驱动，同时保持后半段搜索/下载/渲染执行链继续走当前稳定实现。

这一版要解决的核心问题只有三类：

1. **更像真的 brief understanding**
2. **更像真的 grounded plan generation**
3. **更像真的 plan revision**

用户应该明显感受到两件事：

- 系统确实“理解了”这个产品 brief
- 确认产品画面之后，后续计划是围绕这些画面生成的，而不是套一个通用模板

## Non-Goals

这一阶段明确不做下面这些事：

- 不重写搜索、下载、渲染 job execution pipeline
- 不直接上通用 autonomous tool-using agent
- 不做大规模 `/workspace` UI 重构
- 不解决 hosted auth、billing、部署与多租户
- 不承诺 YouTube / 第三方素材源的长期稳定性
- 不把“真正使用已确认候选素材直接参与渲染”作为这一版硬目标

Agent Planner v1 的定位，是先把“脑子”补上，而不是一口气把整套 agent runtime 做满。

## Approaches Considered

### Approach A: 继续沿用当前启发式和模板，只做体验打磨

优点：

- 开发成本最低
- 几乎不碰现有后端结构
- 对当前 smoke flow 影响最小

问题：

- 产品会继续停留在 “agent-shaped workflow”
- brief quality、grounding quality、plan revision quality 都很难真正提升
- 后续再接模型时，会在已经耦合的启发式逻辑上继续打补丁

这条路不适合作为下一阶段主线。

### Approach B: 引入独立 planner layer，只替换前半段脑力逻辑

优点：

- 范围清晰，能直接提升 agent 体感
- 保留当前执行链稳定性
- 能用 deterministic planner 先跑通 contract，再接真实模型
- 后面继续演进成更强 agent 也有干净边界

问题：

- 需要补一层新的 structured contract
- 会临时并存“planner brain + deterministic execution”的混合架构

这是推荐方案。

### Approach C: 直接做通用 tool-using agent runtime

优点：

- 长期上限高
- 听起来最像“真的 agent”

问题：

- 会同时引入 orchestration、tool control、memory、retry、safety、evaluation 多个新难题
- 当前执行链还没有准备好承接这一级复杂度
- 很容易把现在已经可演示的 workflow 冲散

这条路应该放到 Planner v1 验证之后，而不是现在就跳。

## Recommended Direction

采用 **Approach B**：

> 保留现有 session orchestration 和 execution pipeline，只把 brief understanding、grounded planning、plan revision 三块前半段逻辑收敛到一个独立的 planner service。

这会让 ClipForge 从“有 grounded workflow”往“有真正 planner brain”迈一步，而且这一步是可控的。

## Design Principles

### 1. 状态机继续保持确定性

`AgentSessionService` 仍然是 workflow orchestrator。状态推进、候选确认、版本落库、失败回退这些流程规则不交给模型。

模型负责的是：

- 解释 brief
- 生成 search queries
- 生成 grounded plan
- 根据自然语言反馈修订 plan

### 2. 模型输出必须结构化

Planner 不返回自由文本再靠字符串解析。所有 planner action 都必须经过 Pydantic contract 校验，确保：

- 可测试
- 可持久化
- 可演进
- 可在 deterministic 和 OpenAI 两种实现之间切换

### 3. 先让“前半段更真”，后半段先不重写

这一阶段允许计划和执行之间仍然保留一部分“grounded but not fully execution-bound”的过渡状态。

也就是说，plan 会更 grounded，但搜索/渲染执行链仍然可以继续主要依赖 `searchQuery` 工作。这是有意识的范围控制。

### 4. 先有 deterministic planner，再接真实模型

第一步不是直接把 OpenAI 接进主链路，而是先定义 contract，再做 deterministic planner，让：

- 后端 contract tests 能稳定通过
- `/workspace` flow 在无 key 环境下仍可本地跑通
- fixture-based eval 能先建立基线

然后再接 OpenAI planner。

## Module Responsibilities

### `backend/services/agent_session_service.py`

继续作为主编排器，负责：

- create / read / add message / confirm grounding / confirm session
- session status 更新
- grounding state 落库
- plan version 落库
- retryable error 归类

它不再自己决定 brief 的语义，也不再自己拼 grounded plan 模板。

### `backend/services/grounding_service.py`

职责收缩为：

- 根据 search queries 搜索候选素材
- 聚合 fixture / pexels / youtube 候选
- 当 planner 生成的 queries 没有命中时，执行确定性的 fallback 查询策略

它不再承担：

- brief parsing
- audience/style/feature 提炼
- 主搜索词决策

### `backend/services/planner_service.py`

新增的唯一 planner 入口，负责：

- `understand_brief(...)`
- `build_grounded_plan(...)`
- `revise_grounded_plan(...)`

这里是唯一允许直接调用模型的 session-planning 层。

### `backend/services/planner_models.py`

新增结构化 contract 层，定义 planner 的输入输出模型，避免把 schema 分散在 prompt 或 session service 里。

### `backend/services/gpt_service.py`

保留为旧能力的兼容实现，不把它硬扩成 `/workspace` 的主脑。

如果后续需要共用 OpenAI client 初始化逻辑，可以再做轻量抽取；但 Planner v1 不要求先统一所有 AI service。

## Planner Actions

Planner v1 只支持三个动作。

### 1. `understand_brief`

触发时机：

- `create_session(prompt)`
- grounding 未确认前的 `add_user_message(...)`

输入：

- 当前用户最新 brief
- 可选的已有 understanding（用于增量修订）
- 可选的历史消息摘要

输出：

- `BriefUnderstanding`

用途：

- 生成更合理的 search queries
- 给候选确认阶段提供更可信的产品理解
- 驱动后续 grounded plan generation

### 2. `build_grounded_plan`

触发时机：

- `confirm_grounding_candidates(...)`

输入：

- 原始 prompt
- `BriefUnderstanding`
- 已确认 candidates
- 最近用户消息上下文

输出：

- `GroundedPlanDraft`

用途：

- 生成真正围绕 confirmed candidates 的 plan
- 给 plan versioning 和 step snapshot 提供结构化来源

### 3. `revise_grounded_plan`

触发时机：

- `plan_ready` 状态下的 `add_user_message(...)`

输入：

- 当前 plan
- 最新用户修订意见
- grounding context
- 最近消息上下文

输出：

- `GroundedPlanDraft`

用途：

- 支持自然语言修订，而不是只支持 `场景 1: xxx` 这种窄格式

## Planner Contracts

### `BriefUnderstanding`

推荐字段：

```python
class BriefUnderstanding(BaseModel):
    productName: str = ""
    audience: str = ""
    styleHint: str = ""
    featureHints: list[str] = Field(default_factory=list)
    searchQueries: list[str] = Field(default_factory=list)
    summary: str = ""
    assumptions: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
```
```

说明：

- `summary` 是用户可感知的理解摘要，不是 chain-of-thought
- `assumptions` 用来表达 planner 的可见假设，例如“未明确提供目标受众时，默认偏向品牌/营销场景”
- `searchQueries` 是 grounding search 的主输入

### `GroundedSceneDraft`

推荐字段：

```python
class GroundedSceneDraft(BaseModel):
    id: int
    description: str
    keywords: list[str] = Field(default_factory=list)
    duration: float
    searchQuery: str
    groundingCandidateIds: list[str] = Field(default_factory=list)
```
```

这里新增 `groundingCandidateIds` 的原因很重要：

- 它把“确认过哪些候选画面”真正连接到 scene 级别
- 即使执行链当前暂时还主要吃 `searchQuery`，plan 本身也已经保留了 grounding linkage
- 这给后续真正把 confirmed candidate 直接喂给 execution 留下稳定接口

### `GroundedPlanDraft`

推荐字段：

```python
class GroundedPlanDraft(BaseModel):
    title: str
    targetDuration: float = 30.0
    style: str = ""
    summary: str = ""
    scenes: list[GroundedSceneDraft] = Field(default_factory=list)
```
```

`summary` 用来表达这份 plan 的整体剪辑方向，既能服务 UI，也能用于 snapshot / debug。

## Persistence Strategy

### Keep the current tables

Planner v1 推荐 **不新增表**，优先复用当前持久化骨架：

- `agent_sessions`
- `agent_messages`
- `agent_plans`
- `agent_events`

原因很简单：这一阶段的重点不是建更复杂的数据层，而是把 planner contract 跑通。

### Grounding persistence

`grounding_summary_json` 继续作为 grounding 阶段的主存储容器，保留当前已存在字段：

- `productName`
- `audience`
- `styleHint`
- `featureHints`
- `searchQueries`
- `candidates`
- `selectedCandidateIds`

另外，Planner v1 可以在原始 JSON 中追加内部字段，例如：

- `summary`
- `assumptions`
- `confidence`
- `plannerVersion`

这些字段在第一版不一定要全部暴露给前端响应，但应该允许作为内部调试和 future UI 的留存信息。

### Plan persistence

`plan_json` 继续保存 plan 主体。

推荐把 `PlanScene` 扩成可选支持 `groundingCandidateIds`，这样 `plan_json` 能直接保留 scene -> confirmed candidate 的映射。

如果第一刀不想扩 API surface，那么也可以把这层映射先保存在 `plan_json` 的内部扩展字段里；但推荐方案仍然是把它做成明确字段，而不是躲在隐式 JSON 角落里。

## Session Flow After Planner v1

### Flow 1: 创建会话 / grounding 前修订

1. 落 user message
2. 调 `planner_service.understand_brief(...)`
3. 把 `BriefUnderstanding.searchQueries` 交给 `grounding_service.search_candidates(...)`
4. 若无结果，继续走 grounding service 的 fallback query 逻辑
5. 写回 `grounding_summary_json`
6. 追加 assistant message，提示“我已理解你的产品方向，并整理出候选产品画面，请确认”

### Flow 2: 候选确认后生成 grounded plan

1. 校验 `candidateIds`
2. 读取当前 `grounding_summary_json`
3. 调 `planner_service.build_grounded_plan(...)`
4. 将结果映射为 `EditPlan` / 扩展 plan model
5. 新建 `agent_plans` 版本
6. 更新 grounding 为 `confirmed`
7. 追加 assistant message，提示 grounded plan 已生成

### Flow 3: plan ready 后自然语言修订

1. 落 user message
2. 读取最新 plan + grounding
3. 调 `planner_service.revise_grounded_plan(...)`
4. 写入新的 plan version
5. 保留 grounding confirmed 状态不变

当前的 `场景 1: ...` 关键词补丁逻辑可以保留为 deterministic fallback，但不再作为主修订路径。

## Runtime Modes

Planner v1 需要从第一天开始就支持两种运行模式：

### 1. `deterministic`

用途：

- 本地开发
- contract tests
- fixture eval
- 没有 `OPENAI_API_KEY` 的环境

特点：

- 不调用真实模型
- 只根据固定规则或 fixture 输出 schema-valid planner result
- 保证 `/workspace` flow 在本地依然可稳定跑通

### 2. `openai`

用途：

- 真正验证 agent planner 体感
- 小规模 hosted beta

特点：

- 由 OpenAI 生成 planner output
- 输出必须经过严格 schema 校验
- 出错时应回到明确的 planning failure，而不是静默退化成脏数据

推荐新增环境变量：

- `CLIPFORGE_PLANNER_MODE=deterministic|openai`
- `CLIPFORGE_PLANNER_MODEL=<configurable-model-name>`

本地默认建议是 `deterministic`，而不是强依赖 key。

## OpenAI Planner Requirements

真实模型实现必须遵守几个边界：

1. 使用结构化输出，而不是自由文本
2. 低温度，降低 plan 漂移
3. 每个 action 都有独立 schema
4. schema 校验失败时最多自动重试一次
5. 不请求冗长推理过程，只要 compact rationale / summary

这能避免 `/workspace` 看起来更聪明，但 backend contract 反而变脆。

## Failure Handling

### Planner unavailable

如果 `planner_mode=openai` 且：

- key 缺失
- API 不可达
- 返回结构无效且重试后仍失败

则 session 应进入明确的 planning failure：

- `status = failed`
- `error.retryableStep = "planning"`
- `currentStep` 给出清晰说明

不要静默 fallback 成一份看起来像成功、实际质量不可控的 plan。

### No candidate results

如果 planner 生成的 search queries 没有命中候选：

- grounding service 仍然可以尝试当前 deterministic fallback queries
- 若 fallback 后仍无结果，则保留在可解释的 grounding failure / pending state

### Revision conflicts with confirmed product

`revise_grounded_plan(...)` 默认只改 plan，不自动改 confirmed candidates。

如果用户的自然语言反馈本质上是在换产品，例如：

- “不是 Notion AI，改成 Asana”

这不应该被当成普通 plan revision 静默处理。Planner v1 推荐把这类情况视为需要重新 grounding 的请求，而不是自动替换 confirmed candidates。

是否在第一版直接做“自动回退到 needs_confirmation”可视实现成本决定，但至少不能悄悄吃掉这个语义变化。

## Testing and Evaluation Strategy

### 1. Schema contract tests

新增 planner contract tests，覆盖：

- `BriefUnderstanding`
- `GroundedSceneDraft`
- `GroundedPlanDraft`

重点验证：

- schema 稳定
- 默认值清晰
- scene-level grounding ids 可选但行为明确

### 2. Deterministic planner service tests

新增 planner service tests，覆盖：

- understand brief
- build grounded plan
- revise grounded plan
- invalid revision fallback

### 3. Agent integration tests

扩展现有后端测试，重点验证：

- create session 会先生成 planner-based grounding context
- confirm candidate 会生成 planner-based grounded plan
- plan ready 下的自然语言 message 会生成新的 plan version
- grounding confirmed 后不会被普通 revision 静默冲掉

### 4. Persistence tests

补 persistence coverage，验证：

- planner 生成字段能正确落到 `grounding_summary_json`
- plan version 正确递增
- `groundingCandidateIds` 若落库，能稳定读回

### 5. Golden fixture eval

建立 10-20 条 canonical product briefs 的 fixture 集，覆盖：

- SaaS 产品
- AI 工具
- 消费级 app
- 功能型 brief
- 风格型 brief
- 含歧义产品名的 brief

每条 fixture 至少校验：

- `productName`
- `featureHints`
- `searchQueries`
- plan scene 是否与 confirmed candidates 相关

这组 fixture 是 OpenAI planner 上线前的最低评估基线。

## Suggested File Direction

推荐新增或修改的文件方向如下：

- 新增 `backend/services/planner_models.py`
- 新增 `backend/services/planner_service.py`
- 可选新增 `backend/services/planner_openai.py`
- 可选新增 `backend/services/planner_deterministic.py`
- 修改 `backend/services/agent_session_service.py`
- 收缩 `backend/services/grounding_service.py`
- 视需要调整 `backend/models/agent.py`
- 新增 `tests/test_planner_service.py`
- 新增 `tests/test_planner_models.py`
- 扩展 `tests/test_agent_backend.py`
- 扩展 `tests/test_agent_persistence.py`
- 新增 `tests/fixtures/planner/`

## Rollout Order

### Phase 1A: Contract first

1. 定义 planner models
2. 建立 deterministic planner
3. 加 schema / service / fixture tests

### Phase 1B: Wire pre-confirm flow

1. `create_session` 接 `understand_brief`
2. grounding search 改吃 planner queries
3. grounding persistence 改存 planner understanding

### Phase 1C: Wire grounded plan generation

1. `confirm_grounding_candidates` 接 `build_grounded_plan`
2. plan versioning 接入新 draft
3. step snapshot 适配新 plan / summary

### Phase 1D: Wire plan revision

1. `plan_ready` 下的自由文本修订接 `revise_grounded_plan`
2. 保留旧关键词补丁作为 fallback
3. 补 integration tests

### Phase 1E: Turn on real model

1. 接 OpenAI planner
2. 跑 fixture eval
3. 通过配置切换到 `openai`
4. 做一轮 `/workspace` 人工验收

## Acceptance Criteria

Agent Planner v1 完成时，应该满足：

1. `/workspace` 仍保持当前 grounded-first flow，不回退成功能断裂
2. brief understanding 不再主要由 `grounding_service.parse_brief()` 这类启发式逻辑主导
3. grounded plan 来自显式 planner contract，而不是模板拼装
4. plan ready 后支持自然语言修订，不要求用户记住窄格式语法
5. deterministic mode 下测试和本地 demo 仍可稳定运行
6. OpenAI mode 下 planner failure 是可解释、可重试的，而不是 silent degradation

## Deferred Work

这一版之后，才适合继续考虑：

- 真正把 confirmed candidate 直接送入 execution，而不是主要靠 `searchQuery`
- 更强的 agent memory / multi-turn planning
- general tool-using agent runtime
- hosted beta 的账户、配额、权限和部署体系
- 更细的 planner quality offline eval 面板

## One-Sentence Definition

Agent Planner v1 是 ClipForge `/workspace` 的第一层真正 planner brain：它用结构化模型输出替换前半段启发式理解与模板计划，同时保留后半段执行链的稳定性。

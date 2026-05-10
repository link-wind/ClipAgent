# Brief Retrieval Query Pack Design

Date: 2026-05-10

## Context

ClipForge `master` 当前已经同时具备两条关键基础能力：

1. `/workspace` grounded workflow 已经成立：
   - 用户输入 brief
   - 系统搜索候选产品画面
   - 用户确认候选画面
   - 系统生成 grounded plan
   - 后端继续执行搜索、下载和渲染
2. LangChain initial planner 已经接到主链：
   - `planner_runtime_langchain.py` 已能生成初始 `AgentPlan + ExecutionPlan`
   - `planner_runtime.py` 默认已切到 `langchain`
   - 其余 replan 仍保持 deterministic

但 grounded workflow 的最前段，也就是“如何把用户 brief 转成可检索的搜索意图和搜索词”，目前仍主要由 `backend/services/grounding_service.py` 的规则逻辑负责：

- `parse_brief(...)` 用启发式提取 `product_name / audience / style_hint / feature_hints`
- `_build_search_queries(...)` 只生成少量平铺 query
- `search_candidates(...)` 会把同一批 query 依次喂给 fixture / pexels / youtube

这使得当前系统虽然已经“像一个 agent”，但在检索入口这一层还不够像“理解过 brief 再去搜索”。

## Problem

当前 grounded workflow 的短板，第一优先级不是 UI 解释不够，也不是 ranking 不够复杂，而是：

1. brief 到 query 的映射过于模板化
2. query 没有清晰的分层意图，品牌词、产品 demo 词、功能词、兜底词都混在一起
3. provider 没有被 query 意图显式指导，YouTube 和 Pexels 实际上吃的是不同类型的 query
4. 当前 grounding summary 只能看到最终 `searchQueries`，却不能保留“这些 query 为什么存在、面向哪个 provider、优先级如何”

结果是：

- 模糊 brief 很容易搜偏
- 多义产品名很容易命中错误产品
- 即便模型已经开始负责 initial planning，grounding 入口仍然偏 deterministic 和启发式

## Goal

这一阶段的目标是：

> 构建一个由 LangChain 驱动的 `RetrievalQueryPack` 层，把用户 brief 转成结构化检索计划，再交给现有 `GroundingService` 执行搜索。

这一阶段要做到：

1. 使用模型生成结构化 brief retrieval 理解结果，而不是只靠规则抽取
2. 让 query 具备明确的检索意图分层
3. 让 query 能表达 provider 偏好，而不是所有 provider 吃同一批词
4. 在不改现有 `/workspace` 主流程的前提下，提高候选产品画面的命中质量
5. 保持当前 API 和前端确认流程基本兼容

## Non-Goals

这一阶段明确不做：

- 不新增用户可见的 understanding 卡片
- 不改 `/workspace` 当前确认页结构
- 不实现 candidate ranking / reranking
- 不改 grounded plan generation 逻辑
- 不把 grounding replan 一起切成模型驱动
- 不重写 `PlannerOrchestrator`、`planner_graph.py` 或 Celery 执行链
- 不让模型直接决定最终候选展示顺序

换句话说，这一步只解决：

> “给我一个 brief，我能不能更像样地决定该搜什么。”

## Approaches Considered

### Approach A: 仅增强现有 `parse_brief(...)`

做法：

- 保留当前 `GroundingService` 结构
- 只在规则提取和 query 拼接上做更多启发式增强

优点：

- 改动最小
- 风险最低
- 不引入新的模型 contract

缺点：

- 很快又会积累更多难维护的规则
- 无法真正承接“模型驱动 agent plan”的方向
- provider-aware query 分层会越写越拧

不推荐作为主线。

### Approach B: 新增 LangChain `RetrievalQueryPack`，再交给 `GroundingService`

做法：

- 模型先输出结构化 retrieval pack
- `GroundingService` 只负责执行、聚合和 fallback
- 现有 session orchestration 与 UI 基本不变

优点：

- 变化边界清晰
- 能直接提升检索质量
- 与 LangChain / model-driven planner 的长期方向一致
- 后续可以自然扩到 ranking、explainability、memory

缺点：

- 需要扩一层新的 grounding contract
- 会短期形成“planner 已模型化、grounding query generation 也模型化，但 ranking 仍确定性”的混合态

这是推荐方案。

### Approach C: 一步做到理解卡 + query pack + ranking

做法：

- 模型同时生成用户可见 understanding、query plan 和 candidate ranking 信号
- 前端同步增加可解释展示

优点：

- 用户感知最强
- 端到端更完整

缺点：

- 范围一下变大
- 很难隔离“检索质量”与“展示质量”的收益
- 容易把本阶段做成半个新产品面

这条路适合后续阶段，不适合作为 A-1。

## Recommended Direction

采用 **Approach B**：

> 把 grounded workflow 的“brief -> search intent -> search queries”这一层独立出来，由 LangChain 生成 `RetrievalQueryPack`，然后继续复用当前 `GroundingService` 的 provider 搜索与候选聚合能力。

核心原则是：

- 模型负责“想清楚该怎么搜”
- grounding service 负责“按计划去搜并做好兜底”

## Scope Decisions

这一阶段的关键范围决策如下：

1. **只模型化 retrieval query planning**
   - 不把 ranking、confirmation、grounded plan generation 一起塞进来

2. **保留现有 grounding summary 的外部兼容面**
   - 前端仍主要读取 `searchQueries / candidates / selectedCandidateIds`
   - 新字段只作为增强信息追加

3. **保留 deterministic fallback**
   - 与 initial planner 不同，这一层失败不能直接把流程打死
   - retrieval pack 失败时退回现有规则式 query 生成

4. **provider-aware，但不 provider-hardcode 到 UI**
   - query 可表达 provider 偏好
   - 前端仍只看候选，不需要先理解 provider 策略

## Architecture

### Existing Flow After This Change

新的 grounded 搜索入口将从：

`brief -> parse_brief() -> searchQueries -> search_candidates()`

升级为：

`brief -> build_retrieval_query_pack() -> query plan -> search_candidates_for_query_plan() -> grounding summary`

用户视角上的流程不变：

1. 输入 brief
2. 系统返回候选产品画面
3. 用户确认候选

变化发生在后台的 query planning 层。

### New Module Responsibilities

#### `backend/services/grounding_planner_runtime.py`

新增一个很薄的 LangChain runtime，负责：

- 初始化 `ChatOpenAI`
- 组装 retrieval planning prompt
- 调用 structured output
- 返回 `RetrievalQueryPack`
- 失败时抛出明确异常给调用层

这个模块的职责和 `planner_runtime_langchain.py` 类似，但作用域只在 grounding retrieval，而不是生成完整 `AgentPlan`。

#### `backend/services/grounding_service.py`

职责调整为：

- 协调 retrieval pack 的生成
- 基于 retrieval pack 执行 provider-aware 搜索
- 聚合 candidates
- 在 retrieval pack 失败或结果稀疏时执行 deterministic fallback

它不再是 brief understanding 的主要拥有者。

#### `backend/models/agent.py`

扩展 `AgentGroundingSummary`，在保持现有字段可用的前提下，新增 retrieval planning 痕迹，例如：

- `assumptions`
- `queryPlan`

这样后续 candidate ranking、debug、用户解释都能复用这一层信息。

#### `backend/services/agent_session_service.py`

调用入口保持基本不变：

- `add_user_message(...)` 仍在当前 grounding 时机触发搜索
- `_apply_grounding_to_session(...)` 仍写回 `grounding_summary_json`

它只需要消费增强后的 grounding summary，不需要承担 retrieval 理解逻辑。

## Structured Contract

### `RetrievalQueryPack`

建议新增一个独立 contract，而不是把结构直接塞进 `AgentGroundingSummary`：

- `productName: str`
- `audience: str`
- `styleHint: str`
- `featureHints: list[str]`
- `assumptions: list[str]`
- `queries: list[RetrievalQuery]`

### `RetrievalQuery`

每条 query 需要保留最小但足够稳定的语义：

- `text: str`
- `intent: Literal["brand_exact", "product_demo", "feature_workflow", "stock_fallback"]`
- `providers: list[str]`
- `priority: int`

这份 contract 的目标不是做通用信息抽取，而是服务 grounded candidate retrieval。

## Query Planning Strategy

### Query Tiers

推荐把 query 分成四层，从最窄到最宽：

1. `brand_exact`
   - 用于品牌名、产品名、官方称呼
   - 例如：`notion ai`, `figma slides`, `linear app`

2. `product_demo`
   - 用于产品 walkthrough、official demo、product overview
   - 例如：`notion ai demo`, `figma slides walkthrough`

3. `feature_workflow`
   - 用于功能和使用场景
   - 例如：`team docs collaboration interface`, `project planning workflow`

4. `stock_fallback`
   - 用于无强品牌素材时的广义兜底
   - 例如：`software dashboard laptop`, `team productivity workspace`

### Provider Preferences

建议用轻量策略，而不是复杂打分系统：

- `youtube`
  - 更偏好 `brand_exact` 和 `product_demo`
- `pexels`
  - 更偏好 `feature_workflow` 和 `stock_fallback`
- `fixture`
  - 继续作为开发/测试环境下的稳定兜底

这并不要求同一条 query 只能给一个 provider，但需要允许 query 表达“优先尝试谁”。

### Execution Order

建议按“query priority -> provider preference -> fallback”执行，而不是所有 provider 吃所有 query：

1. 先跑高优先级 `brand_exact / product_demo`
2. 若结果不足，再扩到 `feature_workflow`
3. 若结果仍不足，再跑 `stock_fallback`
4. 若 LangChain retrieval pack 失败，回退到当前 deterministic `_build_search_queries(...)`

## Grounding Summary Direction

为了保持前端兼容，`AgentGroundingSummary` 仍保留：

- `productName`
- `audience`
- `styleHint`
- `featureHints`
- `searchQueries`
- `candidates`
- `selectedCandidateIds`

新增信息建议为：

- `assumptions: list[str]`
- `queryPlan: list[dict]`

其中：

- `searchQueries` 继续作为前端和旧逻辑的平面兼容字段
- `queryPlan` 作为未来 ranking、解释和 debug 的增强字段

## Failure Handling and Fallback

这一阶段建议显式保留 deterministic fallback。

原因：

1. retrieval pack 是 grounding 入口，失败会直接卡住候选确认
2. 当前目标是提升检索效果，不是测试“模型失败时产品如何报错”
3. 本地无 key 环境和 CI 更适合保留可运行路径

推荐策略：

1. LangChain 成功：
   - 使用 `RetrievalQueryPack`
   - 记录 `queryPlan`
2. LangChain 失败：
   - 记录一次 retrieval planning fallback 痕迹
   - 回退到当前规则式 `parse_brief + _build_search_queries`
3. LangChain 成功但候选不足：
   - 先扩低优先级 query
   - 仍不足时再使用 deterministic fallback queries

这一层要追求的是：

> “先尽量搜对，再保证总能搜到点东西。”

## Testing Strategy

这一阶段应优先做 focused tests，而不是端到端 UI 测试。

建议覆盖：

1. `RetrievalQueryPack` 结构化输出与归一化
2. `GroundingService` 能把 `queryPlan` 正确投影成 `searchQueries`
3. provider-aware query 执行顺序正确
4. LangChain retrieval planning 失败时会回退到 deterministic query 逻辑
5. grounding summary 会持久化 `assumptions` 与 `queryPlan`
6. 现有 `/workspace` grounding confirmation API 仍可读取兼容字段

推荐测试位置：

- `tests/test_grounding_service.py`
- `tests/test_agent_api_p0.py`
- 如需 runtime 单测，可新增 `tests/test_grounding_planner_runtime.py`

## Acceptance Criteria

1. 同一条用户 brief 不再只生成一串平铺 query，而是生成带意图分层的 query plan
2. grounding 搜索能够根据 query intent 调整 provider 使用顺序
3. `AgentGroundingSummary` 能保留 `assumptions` 与 `queryPlan`
4. 现有前端仍能继续使用 `searchQueries` 与 `candidates`
5. retrieval planning 失败不会阻断 grounded workflow，而会走 deterministic fallback
6. 本阶段不引入新的用户可见 UI 面

## Resolved Decisions

这一阶段有几个明确结论：

1. 优先解决检索效果，而不是先做用户可见理解卡
2. 先加 retrieval query pack，不顺手做 ranking
3. 允许这一步保留 deterministic fallback
4. retrieval query planning 独立成新的小层，而不是继续把 query 规则堆进 `GroundingService`

它在整个 model-driven agent roadmap 里的位置，是：

> 把 grounded workflow 最前面的“找对产品画面”这一步，先变得像是一个真正理解了 brief 的系统。

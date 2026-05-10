# Structured Execution Diagnostics Design

Date: 2026-05-09

## Context

ClipForge 的 model-driven agent plan 已经推进到 Phase 4：当搜索/下载发生可重试失败时，worker 可以写入 execution feedback，planner runtime 也已经能基于失败反馈重写检索 query 并自动创建后继计划版本。

但当前这条闭环仍然偏“字符串驱动”：

- worker 主要把失败压成 `failureReason`
- planner runtime 再靠字符串分类去判断应该如何重写 query
- `failedSceneIds` 虽然已经能传递，但还缺少更稳定的结构化 diagnostics

这会让后续无论是 deterministic planner 还是 LangChain/OpenAI planner，都继续依赖脆弱的文本启发式，而不是读取统一的诊断契约。

## Problem

现在的问题不是“能不能重规划”，而是“重规划输入是否足够结构化”。

如果继续只靠 `failureReason`，会有三个明显后果：

1. 不同 provider 的错误会被折叠成同一种文本，planner 很难判断真实失败原因。
2. 失败场景、provider 级信息、可重试性、以及是否属于平台限制，无法被稳定表达。
3. 后面接 LangChain 时，planner prompt 里会堆越来越多字符串规则，逐步失去可测试性。

## Goal

建立一份统一的 **structured execution diagnostics** 契约，让 worker 侧的失败信息可以更稳定地进入 planner，并为后续 LangChain planner 提供可结构化消费的输入。

这一阶段要做到：

1. execution feedback 不再只靠一条 `failureReason` 传语义
2. worker 可以传递 scene-level / provider-level diagnostics
3. planner runtime 能基于结构化字段做重规划，而不是只解析文本
4. deterministic runtime 和未来 LangChain runtime 共用同一份 feedback contract

## Non-Goals

这一阶段不做：

- 不重写 provider 搜索/下载实现
- 不改变 job queue、Celery、session 状态机
- 不新增数据库表或字段
- 不做通用 agent tool orchestration
- 不解决所有 provider 的错误归一化问题到最终形态
- 不替换现有 execution feedback replan 的整体流程

## Recommended Approach

采用 **结构化 feedback contract + 渐进式归一化** 的方式。

核心思路是：

- 在 `SearchExecutionFeedback` 中加入少量稳定字段
- worker 侧把失败归一化成结构化 diagnostics
- planner runtime 优先读取结构化字段，文本 `failureReason` 只做 fallback
- LangChain/OpenAI planner 以后直接复用这份 contract

## Approaches Considered

### Approach A: 继续靠 `failureReason` 字符串

优点：

- 最省事
- 兼容当前实现

缺点：

- 语义不稳定
- provider 间不可比较
- 后续模型 prompt 继续膨胀

不推荐。

### Approach B: 增加轻量 structured diagnostics contract

优点：

- 改动小
- 对 deterministic 和未来模型 runtime 都友好
- 能立即减少字符串启发式依赖

缺点：

- 仍需一定的归一化规则
- 不是最终 provider diagnostics 平台

推荐。

### Approach C: 全面 provider diagnostics normalization 层

优点：

- 长期最整洁
- provider 语义最统一

缺点：

- 范围更大
- 容易把这一步拖成 provider 架构重构

暂不做。

## Recommended Direction

采用 **Approach B**：

> 先把 execution feedback schema 结构化，再让 worker 和 planner 分别只负责自己那一层的归一化与消费。

## Proposed Contract

建议在现有 `SearchExecutionFeedback` 基础上补充以下字段：

- `failureCategory`
  - 统一分类，如 `platform_blocked`、`no_inventory`、`download_transient`、`generic_retry`
- `primaryProvider`
  - 触发失败的主 provider，如 `youtube`、`pexels`、`fixture`
- `providerDiagnostics`
  - provider 级摘要列表，保留每个 provider 的简短错误说明
- `sceneDiagnostics`
  - scene 级结构化信息，至少包含 scene id、是否可重试、以及简短摘要
- `retryStrategyHint`
  - 给 planner 的重写方向提示，例如 `stock_footage_fallback`、`inventory_broaden`、`candidate_alternative`

其中：

- `failureReason` 保留，作为兼容和 debug fallback
- `failedSceneIds` 保留，作为最基本的 scene 粒度索引
- 新字段不要求一次填满所有 provider 信息，允许逐步增强

## Data Flow

1. worker 在素材搜索/下载失败后捕获异常
2. worker 提取 scene ids、provider 名称、可重试性、分类信息
3. worker 组装 `SearchExecutionFeedback`
4. `PlannerOrchestrator` 持久化 observation，并将结构化 feedback 传给 planner runtime
5. deterministic planner 使用 `failureCategory` 和 `retryStrategyHint` 进行 query rewrite
6. 未来 LangChain planner 直接读取同一份 contract，不再依赖字符串拼接

## Planner Behavior

planner 侧应遵循以下优先级：

1. 优先读取 `failureCategory`
2. 再读取 `retryStrategyHint`
3. 只有在缺少结构化字段时，才回退到 `failureReason` 文本分类

这样可以保证：

- 新老数据兼容
- deterministic runtime 可控
- 未来模型 runtime prompt 更短、更稳

## Error Handling

如果结构化 diagnostics 缺失或不完整：

- planner 仍然允许执行保守 fallback
- 不因 diagnostics 缺失直接阻断 replan
- worker 只要能给出 `failedSceneIds` 和 `failureReason`，流程仍可继续

也就是说，这个契约是“增强信号”，不是硬门禁。

## Testing Strategy

建议覆盖三层：

1. model tests
   - `SearchExecutionFeedback` 新字段默认值与兼容性
2. worker tests
   - 失败异常能被归一化成结构化 diagnostics
3. planner tests
   - deterministic runtime 优先用 structured diagnostics 做 rewrite
   - 缺字段时仍能回退到旧逻辑

## Success Criteria

当这一步完成时：

- execution feedback 不再只是“一个错误字符串”
- planner 具备稳定的结构化输入层
- deterministic 和 OpenAI/LangChain runtime 共用同一份反馈契约
- 后续的 agent plan 演进可以继续往 model-driven 方向走，而不是继续堆字符串规则

## Out of Scope for This Phase

- provider 统一错误码体系
- 全量 diagnostics 仪表盘
- 失败自动分析 UI
- 多轮自动重试策略编排

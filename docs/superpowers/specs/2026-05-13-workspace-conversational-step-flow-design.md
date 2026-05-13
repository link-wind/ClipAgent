# Workspace Conversational Step Flow Design

Date: 2026-05-13

## Background

ClipForge 当前的 `/workspace` 已经具备可用的方案沟通主链：

1. 用户输入 brief
2. 后端创建 session 并持续推进 planning / execution
3. 前端可以展示主对话、方案内容、步骤状态和结果

但当前的步骤区表达仍然偏“状态面板”：

- 步骤列表会一次性全部出现
- 当前步骤主要通过状态高亮体现
- 总进度条依赖 session progress，但缺少更细粒度的步骤推进感
- 步骤卡片更像系统状态，而不像 agent 在对话里持续同步进展

这会带来一个体验落差：

> 用户正在和 agent 沟通方案，但右侧步骤区看起来像独立的技术状态面板，而不是 agent 工作过程的一部分。

用户已经明确确认的方向是：

1. 保留当前“主对话 + 步骤区”的分区结构
2. 步骤卡片需要按顺序出现，而不是一次性全部渲染
3. 顶部总进度条需要动态增长
4. 每张步骤卡片内部也要有自己的动态进度条
5. 步骤卡片的语气应该像 agent 的回复

## Problem

当前 `/workspace` 步骤区的核心问题不是功能缺失，而是表达方式不够产品化：

1. 步骤面板一次性摊开所有步骤，削弱了“agent 正在推进工作”的过程感
2. 只有总进度，没有步骤内进度，用户难以感知当前步骤是否真的在推进
3. 卡片文案更像阶段标签和静态 summary，而不是 agent 的实时回执
4. 步骤区和主对话区之间的气质割裂，交互上像两个系统拼在一起

## Goal

把 `/workspace` 的步骤区升级为“会说话的 agent 步骤回复流”，同时保持现有整体结构稳定。

这一阶段要做到：

1. 保留当前左右分区布局
2. 主对话区继续承担用户输入、方案沟通、方案确认和结果入口
3. 右侧步骤区改造成按顺序追加的 agent 回复卡片流
4. 顶部总进度条随 session 阶段推进动态增长
5. 当前步骤卡片内部展示步骤级进度条
6. 已完成步骤保留沉淀状态，未开始步骤不提前完整出现

产品目标是：

> 用户应该感觉 agent 正在一边和自己沟通，一边持续汇报当前工作推进，而不是单独盯着一块冷静的状态面板。

## Non-Goals

这一阶段明确不做：

- 不改成单栏聊天布局
- 不把步骤卡片彻底并入主对话消息流
- 不重做 `/workspace` 的整体信息架构
- 不新增新的后端 planning phase
- 不新增新的 execution phase
- 不改动 session / event / plan 的外部 API contract
- 不做复杂动画编排或时间轴播放器式交互
- 不在这一阶段重做结果区、失败诊断区或 grounding UI

这一阶段只解决：

> “在保留现有结构的前提下，让步骤区更像 agent 正在逐步回复和推进工作。”

## Approaches Considered

### Approach A: Keep Split Layout, Turn Steps Into Agent Replies

做法：

- 保留当前左右分区
- 左侧继续是主对话与方案内容
- 右侧步骤区改造成 conversation-style step cards
- 每完成一步，才出现下一张步骤卡片
- 顶部展示总进度条，当前步骤卡片内部展示步骤进度条

优点：

- 改动边界最稳
- 不会打散现有确认流和执行流
- 结构上仍然像工作台，适合产品当前阶段
- 交互感明显增强

缺点：

- 对话感不如“全并入聊天流”那么强
- 仍然存在左右分区的结构边界

这是确认采用的方案。

### Approach B: Merge Step Cards Into Main Chat

做法：

- 把步骤卡片直接当作主对话的一部分
- 用户消息、agent 消息、步骤回执、确认动作都放进同一条聊天流

优点：

- 对话感最强
- 叙事更完整

缺点：

- 需要更大范围重组 `/workspace`
- 容易影响现有方案确认、执行信息和结果入口
- 本阶段实现风险更高

这一阶段不采用。

## Recommended Direction

采用 **Approach A: Keep Split Layout, Turn Steps Into Agent Replies**。

核心原则：

> 保持现有页面骨架稳定，只把步骤区从“状态列表”升级为“agent 回执流”。

## Scope Decisions

这一阶段的关键范围决策如下：

1. **布局不改骨架**
   - 保留现有左右分区
   - 左侧是主对话与方案内容
   - 右侧是步骤区

2. **步骤卡片按顺序出现**
   - 只展示已经开始或已经完成的步骤
   - 未开始步骤不完整渲染
   - 可以保留一个轻量占位，提示“下一张卡片会在当前步骤完成后出现”

3. **双层进度表达**
   - 页面顶部保留总进度条
   - 每张步骤卡片内部显示该步骤自己的进度条
   - 已完成步骤固定为 100%
   - 当前步骤展示动态百分比
   - 未开始步骤展示 0% 或不展示内部进度条

4. **卡片文案偏 agent 回复**
   - 每张卡片不是只写标题 + summary
   - 需要更像“我正在做什么 / 我刚刚完成了什么 / 接下来会发生什么”

5. **状态沉淀要清晰**
   - 已完成步骤保留为沉淀卡片
   - 当前步骤保持高亮
   - 失败态后续沿用现有失败语义，本阶段只保证结构可兼容

## User Experience

### Left Pane: Main Conversation Stays Stable

左侧继续保留当前主要职责：

- 用户输入 brief
- 用户继续补充 / 修改方案方向
- agent 给出高层回应
- 展示当前方案草稿或最终方案摘要
- 提供“确认方案”等关键动作

用户对 `/workspace` 的核心认知不变：

> 左边负责“我和 agent 怎么聊”，右边负责“agent 正在怎么推进”。

### Right Pane: Step Reply Stream

右侧步骤区改造成 agent 的步骤回复流：

- 每张卡片代表一个真实步骤
- 卡片出现顺序与步骤执行顺序一致
- 已完成步骤显示完成状态和完成后的回执文案
- 当前步骤显示进行中状态和步骤内进度条
- 未开始步骤不提前完整露出

卡片文案示例：

- `我已经确认这次的核心目标是 30 秒产品介绍短片，重点是快速建立产品认知。`
- `当前约束是时长短、信息密度高，所以我会优先采用更直接的功能表达。`
- `我正在对比多个方案方向，并根据你刚才的补充继续收敛。`

### Progress Model

用户将同时看到两层进度：

1. **总进度**
   - 位于步骤区顶部
   - 表示整个 planning / execution 当前推进到哪里

2. **步骤进度**
   - 位于单张步骤卡片内部
   - 表示当前步骤自身推进到了哪里

这两层的关系应该是：

- 总进度负责全局节奏感
- 步骤进度负责当前工作仍在真实推进的细节感

### Visibility Rules

步骤区的展示规则建议如下：

1. 已完成步骤：显示完整卡片 + 100% 进度
2. 当前步骤：显示完整卡片 + 动态步骤进度 + 高亮
3. 未开始步骤：
   - 默认不完整展示
   - 可选保留一个轻量 placeholder，提示“下一张卡片将在当前步骤完成后出现”

这样可以保证：

- 用户始终感到工作是逐步展开的
- 页面不会因为一开始就堆满所有步骤而显得“剧透式”

## Data And Mapping

### Existing Data Reused

本阶段尽量复用现有字段：

- `session.status`
- `session.progress`
- `session.currentStep`
- `session.steps`
- 已有步骤的 `status / progress / summary / result`

目标是：

> 优先通过前端 read model 改造完成表达升级，而不是先改后端 contract。

### Frontend Read Model

前端需要把现有步骤数据重新映射成更适合 UI 的结构，例如：

```ts
type ConversationalStepCard = {
  id: string
  title: string
  status: 'pending' | 'running' | 'succeeded' | 'failed'
  progress: number
  message: string
  note?: string | null
  visible: boolean
  isCurrent: boolean
}
```

核心是新增两层前端语义：

1. `visible`
   - 控制这张卡片是否应该出现

2. `message`
   - 把原本偏 summary/result 的内容改写为更像 agent 回复的展示文案

### Progress Mapping

建议的进度映射规则：

1. `session.progress` 继续作为顶部总进度的主要来源
2. 单步卡片优先使用 step 自身的 `progress`
3. 若 step 处于 `pending` 但实际是当前激活阶段，需要允许一个合理 fallback
4. `succeeded` 步骤强制显示 100%
5. `pending` 步骤若可见，占位卡片显示 0%

## Component Design

### `AiStepFlow`

`AiStepFlow` 将继续作为步骤区主组件，但职责要变化：

当前职责偏：

- 固定渲染整个步骤列表
- 用 active / complete 样式区分状态

新职责应变为：

1. 根据 session 计算“哪些卡片现在可见”
2. 计算总进度
3. 计算每张卡片的步骤进度
4. 输出 conversation-style cards
5. 兼容 planning 和 execution 阶段的不同步骤集合

### Supporting Helpers

建议抽出若干纯函数，避免 `AiStepFlow.tsx` 再次膨胀：

- `getVisibleSteps(session)`
- `buildConversationalStepMessage(step, session)`
- `getStepCardProgress(step, session)`
- `getTotalProgress(session)`

这些 helper 应尽量保持纯函数化，方便单测覆盖。

## Visual Design

### Overall Tone

步骤区的视觉气质应从“控制台状态列表”转向“agent 工作回执卡片”：

- 卡片有明确层次，但不过度装饰
- 当前步骤比已完成步骤更突出
- 进度条存在感清晰，但不能喧宾夺主
- 文案阅读感要接近聊天消息，而不是监控面板

### Step Card Anatomy

每张步骤卡片建议包含：

1. 标题
2. 状态 tag
3. agent 风格主文案
4. 步骤内进度条
5. 可选 note（例如“当前步骤完成后会出现下一张卡片”）

### Motion

本阶段允许轻量过渡，但不依赖复杂动画：

- 新卡片出现时可有淡入 / 上移
- 当前步骤进度条宽度变化可平滑过渡
- 避免引入重型时间轴动画或逐字打字机效果

## Failure Handling

本阶段不重做失败体验，但步骤区需要兼容失败状态：

- 若某一步失败，该卡片应能切换到失败样式
- 总进度保留当前值，不再继续增长
- 后续失败诊断面板仍由现有失败区承载

换句话说：

> 步骤区只保证失败时结构不崩，并能把“失败发生在哪一步”表达清楚。

## Testing

### Frontend Contract Tests

需要补充前端 contract 级测试，重点覆盖：

1. 步骤卡片不会一次性完整渲染所有步骤
2. 当前步骤之前的卡片显示为已完成
3. 当前步骤卡片显示步骤内进度条
4. 已完成步骤卡片显示 100%
5. 占位卡片或未开始策略符合最终实现约定
6. 文案中存在 agent 风格的回执表达，而不仅是原始 summary

### Build Verification

实现完成后至少需要运行：

1. `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend`
2. `npm run build`

如果改动涉及 `/workspace` 的特定 contract 文本，测试可以先从更小粒度的前端 contract 用例入手，再补全量验证。

## Rollout Plan

建议按以下顺序实现：

1. 先重构 `AiStepFlow` 的 read model 和 helper
2. 再改 JSX 结构，让卡片支持“只显示可见步骤”
3. 再补总进度与步骤内进度条
4. 再补文案风格和占位卡片
5. 最后补测试和 build 验证

这样能把风险控制在步骤区内部，不打散现有 `/workspace` 主流程。

## Open Question Resolved

本次设计过程中用户已经明确确认：

- 不采用“全部并入聊天流”的方案
- 直接采用保守的 split layout 方案
- 需要在步骤卡片内部也体现动态进度条

因此本设计没有待确认的主方向分歧，下一步可以直接进入 implementation plan。

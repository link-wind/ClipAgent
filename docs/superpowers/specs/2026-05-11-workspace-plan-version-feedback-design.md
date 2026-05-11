# Workspace Plan Version Feedback Design

## Background

`/workspace` 现在已经具备一条真实可运行的 user revision 主链：

1. 用户在方案已生成的会话里继续发送消息。
2. `AgentSessionService.add_user_message(...)` 检测到已有 plan 后，走 `PlannerOrchestrator.persist_user_revision_replan(...)`。
3. planner runtime 生成新的 immutable `AgentPlan / ExecutionPlan` 版本，并把 `session_record.current_plan_id` 切到最新 plan。
4. `AgentReadService.read_session(...)` 返回最新 session，前端 `BriefWorkspacePage` 直接 `setSession(nextSession)`。

这条链路在后端已经是真实落库的，并不是前端本地拼接出来的假状态。

但当前 `/workspace` 页面缺少一个清晰、稳定的反馈信号，告诉用户：

- 这次补充的 revision 是否真的生成了新的 plan version
- 当前页面显示的 plan 是否已经和数据库中的 current plan 对齐

于是页面虽然会刷新 plan 内容，但用户只能“看起来像变了”，不能明确知道“计划已经根据我的修改更新成功”。

## Problem

当前问题不在于 planner 不能重规划，而在于 `/workspace` 缺少一个最小但可信的 plan version feedback contract：

1. `AgentSession` 响应里没有 current plan version，前端无法明确判断 revision 是否生成了新版本。
2. `/workspace` 只能依赖 `session.plan` 内容变化来猜测是否更新成功，这对恢复会话、未来版本追踪和异常排查都不够稳。
3. 页面没有一条轻量但明确的“计划已更新”反馈，因此 revision 成功后的体验不够产品化。

这一阶段要解决的是：

> 让 `/workspace` 在用户发送 revision 后，能够基于真实 plan version 判断并反馈“计划已更新”。

## Goal

这一阶段的目标是：

> 为 `/workspace` 建立一个最小闭环 contract，让前端能依据真实 `currentPlanVersion` 感知 user revision replan 已完成，并立即显示更新后的 plan。

这一阶段要做到：

1. 后端 `AgentSession` 返回 `currentPlanVersion`。
2. `currentPlanVersion` 对应 session 当前指向的 current plan，而不是前端猜测的“最新看起来像 plan 的内容”。
3. `/workspace` 在已有 plan 的会话中发送 revision 成功后，如果版本号递增，显示“已根据你的修改更新计划”。
4. 页面继续使用返回的新 `session.plan` 直接刷新最终方案区，不依赖额外轮询来完成这次更新反馈。
5. 这条反馈只在真实产生新 plan version 时出现，不因为消息发送成功就误报。

## Non-Goals

这一阶段明确不做：

- 不展示 plan version 历史
- 不新增 plan diff 或对比视图
- 不展示 `changeSummary`
- 不展示 `plannerTrace`
- 不把 revision replan 改造成新的事件流 UI
- 不新增 toast、弹窗或全局通知中心
- 不改 `/workspace` 的单栏主体结构
- 不扩展 task execution、search、render 相关流程

这一阶段只解决：

> “用户修改方案后，页面如何基于真实 plan version 立即、可信地反馈计划已经更新。”

## Approaches Considered

### Approach A: Pure Frontend Detection

做法：

- 不改后端 contract
- 前端只比较 `session.plan` 内容或消息返回时机
- 若收到新 session，则直接显示“计划已更新”

优点：

- 改动最小
- 前端实现最快

缺点：

- 无法证明是否真的生成了新 plan version
- 容易把“消息提交成功”和“计划已经落到新版本”混在一起
- 后续恢复会话或版本跟踪时，判断基础不稳

这一阶段不推荐。

### Approach B: Minimal Plan Version Contract

做法：

- 后端 `AgentSession` 新增 `currentPlanVersion`
- 前端在发送 revision 前记录当前版本
- 返回成功后仅在版本号递增时显示“已根据你的修改更新计划”

优点：

- 改动很小，但判断依据是真实持久化状态
- 能把 revision replan、plan persistence、前端刷新串成一个可信闭环
- 为后续版本对比、恢复会话、调试追踪保留良好基础

缺点：

- 需要同时改后端 response model 和前端状态判断

这是推荐方案。

### Approach C: Full Revision Status Stream

做法：

- 为 revision replan 单独增加事件和步骤反馈
- 前端展示“正在重规划 -> 已更新计划”

优点：

- 体验最完整
- 更接近长期 agent workflow 形态

缺点：

- 范围明显大于当前基础版目标
- 会把这一阶段从“闭环 contract”扩成“新交互系统”

这一阶段不推荐。

## Recommended Direction

采用 **Approach B: Minimal Plan Version Contract**。

核心原则：

> 页面上的“计划已更新”必须建立在真实 current plan version 递增之上，而不是建立在前端主观推断之上。

这能在不显著增加产品复杂度的前提下，把 `/workspace` revision feedback 做成一条可靠的产品闭环。

## Scope Decisions

这一阶段的关键范围决策如下：

1. **新增字段只做最小化**
   - 只新增 `currentPlanVersion`
   - 不额外新增 `currentPlanId`、`previousPlanVersion`、`changeSummary` 等字段

2. **版本号必须对应 current plan**
   - 读取 session 时，版本号语义是“当前 session 正在使用的 plan 版本”
   - 不是“该 session 下最大 version 的 plan”，除非两者本来就是同一条

3. **提示只在 revision path 中触发**
   - 页面已有 plan 时发送用户消息，才进入“版本是否递增”的判断
   - 初始建 plan、grounding confirm、执行阶段轮询都不显示这条提示

4. **提示是内联状态，不是全局通知**
   - 提示直接放在最终方案区附近
   - 不做 toast，不打断当前单栏流程

## Architecture

### Backend Contract Layer

受影响层：

- `backend/models/agent.py`
- `backend/services/agent_read_service.py`
- 如有必要，补充对应 API contract 测试与 persistence/service 测试

后端职责：

1. 在 `AgentSession` response model 中新增 `currentPlanVersion: int | None`
2. 在 `read_session(...)` / `build_session_response(...)` 中填充该字段
3. 返回的 `currentPlanVersion` 必须与当前返回的 `plan` 对应同一条 current plan

关键约束：

- `session_record.current_plan_id` 存在时，应优先以它定位 current plan version
- 不能简单把 “latest plan version” 当作 current plan version 的唯一来源
- 当 session 尚未生成 plan 时，返回 `null`

### Frontend Feedback Layer

受影响层：

- `src/lib/agentApi.ts`
- `src/components/workspace/BriefWorkspacePage.tsx`

前端职责：

1. 接收 `currentPlanVersion`
2. 在已有 plan 的 session 中发送 revision 前，记录发送前版本
3. 消息提交成功后，比较 `nextSession.currentPlanVersion` 与发送前版本
4. 仅在新版本号严格递增时，显示“已根据你的修改更新计划”
5. 始终使用返回的 `nextSession.plan` 直接刷新 UI

## Detailed Design

### Backend Session Response

`AgentSession` 新增字段：

- `currentPlanVersion: int | None`

语义：

- `null`：当前会话还没有 plan
- 正整数：当前会话正在使用的 plan version

填充规则：

1. 若 `session_record.current_plan_id` 为空，则返回 `null`
2. 若 `session_record.current_plan_id` 存在，则读取对应 `AgentPlanRecord`
3. `plan` 字段与 `currentPlanVersion` 必须来自同一条 current plan

实现建议：

- `AgentReadService` 不应再只依赖 `load_latest_plan(...)`
- 需要显式区分：
  - latest plan for session
  - current plan pointed by `session_record.current_plan_id`

如果当前代码路径上这两者通常相同，也仍然应按 current plan 语义来构建 response，避免未来出现“最新版本”和“当前使用版本”脱钩时 contract 失真。

### Frontend Revision Feedback

`BriefWorkspacePage` 新增轻量本地状态即可，不需要改全局 Zustand 结构。

推荐新增本地状态：

- `pendingRevisionBaseVersion: number | null`
- `showPlanUpdatedNotice: boolean`

交互规则：

1. 用户发送消息前：
   - 若当前 session 已有 plan 且 `currentPlanVersion` 为数字，则记录该版本为 base version
   - 否则不进入 revision success 提示判断

2. 请求成功后：
   - `setSession(nextSession)`
   - 若存在 base version，且 `nextSession.currentPlanVersion > base version`，显示提示
   - 否则不显示提示

3. 提示清理：
   - 切换到新 session 时清理
   - 进入执行态（如 `queued/searching/downloading/rendering`）时可隐藏
   - 请求失败时不显示提示

展示位置：

- 放在最终方案区顶部或标题附近
- 文案固定为：`已根据你的修改更新计划`

这条提示是“当前 plan 已切到新版本”的确认，不承担解释修改内容的责任。

## Edge Cases

1. **初始建 plan**
   - 首次创建 session 并生成 plan 时，不显示这条 revision update 提示

2. **Grounding confirmation**
   - 候选画面确认虽然也可能生成新 plan version，但不属于本阶段的 revision success 提示范围

3. **Request failure**
   - 若 `sendAgentMessage(...)` 失败，保留现有错误提示，不显示 update notice

4. **Session restore**
   - 恢复旧会话时，只展示当前 session 返回的数据
   - 不因为当前版本号大于本地历史值就推断“刚刚更新过”

5. **Version not incremented**
   - 若 revision 请求成功，但 `currentPlanVersion` 没有递增，则前端不显示 success notice
   - 这意味着后端 contract 或 planner persistence 存在异常，页面应避免误报

6. **Execution polling**
   - 执行阶段的 session 轮询不应反复触发这条 revision success 提示

## Testing Strategy

### Backend Tests

重点覆盖：

1. 初始计划创建后，session response 返回 `currentPlanVersion = 1`
2. user revision replan 后，session response 返回递增后的 version
3. session response 中的 `plan` 与 `currentPlanVersion` 对应同一条 current plan

建议优先补在这些测试附近：

- `tests/test_agent_persistence.py`
- `tests/test_agent_backend.py`

测试重点不是单独证明字段存在，而是证明这个字段与 current plan persistence 语义一致。

### Frontend Contract Tests

当前仓库前端 contract 主要通过 Python 测试检查源码约束，因此本阶段应延续现有模式，而不是额外引入新的前端测试框架。

建议补充源码 contract 断言，至少覆盖：

1. `AgentSession` TS 类型包含 `currentPlanVersion`
2. `BriefWorkspacePage.tsx` 存在发送前记录 base version 的逻辑
3. `BriefWorkspacePage.tsx` 仅在 `nextSession.currentPlanVersion > baseVersion` 时显示“已根据你的修改更新计划”
4. 成功后继续直接 `setSession(nextSession)`，不引入额外轮询依赖

建议落点：

- `tests/test_agent_backend.py`

## Acceptance Criteria

以下条件全部满足时，这一阶段算完成：

1. 用户在 `/workspace` 中打开一个已有 plan 的会话
2. 用户继续发送一条 revision 消息
3. 后端成功生成新的 immutable plan version，并把 session current plan 切到该版本
4. API 返回的 session 包含递增后的 `currentPlanVersion`
5. 前端无需手动刷新，立即展示新的 `session.plan`
6. 页面在最终方案区显示“已根据你的修改更新计划”
7. 若没有真实生成新 version，则不显示该提示

## Rollout Notes

这是一个很小但关键的 contract 收口阶段，适合优先完成。

完成后，系统会获得一个更扎实的基础：

- 用户能明确知道 revision 已成功写入新的 plan version
- `/workspace` 不再只是“看起来更新了”，而是“确认 current plan 已更新”
- 后续若要做 version history、change summary 或 planner trace 可视化，可以建立在同一套 plan version contract 之上继续扩展

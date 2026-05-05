# ClipForge Dashboard Tailwind Home Design

## Background

ClipForge 当前已经具备三页产品结构雏形：

1. Dashboard 首页
2. `/workspace` 方案沟通页
3. `/tasks` 任务管理页

但当前首页仍更接近开发工作台或内部工具视角。虽然它已经展示了关键指标、趋势、资产构成和最近任务，但整体表达顺序更像“系统现在有哪些模块”，而不是“ClipForge 是什么产品，以及它如何帮助用户持续产出视频”。

同时，当前前端样式体系主要依赖 CSS Modules。项目下一阶段希望逐步引入 Tailwind CSS，但不适合在一次改动里把全部页面和全部组件一起迁移。

因此，这一轮应聚焦一个足够完整、又风险可控的切口：

- 只重做 Dashboard 首页
- 首页整页迁移到 Tailwind
- 其余页面和现有 CSS Modules 暂时保留

这样既能把产品门面先立起来，也能为后续页面迁移建立 Tailwind 的实际落地模式。

## Goals

1. 把首页从“开发工作台”重构为更成熟的产品首页。
2. 让首页第一屏先说明 ClipForge 是什么产品，再展示系统运行状态。
3. 保留当前 dashboard 数据契约，不新增后端字段。
4. 在首页范围内完整引入 Tailwind CSS。
5. 保持 `/workspace` 与 `/tasks` 页面暂不迁移，控制本轮改动范围。

## Non-Goals

- 本轮不重做 `/workspace` 页面。
- 本轮不重做 `/tasks` 页面。
- 本轮不改动 dashboard API 返回结构。
- 本轮不做全站 CSS Modules 到 Tailwind 的迁移。
- 本轮不引入新的后端业务模块、图表服务或设计系统框架。

## Chosen Direction

本轮首页采用以下组合方向：

- 视觉气质：`Editorial Ops`
- 信息结构：`Overview First`
- 首屏表达：`Product Identity`

这意味着首页第一屏的任务不是先像监控台一样展示队列，而是先建立对 ClipForge 的产品认知：

- 它是一个面向短视频生成与推进的产品化工作台
- 用户可以从这里进入新方案创建
- 首页下方的数据和趋势是产品正在工作的证据，而不是首页自我介绍的主体

相较于“Queue First”或“Operator Desk”方向，这个组合更适合作为产品门面，也更符合“产品感优先”的阶段目标。

## Product Positioning On Home

首页首屏应清楚传达以下认知：

> ClipForge 是一个对话式短视频制作工作台，用于把创意 brief 推进成可执行方案、任务流程和最终产出。

这个定位需要通过页面结构共同完成，而不是只靠一句 marketing 文案。首屏里的产品名、说明文案、主按钮和右侧运行概况应一起完成这个任务。

首页不应呈现为：

- 偏监控台的内部运营界面
- 偏营销站点的 landing page
- 偏实验性质的 Agent demo

首页应呈现为：

- 可持续使用的产品首页
- 有真实运行状态的内容生产工作台
- 能自然引导用户进入下一步操作的产品入口

## Scope

本轮只覆盖：

- `src/components/dashboard/DashboardPage.tsx`
- 与 Dashboard 直接相关的样式与依赖
- Tailwind 在 Next.js 中的基础接入
- 首页结构检查与构建验证

本轮不覆盖：

- `src/components/workspace/*`
- `src/components/tasks/*`
- 全局公共组件的大规模重写
- 后端 dashboard 数据计算逻辑

## Information Architecture

Dashboard 首页采用四层结构，自上而下组织。

### 1. Product Hero

首屏承担“解释产品身份”的职责。

布局原则：

- 左侧为产品身份与行动区
- 右侧为紧凑运行概况
- 不用巨大图表占据首屏
- 不做营销站常见的夸张 hero 视觉

首屏应包含：

- 产品标题，例如 `ClipForge`
- 一句简洁产品说明，明确它与“方案推进 / 视频产出 / 工作流管理”相关
- 主按钮：`新建方案`
- 次按钮：`任务管理`
- 搜索输入或快捷入口可保留，但优先级低于产品身份与主动作
- 右侧概况卡，展示当前会话、活跃任务、完成情况等压缩信息

首屏的语气是“这是一个正在稳定工作的产品”，不是“看看我们能做什么”。

### 2. Key Metrics

第二层展示首页的核心指标卡，用于建立系统规模感与运行状态。

保留现有四项核心指标：

- 总会话
- 活跃任务
- 已完成
- 失败任务

设计要求：

- 仍使用四张并列指标卡
- 文案改为产品化描述，而非偏开发诊断说明
- 指标卡视觉需要与 hero 同属一个系统，但层级次于首屏身份区

### 3. Operational Proof

第三层用于证明 ClipForge 不是静态概念，而是在持续推进内容工作。

该层包含两部分：

- 左侧：最近 7 个任务产出走势
- 右侧：健康快照与资产构成

这里的重点不是做监控大屏，而是让用户快速回答三个问题：

1. 最近有在持续产出吗？
2. 当前运行状态稳定吗？
3. 资源主要分布在哪些内容类型上？

因此，这一层应强调清楚、克制和易扫读，而不是复杂交互。

### 4. Recent Work

底部区域展示最近工作，用更产品化的卡片或紧凑列表承接最近任务。

每项至少展示：

- 标题
- 状态
- 当前步骤
- 更新时间

它的职责有两层：

1. 让首页具备“最近发生了什么”的连续性
2. 作为进入后续流程的跳板，连接到 `workspace` 或 `tasks`

这一区域不应再像原始数据列表，而应更接近成熟产品里的 recent work 模块。

## Tailwind Introduction Strategy

本轮采用“单页完整迁移，其他页面保持不动”的渐进引入方式。

### Why This Slice

选择首页作为 Tailwind 首个完整落点，原因如下：

- 首页是产品门面，改版收益最高
- 页面边界清楚，便于独立迁移
- 现有数据依赖简单，不需要同步改动后端
- 可以在真实页面中验证 Tailwind 的组织方式，而不是只做局部试点

### Migration Boundary

本轮原则如下：

- Tailwind 接入到项目中
- `DashboardPage.tsx` 页面级结构优先改用 Tailwind class
- Dashboard 相关旧 CSS Module 允许逐步缩空或删除
- 其他页面继续使用原有 CSS Modules，不强求同步迁移

### Styling Model

首页优先使用 Tailwind 组织：

- 布局：`grid`、`flex`、间距、容器宽度
- 面板：边框、圆角、阴影、背景
- 排版：标题层级、辅助文案、标签、小字说明
- 响应式：桌面与移动端分布

若存在以下情况，可保留少量非 Tailwind 支撑：

- 第三方图形或渐变表达过于冗长
- 极少量复用型样式需要临时共存

但默认目标仍是让首页主要视觉由 Tailwind 驱动，而不是“Tailwind 点缀 + 大量旧样式未迁移”。

## Design Language

首页整体保持 `Editorial Ops` 气质。

### Tone

- 专业
- 清楚
- 低噪音
- 像成熟内容工具，而不是内部控制台

### Color

- 浅色背景为主
- 石墨灰作为主要文字与标题色
- 低饱和绿、蓝灰作为辅助色
- 错误态保留红色语义，但避免过高饱和度

### Shape And Density

- 容器圆角控制在 8px 左右
- 模块边界清楚
- 信息密度中等偏高，但不拥挤
- 首屏留出足够呼吸感，避免一上来就是数据堆叠

## Data Dependencies

本轮复用当前 dashboard 数据，不新增 API 字段。

首页继续依赖现有数据：

- `totalSessions`
- `activeTasks`
- `completedTasks`
- `failedTasks`
- `recentTasks`

静态趋势值与资产构成可先继续使用现有前端定义数据，作为页面结构的一部分保留。

本轮不处理：

- 新趋势接口
- 动态资产分析接口
- 首页跨页聚合查询优化

## Interaction Rules

首页交互保持轻量、明确。

- `新建方案` 进入 `/workspace`
- `任务管理` 进入 `/tasks`
- 搜索保留为筛选最近任务或定位会话的辅助能力
- recent work 中的任务项可进入对应流程

首页不承担：

- 深度任务管理
- 复杂筛选器组合
- 详细任务诊断

这些职责仍分别留给 `/workspace` 和 `/tasks`。

## Implementation Constraints

实现时应遵守以下约束：

1. 不修改 dashboard 数据契约来适配视觉设计。
2. 不为首页改版引入新的全局复杂抽象。
3. 不顺手重做其它两个页面。
4. Tailwind 的引入应服务于本轮页面改造，而不是附带发散成全站样式重组。

## Risks

### Tailwind And Existing Styles Coexistence

项目当前基于 CSS Modules，接入 Tailwind 后短期内会出现双体系共存。若边界不清，容易造成：

- 首页仍混杂过多旧样式
- 类名职责不清
- 后续迁移标准模糊

因此本轮必须把首页作为清晰样板页，而不是半迁移状态。

### Hero Drift

若首屏右侧运行信息过重，首页会再次滑回“控制台首页”；若首屏文案过重，又会偏成营销站。因此需要在“产品身份”与“运行概况”之间保持平衡。

### CSS Cleanup Ambiguity

旧的 `DashboardPage.module.css` 需要明确是完全退出、部分保留还是仅剩兜底样式。实现计划中应把这个决策写清楚，避免产生长期混合负担。

## Testing And Verification

本轮至少需要验证：

1. `npm run build` 通过
2. 首页在桌面和移动视口下结构稳定
3. 现有 dashboard 页面结构检查可继续工作，必要时更新断言文案
4. `/workspace` 与 `/tasks` 未因 Tailwind 接入被意外破坏

若新增 Tailwind 配置文件或 PostCSS 配置，也应确保构建链路与当前 Next.js 版本兼容。

## Success Criteria

当以下条件成立时，本轮可以认为完成：

1. 首页第一眼能明确说明 ClipForge 是什么产品。
2. 首页整体观感明显脱离开发工作台，更接近成熟产品首页。
3. 首页代码主要由 Tailwind 驱动。
4. 现有 dashboard 数据能力保持不变。
5. 其它页面未被卷入本轮迁移。

## Next Step

这份 spec 通过后，下一步只需要为该 spec 编写实施计划，聚焦：

- Tailwind 基础接入
- Dashboard 整页迁移
- 旧 Dashboard 样式清理策略
- 构建与结构验证

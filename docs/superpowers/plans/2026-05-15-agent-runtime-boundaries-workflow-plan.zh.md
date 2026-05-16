# Agent Runtime 功能边界与工作流规划实施计划

> **给 agentic workers：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步执行本计划。每一步使用 checkbox（`- [ ]`）追踪状态。

**目标：** 完成 ClipForge 下一阶段 Agent Runtime 的规划文档体系，明确功能边界、工作流程、多 Agent 预留，以及第一阶段架构基础实施计划。

**架构：** 本计划只写文档，不实现代码。文档层面先建立“垂直视频 Agent + 可插拔 RAG/Skill/MCP 能力层 + 未来多 Agent 预留”的目标架构，再把第一阶段收敛成可执行的架构边界实施计划。

**技术栈：** Markdown 文档、现有 `docs/superpowers/specs/` 与 `docs/superpowers/plans/` 目录、ClipForge 当前 Next.js/FastAPI/Celery/PostgreSQL/Redis/LangGraph/LangChain 架构上下文。

---

## 文件结构

### 本次规划文档

- Create: `docs/superpowers/specs/2026-05-15-agent-runtime-boundaries-workflow-design.md`
  - 设计规格说明，记录功能边界、核心工作流、RAG/Skill/MCP 落点、多 Agent 预留和分阶段路线。
- Create: `docs/superpowers/plans/2026-05-15-agent-runtime-boundaries-workflow-plan.zh.md`
  - 当前文档，记录这次规划工作的执行清单和文档验收标准。
- Keep: `docs/superpowers/plans/2026-05-15-agent-runtime-architecture-foundation.md`
  - 已有英文实施计划，聚焦第一阶段架构目录和兼容模块。
- Keep: `docs/superpowers/plans/2026-05-15-agent-runtime-architecture-foundation.zh.md`
  - 已有中文实施计划，作为后续真正实施 Phase 1 的主要执行文档。

### 不修改的文件

- Do not modify: `backend/**`
- Do not modify: `src/**`
- Do not modify: `tests/**`
- Do not modify: `README.md`

本轮目标是“把文档都写好”，不进入代码实现或 README 改写。

---

## 规划决策

### 决策 1: 产品定位

ClipForge 下一阶段继续定位为：

```text
面向视频生成任务的 Agent 工作流系统
```

不是：

- 通用聊天 Agent
- 一开始就完整多 Agent 平台
- 单纯 RAG demo
- 单纯 MCP tool demo

### 决策 2: 能力边界

RAG、Skill、MCP 的边界固定为：

```text
RAG = Agent 知道什么
Skill = Agent 怎么做
MCP = Agent 能调用什么
```

Planner Runtime 负责把这些能力组合成计划，但不直接承担知识检索、工具调用和执行任务。

### 决策 3: 当前阶段的实现边界

下一阶段的第一步只做 Agent Runtime Boundary：

- no-op `ContextEngine`
- default `SkillEngine`
- skipped `ToolGateway`
- no-op `TraceRecorder`
- thin `AgentRuntime`
- application/runtime/domain/infrastructure/workers 兼容包

不做真实 RAG、真实 MCP、多 Agent 调度和完整 skill registry。

### 决策 4: 多 Agent 预留

允许未来向多 Agent 演进，但当前阶段只预留概念：

- `AgentRun`
- `AgentStep`
- `AgentDecision`
- `TraceEvent.actor`
- `TraceEvent.role`

当前仍然按单 Agent Runtime 实现。

---

## Task 1: 完成设计规格文档

**Files:**
- Create: `docs/superpowers/specs/2026-05-15-agent-runtime-boundaries-workflow-design.md`

- [ ] **Step 1: 写清产品定位**

在设计文档中写明：

```text
ClipForge 是面向视频生成任务的 Agent 工作流系统。
RAG、Skill、MCP 和未来多 Agent 都服务于视频生成主线。
```

验收：

```bash
rg -n "面向视频生成任务的 Agent 工作流系统|垂直视频 Agent" \
  docs/superpowers/specs/2026-05-15-agent-runtime-boundaries-workflow-design.md
```

Expected: 能找到对应定位文字。

- [ ] **Step 2: 写清功能边界**

在设计文档中为以下模块分别写明“职责”和“不负责”：

```text
Session / Conversation
Context Engine / RAG
Skill Engine
Planner Runtime
Tool Gateway / MCP
Execution Engine
Trace / Observation
```

验收：

```bash
rg -n "Session / Conversation|Context Engine / RAG|Skill Engine|Planner Runtime|Tool Gateway / MCP|Execution Engine|Trace / Observation" \
  docs/superpowers/specs/2026-05-15-agent-runtime-boundaries-workflow-design.md
```

Expected: 每个模块标题都能匹配。

- [ ] **Step 3: 写清主工作流**

在设计文档中写入完整主工作流：

```text
用户输入 brief
Session Manager 记录消息
AgentRuntime 创建 AgentRun
ContextEngine 检索上下文
SkillEngine 选择 skill
PlannerRuntime 生成 AgentPlan + ExecutionPlan
TraceRecorder 记录决策
用户确认或修改
ExecutionEngine 创建 Job
Worker 执行
成功写 artifact 或失败写 diagnostic
失败反馈进入 repair/replan workflow
```

验收：

```bash
rg -n "用户输入 brief|AgentRuntime 创建 AgentRun|ContextEngine 检索上下文|SkillEngine 选择 skill|失败反馈进入 repair/replan workflow" \
  docs/superpowers/specs/2026-05-15-agent-runtime-boundaries-workflow-design.md
```

Expected: 主工作流关键节点都能匹配。

- [ ] **Step 4: 写清失败修复工作流**

在设计文档中写入：

```text
Worker failure
ExecutionEngine normalizes diagnostic payload
TraceRecorder records failure event
ContextEngine adds failure context
SkillEngine selects repair skill
PlannerRuntime creates repaired plan version
ExecutionEngine creates replacement job
```

验收：

```bash
rg -n "Worker failure|ExecutionEngine normalizes diagnostic payload|PlannerRuntime creates repaired plan version|replacement job" \
  docs/superpowers/specs/2026-05-15-agent-runtime-boundaries-workflow-design.md
```

Expected: 失败修复链路关键节点都能匹配。

- [ ] **Step 5: 写清 RAG/Skill/MCP 各自工作流**

在设计文档中分别写入：

```text
RAG 工作流
Skill 工作流
Tool / MCP 工作流
```

验收：

```bash
rg -n "RAG 工作流|Skill 工作流|Tool / MCP 工作流|ContextUsage|SkillRun|ToolCall" \
  docs/superpowers/specs/2026-05-15-agent-runtime-boundaries-workflow-design.md
```

Expected: 三条工作流和核心记录对象都能匹配。

- [ ] **Step 6: 写清多 Agent 预留**

在设计文档中写明当前阶段不做多 Agent 调度，但预留：

```text
AgentRun
AgentStep
AgentDecision
TraceEvent.actor
TraceEvent.role
```

并列出未来可能的 roles：

```text
SupervisorAgent
ResearchAgent
PlannerAgent
AssetAgent
DirectorAgent
RenderAgent
CriticAgent
```

验收：

```bash
rg -n "多 Agent 预留|SupervisorAgent|ResearchAgent|PlannerAgent|AssetAgent|DirectorAgent|RenderAgent|CriticAgent|TraceEvent.actor|TraceEvent.role" \
  docs/superpowers/specs/2026-05-15-agent-runtime-boundaries-workflow-design.md
```

Expected: 多 Agent 预留和未来角色都能匹配。

---

## Task 2: 对齐第一阶段架构实施文档

**Files:**
- Keep: `docs/superpowers/plans/2026-05-15-agent-runtime-architecture-foundation.zh.md`

- [ ] **Step 1: 确认第一阶段计划范围**

检查中文实施计划是否明确说明：

```text
第一阶段只做架构边界和兼容模块
不引入真实 RAG
不引入真实 MCP
不引入完整 skill registry
不改变 API response shape
```

Run:

```bash
rg -n "本阶段不增加 vector database|本阶段不增加 MCP client|本阶段不增加完整 skill registry|本阶段不改变 API response shape" \
  docs/superpowers/plans/2026-05-15-agent-runtime-architecture-foundation.zh.md
```

Expected: 所有限制都能匹配。

- [ ] **Step 2: 确认第一阶段计划包含 runtime contracts**

Run:

```bash
rg -n "ContextEngine|SkillEngine|ToolGateway|TraceRecorder|AgentRuntime" \
  docs/superpowers/plans/2026-05-15-agent-runtime-architecture-foundation.zh.md
```

Expected: 五个 runtime contract 都能匹配。

- [ ] **Step 3: 确认第一阶段计划包含验证链路**

Run:

```bash
rg -n "tests.test_agent_runtime_architecture|tests.test_agent_backend|tests.test_agent_jobs|npm run build|node scripts/check-product-pages.mjs" \
  docs/superpowers/plans/2026-05-15-agent-runtime-architecture-foundation.zh.md
```

Expected: 测试、build、页面检查命令都能匹配。

---

## Task 3: 完成规划文档自检

**Files:**
- Check: `docs/superpowers/specs/2026-05-15-agent-runtime-boundaries-workflow-design.md`
- Check: `docs/superpowers/plans/2026-05-15-agent-runtime-boundaries-workflow-plan.zh.md`
- Check: `docs/superpowers/plans/2026-05-15-agent-runtime-architecture-foundation.zh.md`

- [ ] **Step 1: 扫描占位词**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python - <<'PY'
from pathlib import Path

patterns = [
    "TB" + "D",
    "TO" + "DO",
    "implement " + "later",
    "fill in " + "details",
    "appropriate error " + "handling",
    "Write tests for " + "the above",
    "Similar to " + "Task",
]
paths = [
    Path("docs/superpowers/specs/2026-05-15-agent-runtime-boundaries-workflow-design.md"),
    Path("docs/superpowers/plans/2026-05-15-agent-runtime-boundaries-workflow-plan.zh.md"),
    Path("docs/superpowers/plans/2026-05-15-agent-runtime-architecture-foundation.zh.md"),
]

matches = []
for path in paths:
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for pattern in patterns:
            if pattern in line:
                matches.append(f"{path}:{lineno}: {pattern}")

if matches:
    raise SystemExit("\n".join(matches))
PY
```

Expected: 没有输出。

- [ ] **Step 2: 检查文档文件状态**

Run:

```bash
git status --short \
  docs/superpowers/specs/2026-05-15-agent-runtime-boundaries-workflow-design.md \
  docs/superpowers/plans/2026-05-15-agent-runtime-boundaries-workflow-plan.zh.md \
  docs/superpowers/plans/2026-05-15-agent-runtime-architecture-foundation.zh.md
```

Expected: 三份文档显示为新增或已修改，且没有业务代码文件出现在这个命令输出里。

- [ ] **Step 3: 记录最终交付说明**

最终回复中列出：

```text
设计 spec 路径
中文实施计划路径
已有架构基础计划路径
说明本轮未改代码
说明文档自检结果
```

---

## 后续执行建议

文档全部确认后，下一步不应该立刻做 RAG/MCP。推荐执行顺序：

1. 先执行 `2026-05-15-agent-runtime-architecture-foundation.zh.md` 的 Phase 1。
2. 验证所有当前 API、planner、job、frontend build 不回归。
3. 再写 Phase 2 的 Trace/AgentRun 设计和计划。
4. 再进入 RAG foundation。
5. 最后再接 Skill registry、MCP 和多 Agent。

## 自检

- 本计划只规划文档交付，不要求修改业务代码。
- 设计 spec 和实施 plan 职责分离：spec 解释边界，plan 解释任务。
- 多 Agent 明确作为未来能力，不进入下一阶段实现范围。
- 下一阶段优先级清晰：先 Agent Runtime Boundary，再 Trace/Run，再 RAG/Skill/MCP。

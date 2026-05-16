# Tasks Tailwind Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `/tasks` 页面迁移到 Tailwind，并补齐任务列表与任务详情的失败态、结果态和操作反馈，让用户能稳定理解任务执行状态。

**Architecture:** 保持 `/api/agent/tasks` 与 `/api/agent/tasks/{id}` 现有契约不变，先把 `TaskManagerPage` 的视觉层从 CSS Module 迁到 Tailwind，再在同一组件内补强列表行、详情弹窗、失败提示和结果入口。优先复用 `ProductShell`、`taskApi` 与现有 `AgentTaskDetail`/`AgentTaskSummary` 数据结构，不做后端字段扩展。

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, existing task API contracts, unittest + `npm run build` + `node scripts/check-product-pages.mjs`

---

### Task 1: 锁定 `/tasks` 页当前 Tailwind 迁移契约

**Files:**
- Modify: `tests/test_agent_backend.py`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: 写一个失败测试，要求 `/tasks` 页面不再依赖 CSS Module**

```python
    def test_task_manager_page_is_tailwind_based(self):
        task_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("TaskManagerPage.module.css", task_source)
        self.assertNotIn("styles.", task_source)
        self.assertIn('className="min-h-full', task_source)
        self.assertIn("任务管理页面", task_source)
```

- [ ] **Step 2: 再写一个失败测试，要求任务详情里明确包含失败步骤、事件、结果入口**

```python
    def test_task_manager_page_exposes_failure_and_result_states(self):
        task_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("标准步骤", task_source)
        self.assertIn("事件时间线", task_source)
        self.assertIn("结果与操作", task_source)
        self.assertIn("失败步骤", task_source)
        self.assertIn("结果预览", task_source)
        self.assertIn("重新执行", task_source)
```

- [ ] **Step 3: 运行测试，确认它们先失败**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_task_manager_page_is_tailwind_based \
  tests.test_agent_backend.FrontendClientContractTests.test_task_manager_page_exposes_failure_and_result_states
```

Expected: FAIL，原因是当前 `TaskManagerPage.tsx` 仍然引用 `TaskManagerPage.module.css`，并且尚未包含新文案/状态入口。

- [ ] **Step 4: 提交测试约束**

```bash
git add tests/test_agent_backend.py
git commit -m "test: lock tasks tailwind hardening contract"
```

### Task 2: 迁移 `/tasks` 页面布局层到 Tailwind

**Files:**
- Modify: `src/components/tasks/TaskManagerPage.tsx`
- Delete: `src/components/tasks/TaskManagerPage.module.css`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: 删除 CSS Module import，并把状态色常量从 CSS 变量改成 Tailwind 友好的 token map**

把这段：

```tsx
import styles from './TaskManagerPage.module.css';

const STATUS_TONES: Record<string, string> = {
  queued: 'var(--task-accent-1)',
  pending: 'var(--task-accent-1)',
  running: 'var(--task-accent-2)',
  active: 'var(--task-accent-2)',
  completed: 'var(--task-accent-3)',
  done: 'var(--task-accent-3)',
  succeeded: 'var(--task-accent-3)',
  failed: 'var(--task-accent-4)',
  error: 'var(--task-accent-4)',
  canceled: 'var(--task-accent-5)',
  cancelled: 'var(--task-accent-5)',
  idle: 'var(--task-accent-1)',
};
```

改成：

```tsx
const STATUS_TONES: Record<string, string> = {
  queued: 'bg-slate-100 text-slate-700',
  pending: 'bg-slate-100 text-slate-700',
  running: 'bg-sky-100 text-sky-700',
  active: 'bg-sky-100 text-sky-700',
  completed: 'bg-emerald-100 text-emerald-700',
  done: 'bg-emerald-100 text-emerald-700',
  succeeded: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-rose-100 text-rose-700',
  error: 'bg-rose-100 text-rose-700',
  canceled: 'bg-zinc-100 text-zinc-600',
  cancelled: 'bg-zinc-100 text-zinc-600',
  idle: 'bg-slate-100 text-slate-700',
}

function getStatusTone(status: string) {
  return STATUS_TONES[status] ?? 'bg-sky-100 text-sky-700'
}
```

- [ ] **Step 2: 先只改最外层容器、hero、toolbar、列表壳子，保持原有 JSX 结构**

把组件开头的外层结构改成类似：

```tsx
    <ProductShell>
      <div className="min-h-full space-y-4">
        <section
          aria-label="任务管理"
          className="rounded-lg border border-slate-200 bg-white/90 p-5 shadow-sm"
        >
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div className="min-w-0 flex-1 space-y-3">
              <nav className="flex items-center gap-2 text-xs font-medium text-slate-500" aria-label="面包屑">
                <Link href="/" className="font-semibold text-slate-900 no-underline">
                  总览
                </Link>
                <span aria-hidden="true">/</span>
                <span>任务</span>
              </nav>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight text-slate-950">任务管理页面</h1>
                <p className="max-w-3xl text-sm leading-6 text-slate-600">
                  统一查看任务队列、状态和最近结果；在列表里筛选、搜索、批量理解任务状态，并通过弹窗查看和处理单个任务。
                </p>
              </div>
            </div>
            <div className="grid w-full gap-3 md:grid-cols-[minmax(0,1fr)_160px_auto] xl:max-w-xl">
              {/* search / filter / primary action */}
            </div>
          </div>
        </section>
```

- [ ] **Step 3: 把任务列表表头、行布局、空态改成 Tailwind**

目标是把这些 CSS Module 类：

```tsx
styles.listPane
styles.tableHead
styles.taskRow
styles.taskRowSelected
styles.taskMain
styles.progressCell
styles.rowActions
styles.emptyState
```

全部替换成内联 className，列表行结构保持不变，推荐形态：

```tsx
<section aria-label="任务列表" className="rounded-lg border border-slate-200 bg-white/90 p-4 shadow-sm">
  <div className="hidden min-h-11 grid-cols-[28px_minmax(220px,1.45fr)_110px_130px_minmax(140px,0.9fr)_130px_110px] items-center gap-3 border-b border-slate-200 px-3 text-xs font-semibold text-slate-500 lg:grid">
    ...
  </div>
  <div className="mt-3 grid gap-3 lg:mt-0 lg:gap-0">
    {filteredTasks.map((task) => (
      <div
        key={task.id}
        className={[
          "grid gap-3 rounded-lg border border-slate-200 bg-white p-3 lg:rounded-none lg:border-x-0 lg:border-t-0 lg:border-b lg:p-3",
          isSelected ? "bg-lime-50" : "",
        ].join(" ")}
      >
        ...
      </div>
    ))}
  </div>
</section>
```

- [ ] **Step 4: 删掉 `TaskManagerPage.module.css`**

```bash
git rm src/components/tasks/TaskManagerPage.module.css
```

- [ ] **Step 5: 运行 Task 1 的两个测试，确认转绿**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_task_manager_page_is_tailwind_based \
  tests.test_agent_backend.FrontendClientContractTests.test_task_manager_page_exposes_failure_and_result_states
```

Expected: PASS

- [ ] **Step 6: 提交 Tailwind 迁移骨架**

```bash
git add src/components/tasks/TaskManagerPage.tsx src/components/tasks/TaskManagerPage.module.css tests/test_agent_backend.py
git commit -m "feat: migrate tasks page to tailwind"
```

### Task 3: 补强任务详情的失败恢复与结果展示

**Files:**
- Modify: `src/components/tasks/TaskManagerPage.tsx`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: 为结果 URL 和失败步骤加两个小工具函数**

在 `TaskManagerPage.tsx` 顶部工具函数区新增：

```tsx
function getSafeResultUrl(value: string | null | undefined) {
  const candidate = value?.trim() ?? ''
  if (!candidate) {
    return ''
  }

  if (candidate.startsWith('/') && !candidate.startsWith('//')) {
    return candidate
  }

  try {
    const url = new URL(candidate)
    return url.protocol === 'http:' || url.protocol === 'https:' ? candidate : ''
  } catch {
    return ''
  }
}

function findFailedStep(task: AgentTaskDetail | null) {
  return task?.steps.find((step) => step.status === 'failed') ?? null
}
```

- [ ] **Step 2: 在详情弹窗的“错误信息”区明确展示失败步骤**

把错误区改成：

```tsx
const failedStep = findFailedStep(activeTask)
const resultUrl = getSafeResultUrl(activeTask.videoUrl)

...

<section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
  <h3 className="text-sm font-semibold text-slate-900">错误信息</h3>
  <div className="mt-2 space-y-2 text-sm text-slate-600">
    <p>{activeTask.error ? activeTask.error.message ?? '任务存在错误信息，但未返回详细文案。' : '未检测到错误。'}</p>
    {failedStep ? (
      <p className="text-rose-700">
        失败步骤：{failedStep.title}
      </p>
    ) : null}
  </div>
</section>
```

- [ ] **Step 3: 在“结果与操作”区补齐结果预览和下载入口**

把结果区改成：

```tsx
<section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
  <h3 className="text-sm font-semibold text-slate-900">结果与操作</h3>
  <div className="mt-3 flex flex-wrap gap-3">
    <button type="button" className="inline-flex min-h-10 items-center rounded-lg border border-slate-200 px-3 text-sm font-medium text-slate-700">
      刷新状态
    </button>
    <button type="button" className="inline-flex min-h-10 items-center rounded-lg border border-slate-200 px-3 text-sm font-medium text-slate-700">
      查看方案
    </button>
    {resultUrl ? (
      <>
        <a
          href={resultUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex min-h-10 items-center rounded-lg bg-slate-900 px-3 text-sm font-medium text-white no-underline"
        >
          结果预览
        </a>
        <a
          href={resultUrl}
          download
          className="inline-flex min-h-10 items-center rounded-lg border border-slate-200 px-3 text-sm font-medium text-slate-700 no-underline"
        >
          下载结果
        </a>
      </>
    ) : null}
    {(activeTask.status === 'failed' || activeTask.status === 'error') && activeTask.error ? (
      <button type="button" className="inline-flex min-h-10 items-center rounded-lg bg-rose-600 px-3 text-sm font-medium text-white">
        重新执行
      </button>
    ) : null}
  </div>
</section>
```

- [ ] **Step 4: 把事件时间线和标准步骤卡片统一成 Tailwind 视觉**

将 `stepCard`、`eventList` 等 CSS Module 残余 className 全部替换成内联 Tailwind，保持文案与数据结构不变，重点确保：
- 步骤状态 badge 清楚
- 进度条稳定
- 错误文案用 `text-rose-700`
- 事件行用 `border-b border-slate-200`

- [ ] **Step 5: 跑整个前端契约测试文件**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend -v
```

Expected: PASS

- [ ] **Step 6: 提交任务详情补强**

```bash
git add src/components/tasks/TaskManagerPage.tsx tests/test_agent_backend.py
git commit -m "feat: harden tasks detail states"
```

### Task 4: 做整页验证与真实页面检查

**Files:**
- Verify only: `src/components/tasks/TaskManagerPage.tsx`
- Verify only: `src/app/tasks/page.tsx`

- [ ] **Step 1: 运行生产构建**

Run:

```bash
npm run build
```

Expected: build 成功，`/tasks` 页面被正常编译。

- [ ] **Step 2: 运行产品页面结构检查**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: `product page checks passed`

- [ ] **Step 3: 启动本地前端并人工检查 `/tasks`**

Run:

```bash
npm run dev -- --hostname 127.0.0.1 --port 3000
```

检查点：
- `/tasks` 列表页在桌面和窄屏下都不溢出
- 搜索和状态筛选仍然可用
- 打开任务详情弹窗后，能看到“标准步骤”“事件时间线”“结果与操作”
- 有失败任务时能看到“失败步骤”
- 有成功任务时能看到“结果预览”

- [ ] **Step 4: 如果真实数据不足，用已存在任务详情接口做一次只读检查**

访问：

```bash
curl -sS http://127.0.0.1:8010/api/agent/tasks | head
```

如果本地后端已运行，再确认 `/tasks` UI 是否正确消费 `currentStep`、`currentStepId`、`steps[]`、`events[]`、`videoUrl`。

- [ ] **Step 5: 提交最终收口**

```bash
git add src/components/tasks/TaskManagerPage.tsx tests/test_agent_backend.py
git commit -m "test: verify tasks tailwind hardening"
```

## Self-Review

- 这个计划只覆盖 `/tasks` 页面，不扩展到 `/workspace`、`/dashboard` 或后端 API 新字段，范围收得住。
- 计划里的测试、实现、验证文件路径都对应当前仓库真实路径。
- 任务顺序是：先锁契约，再迁布局，再补失败/结果态，最后整体验证，符合你当前“先产品可用，再做更大范围 Tailwind 迁移”的节奏。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-06-tasks-tailwind-hardening.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

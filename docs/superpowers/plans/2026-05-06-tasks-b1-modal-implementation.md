# Tasks B1 Modal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the real `/tasks` page to Tailwind CSS and upgrade it into the chosen B1 pattern: list-first task management with a richer modal detail surface.

**Architecture:** Keep `/tasks` as a single route and keep `TaskManagerPage.tsx` as the main page entry, but remove the page-level CSS Module dependency and rebuild the page with Tailwind classes plus small local helpers. Preserve the current `AgentTaskSummary[]` list contract and `AgentTaskDetail` modal contract, then expand the modal to show status summary, standard steps, event timeline, assets, and result sections more clearly.

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, existing `taskApi` client, Python `unittest`, Node build-time structural checks.

---

## File Structure

- Modify: `tests/test_agent_backend.py`
  - Adds source-contract coverage for the chosen B1 `/tasks` layout and modal detail sections.
- Modify: `scripts/check-product-pages.mjs`
  - Updates static page checks so the real `/tasks` page is validated against the B1 structure instead of the older CSS Module-era wording.
- Modify: `src/components/tasks/TaskManagerPage.tsx`
  - Removes `TaskManagerPage.module.css` import.
  - Adds Tailwind-based page structure, helper functions, and upgraded modal sections.
- Delete: `src/components/tasks/TaskManagerPage.module.css`
  - Removes the page-level stylesheet once Tailwind migration is complete.

Do not modify backend API contracts in this plan.
Do not fold the concept pages into the real `/tasks` route in this plan.

---

### Task 1: Lock The B1 `/tasks` Contract With Failing Tests

**Files:**
- Modify: `tests/test_agent_backend.py`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_page_is_tailwind_based`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_modal_renders_b1_sections`

- [ ] **Step 1: Add the failing source-contract tests**

Add these tests inside `FrontendClientContractTests` in `tests/test_agent_backend.py`, after `test_tasks_concept_pages_share_mock_data_and_cover_three_layouts`:

```python
    def test_tasks_page_is_tailwind_based(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("TaskManagerPage.module.css", tasks_source)
        self.assertNotIn("styles.", tasks_source)
        self.assertIn("className=\"grid min-w-0 gap-4", tasks_source)
        self.assertIn("aria-label=\"任务列表\"", tasks_source)

    def test_tasks_modal_renders_b1_sections(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("列表 + 弹窗详情", tasks_source)
        self.assertIn("任务详情", tasks_source)
        self.assertIn("状态摘要", tasks_source)
        self.assertIn("标准步骤", tasks_source)
        self.assertIn("事件时间线", tasks_source)
        self.assertIn("素材与结果", tasks_source)
        self.assertIn("activeTask.videoUrl", tasks_source)
        self.assertIn("activeTask.clips", tasks_source)
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_page_is_tailwind_based \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_modal_renders_b1_sections
```

Expected: fail because `TaskManagerPage.tsx` still imports `TaskManagerPage.module.css`, uses `styles.*`, and does not yet contain the upgraded B1 modal wording.

---

### Task 2: Add Tailwind-Friendly Helpers Before Markup Rewrite

**Files:**
- Modify: `src/components/tasks/TaskManagerPage.tsx`
- Test: `npm run build`

- [ ] **Step 1: Add status style helpers**

In `src/components/tasks/TaskManagerPage.tsx`, replace the CSS-variable tone helper with Tailwind class mapping:

```tsx
function getStatusClasses(status: string) {
  switch (status) {
    case 'completed':
    case 'done':
    case 'succeeded':
      return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
    case 'failed':
    case 'error':
      return 'bg-rose-50 text-rose-700 ring-rose-200';
    case 'running':
    case 'active':
      return 'bg-sky-50 text-sky-700 ring-sky-200';
    case 'queued':
    case 'pending':
    case 'idle':
    case 'canceled':
    case 'cancelled':
    default:
      return 'bg-amber-50 text-amber-700 ring-amber-200';
  }
}
```

- [ ] **Step 2: Add modal section helpers**

Still in `TaskManagerPage.tsx`, add:

```tsx
function getTaskResultLabel(task: AgentTaskDetail) {
  if (task.videoUrl) {
    return '已有成片';
  }
  if (task.error) {
    return '待修复';
  }
  return '执行中';
}

function getClipCountLabel(task: AgentTaskDetail) {
  return `${task.clips.length} 段素材`;
}
```

- [ ] **Step 3: Add a reusable progress bar fragment helper**

Add:

```tsx
function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-[#e9eee6]" aria-hidden="true">
      <span
        className="block h-full rounded-full bg-gradient-to-r from-[#8eb45f] to-[#4b8a86]"
        style={{ width: formatProgress(value) }}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run build to confirm helpers compile**

Run:

```bash
npm run build
```

Expected: build still passes before the full markup rewrite.

---

### Task 3: Convert The Main `/tasks` Page To Tailwind

**Files:**
- Modify: `src/components/tasks/TaskManagerPage.tsx`
- Delete: `src/components/tasks/TaskManagerPage.module.css`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_page_is_tailwind_based`
- Test: `npm run build`

- [ ] **Step 1: Remove the CSS Module import**

Delete:

```tsx
import styles from './TaskManagerPage.module.css';
```

- [ ] **Step 2: Replace the outer page and hero wrapper**

Rewrite the main return wrapper from:

```tsx
<ProductShell>
  <div className={styles.page}>
```

to a Tailwind structure like:

```tsx
<ProductShell>
  <div className="grid min-w-0 gap-4 lg:gap-5">
    <section className="rounded-lg border border-border bg-white/88 p-5 shadow-soft sm:p-6" aria-label="任务管理">
```

and convert the hero header/body/toolbar sections to Tailwind classes using the same visual direction as Dashboard and `/workspace`.

- [ ] **Step 3: Replace search and filter controls**

Convert the search and filter row to:

```tsx
<div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_180px_auto]">
  <label className="grid gap-2">
    <span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">搜索</span>
    <input
      className="min-h-11 rounded-lg border border-border bg-white px-4 text-sm text-ink outline-none focus:border-[#c2cfb5]"
      ...
    />
  </label>
  <label className="grid gap-2">
    <span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">状态</span>
    <select
      className="min-h-11 rounded-lg border border-border bg-white px-4 text-sm text-ink outline-none focus:border-[#c2cfb5]"
      ...
    />
  </label>
  <button
    type="button"
    className="inline-flex min-h-11 items-center justify-center rounded-lg border border-[#1f2522] bg-[#1f2522] px-4 text-sm font-semibold text-white disabled:opacity-45"
    ...
  >
    批量操作
  </button>
</div>
```

- [ ] **Step 4: Replace task list layout**

Convert the list section into Tailwind-based list/table hybrid markup:

```tsx
<section className="grid gap-4 rounded-lg border border-border bg-white p-4 shadow-soft" aria-label="任务列表">
```

and each row should use a structure like:

```tsx
<div className={`grid gap-3 rounded-lg border p-4 ${isSelected ? 'border-[#bfd4a2] bg-[#f6faef]' : 'border-border bg-white'}`}>
```

with a status badge using `getStatusClasses(task.status)` and a `ProgressBar`.

- [ ] **Step 5: Run the Tailwind source-contract test**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_page_is_tailwind_based
```

Expected: pass.

- [ ] **Step 6: Delete the CSS Module file**

Delete:

```text
src/components/tasks/TaskManagerPage.module.css
```

- [ ] **Step 7: Re-run build**

Run:

```bash
npm run build
```

Expected: build passes after the page-level Tailwind migration.

---

### Task 4: Upgrade The Modal To The Chosen B1 Detail Structure

**Files:**
- Modify: `src/components/tasks/TaskManagerPage.tsx`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_modal_renders_b1_sections`
- Test: `npm run build`

- [ ] **Step 1: Rename the modal framing language to B1**

Inside the modal header area, add explicit B1 wording:

```tsx
<span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">列表 + 弹窗详情</span>
<h2 id="task-detail-title" className="mt-1 text-xl font-semibold text-ink">
  任务详情：{activeTask.title}
</h2>
```

- [ ] **Step 2: Replace “状态与进度” with “状态摘要”**

Use:

```tsx
<section className="grid gap-3 rounded-lg border border-border bg-[#fbfcfa] p-4">
  <h3 className="text-sm font-semibold text-ink">状态摘要</h3>
  <div className="grid gap-3 sm:grid-cols-3">
    <SummaryCard label="当前步骤" value={activeTask.currentStep || '无'} />
    <SummaryCard label="最近更新时间" value={formatDateTime(activeTask.updatedAt)} />
    <SummaryCard label="产出状态" value={getTaskResultLabel(activeTask)} />
  </div>
  <div className="flex items-center gap-3">
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ring-1 ${getStatusClasses(activeTask.status)}`}>
      {getStatusLabel(activeTask.status)}
    </span>
    <span className="text-sm font-semibold text-ink">{formatProgress(activeTask.progress)}</span>
  </div>
  <ProgressBar value={activeTask.progress} />
  {activeTask.error ? (
    <div className="rounded-lg border border-[#f4c7cc] bg-[#fff7f7] px-4 py-3 text-sm text-[#8b1f2d]">
      {activeTask.error.message ?? '任务存在错误信息，但未返回详细文案。'}
    </div>
  ) : null}
</section>
```

- [ ] **Step 3: Upgrade the standard steps section**

Convert each step card to the richer Tailwind pattern:

```tsx
<article key={step.id} className="grid gap-2 rounded-lg border border-border bg-[#fbfcfa] p-3">
```

and keep:
- title
- description
- status label
- progress bar
- summary
- inline step error

- [ ] **Step 4: Upgrade the event timeline section**

Replace the basic list with cards:

```tsx
<div className="grid gap-3">
  {activeTask.events.map((event, index) => (
    <div key={`${event.id}-${index}`} className="grid gap-1 rounded-lg border border-border bg-[#fbfcfa] p-3">
```

and render event type, step, timestamp, and message.

- [ ] **Step 5: Add the “素材与结果” section**

Insert a new section before actions:

```tsx
<section className="grid gap-3 rounded-lg border border-border bg-white p-4">
  <div className="flex items-center justify-between gap-3">
    <h3 className="text-sm font-semibold text-ink">素材与结果</h3>
    <span className="text-xs font-semibold text-secondary">{getClipCountLabel(activeTask)}</span>
  </div>
  <div className="grid gap-3">
    {activeTask.clips.map((clip) => (
      <div key={`${clip.sceneId}-${clip.publicUrl}`} className="rounded-lg border border-border bg-[#fbfcfa] p-3">
        <div className="flex items-center justify-between gap-3">
          <strong className="text-sm text-ink">Scene {clip.sceneId}</strong>
          <span className="text-xs text-secondary">{clip.duration}s</span>
        </div>
        <p className="mt-1 text-sm text-ink">{clip.caption}</p>
        <p className="mt-1 truncate text-xs text-secondary">{clip.sourceUrl}</p>
      </div>
    ))}
    <div className="rounded-lg border border-dashed border-[#cfd8cb] bg-[#f7faf4] p-4">
      <span className="block text-xs font-semibold uppercase tracking-[0.02em] text-secondary">输出视频</span>
      <p className="mt-2 text-sm text-ink">
        {activeTask.videoUrl || '当前还没有可播放视频，详情区会继续显示失败或进行中的状态。'}
      </p>
    </div>
  </div>
</section>
```

- [ ] **Step 6: Keep actions present but scoped**

Use:

```tsx
<section className="grid gap-3 rounded-lg border border-border bg-white p-4">
  <h3 className="text-sm font-semibold text-ink">结果与操作</h3>
  <div className="flex flex-wrap gap-2">
```

Keep “刷新状态” and “查看方案”.
Keep “重新执行” only when `activeTask.status` is failed/error.

- [ ] **Step 7: Run the modal source-contract test**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_modal_renders_b1_sections
```

Expected: pass.

- [ ] **Step 8: Re-run build**

Run:

```bash
npm run build
```

Expected: build passes with the upgraded modal structure.

---

### Task 5: Update Structural Checks For The Real `/tasks` Page

**Files:**
- Modify: `scripts/check-product-pages.mjs`
- Test: `node scripts/check-product-pages.mjs`

- [ ] **Step 1: Update the `/tasks` page checks**

Replace the current minimal `/tasks` assertions:

```js
  assertIncludes(tasksHtml, '当前阶段', 'tasks 页面缺少当前阶段列');
  assertIncludes(tasksHtml, '任务列表', 'tasks 页面缺少任务列表区块');
  assertIncludes(tasksHtml, '批量操作', 'tasks 页面缺少批量操作入口');
  assertExcludes(tasksHtml, 'Modal 任务详情', 'tasks 页面仍保留常驻详情说明区');
```

with checks aligned to the new B1 page, for example:

```js
  assertIncludes(tasksHtml, '任务列表', 'tasks 页面缺少任务列表区块');
  assertIncludes(tasksHtml, '批量操作', 'tasks 页面缺少批量操作入口');
  assertIncludes(tasksHtml, '搜索任务', 'tasks 页面缺少搜索输入');
  assertIncludes(tasksHtml, '查看详情', 'tasks 页面缺少详情入口');
```

Do not require modal-only text in the static `/tasks.html` output, because the modal opens client-side.

- [ ] **Step 2: Run the structure check after build**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: pass.

---

### Task 6: Full Verification

**Files:**
- Modify: `tests/test_agent_backend.py`
- Modify: `scripts/check-product-pages.mjs`
- Modify: `src/components/tasks/TaskManagerPage.tsx`
- Delete: `src/components/tasks/TaskManagerPage.module.css`

- [ ] **Step 1: Run the focused frontend contract tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_page_is_tailwind_based \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_modal_renders_b1_sections
```

Expected: both pass.

- [ ] **Step 2: Run the broader backend/frontend contract file**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend
```

Expected: pass.

- [ ] **Step 3: Run the production build**

Run:

```bash
npm run build
```

Expected: pass.

- [ ] **Step 4: Run the static page checks**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: `product page checks passed`.

---

## Self-Review

- Spec coverage: this plan covers the chosen B1 route, Tailwind migration, richer modal detail sections, and validation updates.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: all field names align with the current `AgentTaskSummary` / `AgentTaskDetail` contract and `taskApi.ts`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-06-tasks-b1-modal-implementation.md`.

Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

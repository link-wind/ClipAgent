# Workspace Tailwind Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `/workspace` to Tailwind CSS and verify the frontend can drive the real backend execution path with external素材搜索、下载、渲染.

**Architecture:** Keep `BriefWorkspacePage.tsx` as the single `/workspace` page component and preserve the existing `AgentSession` API contract. Replace page-level CSS Module styling with Tailwind classes, add a lightweight post-confirmation execution handoff that reads the later `steps[]`, and document/run the real FastAPI + Celery + PostgreSQL + Redis + yt-dlp + FFmpeg integration path.

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, Zustand, FastAPI, SQLAlchemy, PostgreSQL, Redis, Celery, yt-dlp, FFmpeg, Python `unittest`, Node build-time structural checks.

---

## File Structure

- Modify `tests/test_agent_backend.py`
  - Adds frontend source-contract coverage for the Tailwind workspace migration and execution handoff.
- Modify `scripts/check-product-pages.mjs`
  - Keeps static `/workspace` HTML checks aligned with the Tailwind page and existing empty-state render.
- Modify `src/components/workspace/BriefWorkspacePage.tsx`
  - Removes the CSS Module import.
  - Replaces all page-level class names with Tailwind classes.
  - Adds execution handoff, result, and failure UI from existing session fields and `steps[]`.
- Delete `src/components/workspace/BriefWorkspacePage.module.css`
  - Removes the page-level stylesheet after Tailwind migration.
- Modify `README.md`
  - Adds a focused real external素材 integration runbook and expected verification outcomes.

Do not migrate `/tasks` in this plan. Do not change Dashboard.

---

### Task 1: Lock Workspace Migration And Handoff Contracts

**Files:**
- Modify: `tests/test_agent_backend.py`
- Test: `./.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_workspace_page_is_tailwind_based`
- Test: `./.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_workspace_handoff_renders_execution_steps_and_result_states`

- [ ] **Step 1: Add failing frontend source-contract tests**

Add these tests to `FrontendClientContractTests` in `tests/test_agent_backend.py`, after `test_workspace_polls_running_sessions_and_restores_events`:

```python
    def test_workspace_page_is_tailwind_based(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("BriefWorkspacePage.module.css", workspace_source)
        self.assertNotIn("styles.", workspace_source)
        self.assertIn("className=\"min-h-full", workspace_source)
        self.assertIn("grid w-full max-w-[980px]", workspace_source)

    def test_workspace_handoff_renders_execution_steps_and_result_states(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("EXECUTION_STEP_IDS", workspace_source)
        self.assertIn("create_task", workspace_source)
        self.assertIn("search_assets", workspace_source)
        self.assertIn("prepare_assets", workspace_source)
        self.assertIn("render_video", workspace_source)
        self.assertIn("执行交接", workspace_source)
        self.assertIn("activeJobId", workspace_source)
        self.assertIn("查看任务详情", workspace_source)
        self.assertIn("结果预览", workspace_source)
        self.assertIn("失败步骤", workspace_source)
```

- [ ] **Step 2: Run both tests and verify they fail for the current CSS Module page**

Run:

```bash
./.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_page_is_tailwind_based \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_handoff_renders_execution_steps_and_result_states
```

Expected: fail because `BriefWorkspacePage.tsx` still imports `BriefWorkspacePage.module.css`, uses `styles.*`, and does not yet render execution handoff/result/failure UI.

- [ ] **Step 3: Commit the failing contract tests**

Run:

```bash
git add tests/test_agent_backend.py
git commit -m "test: lock workspace tailwind handoff contract"
```

Expected: one commit containing only the two failing frontend source-contract tests.

---

### Task 2: Add Workspace Handoff Helpers Without Changing Markup Yet

**Files:**
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
- Test: `npm run build`

- [ ] **Step 1: Add execution step constants and status labels**

In `src/components/workspace/BriefWorkspacePage.tsx`, after `WORKSPACE_STEP_TITLES`, add:

```tsx
const EXECUTION_STEP_IDS = ['create_task', 'search_assets', 'prepare_assets', 'render_video'] as const;
const EXECUTION_STEP_TITLES: Record<(typeof EXECUTION_STEP_IDS)[number], string> = {
  create_task: '创建执行任务',
  search_assets: '搜索素材',
  prepare_assets: '准备素材',
  render_video: '渲染视频',
} as const;

const STEP_STATUS_LABELS: Record<string, string> = {
  pending: '等待中',
  running: '进行中',
  succeeded: '已完成',
  failed: '失败',
  skipped: '已跳过',
};
```

- [ ] **Step 2: Add step utility helpers**

After `getWorkspaceStatus`, add:

```tsx
function getStepStatusText(status: string) {
  return STEP_STATUS_LABELS[status] ?? status;
}

function getStepProgress(step: WorkspaceStep, fallbackProgress: number) {
  const value = step.status === 'pending' ? fallbackProgress : step.progress;
  return Math.max(0, Math.min(100, value));
}

function findFailedStep(session: AgentSession | null) {
  return session?.steps?.find((step) => step.status === 'failed') ?? null;
}
```

- [ ] **Step 3: Add derived execution/result values inside the component**

Inside `BriefWorkspacePage`, after the existing `workspaceSteps` `useMemo`, add:

```tsx
  const executionSteps = useMemo(() => {
    if (!session?.steps?.length) {
      return [];
    }

    return EXECUTION_STEP_IDS
      .map((stepId) => session.steps.find((step) => step.id === stepId))
      .filter((step): step is AgentSession['steps'][number] => Boolean(step));
  }, [session?.steps]);

  const failedStep = findFailedStep(session);
  const showExecutionHandoff = Boolean(session?.activeJobId || executionSteps.some((step) => step.status !== 'pending'));
  const resultUrl = session?.videoUrl || '';
```

- [ ] **Step 4: Run TypeScript/build verification**

Run:

```bash
npm run build
```

Expected: build passes with the new helpers unused or lightly used. If TypeScript reports unused helpers under the current configuration, continue to Task 3 before committing.

- [ ] **Step 5: Commit helper slice if the build passes**

Run:

```bash
git add src/components/workspace/BriefWorkspacePage.tsx
git commit -m "feat: add workspace execution step helpers"
```

Expected: one commit containing helper-only changes.

---

### Task 3: Convert Workspace Markup To Tailwind

**Files:**
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
- Delete: `src/components/workspace/BriefWorkspacePage.module.css`
- Test: `./.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_workspace_page_is_tailwind_based`
- Test: `npm run build`

- [ ] **Step 1: Remove the CSS Module import**

Delete this line from `src/components/workspace/BriefWorkspacePage.tsx`:

```tsx
import styles from './BriefWorkspacePage.module.css';
```

- [ ] **Step 2: Replace the outer page/header/workspace markup**

Replace the return wrapper from:

```tsx
<ProductShell>
  <div className={styles.page}>
    <header className={styles.header}>
```

through the matching header layout classes with Tailwind classes using this structure:

```tsx
<ProductShell>
  <div className="min-h-full px-4 py-4 sm:px-5">
    <header className="mx-auto w-full max-w-[980px] rounded-lg border border-border bg-white p-5 shadow-soft sm:p-6">
      <nav className="flex items-center gap-2 text-sm font-bold text-secondary" aria-label="面包屑">
        <Link href="/" className="text-ink no-underline">
          ClipForge
        </Link>
        <span aria-hidden="true">/</span>
        <span>方案沟通</span>
      </nav>
      <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold leading-tight text-ink sm:text-3xl">方案沟通页面</h1>
          <p className="mt-2 max-w-[68ch] text-sm leading-6 text-secondary">
            单栏推进需求理解、方向选择和最终确认，AI 的每一步都先给进度，再展示结果。
          </p>
        </div>
        <div className="min-w-[130px] rounded-full border border-[rgba(168,198,108,0.38)] bg-[#e3efd4] px-4 py-2 text-right">
          <span className="block text-xs text-secondary">当前状态</span>
          <strong className="mt-1 block text-sm font-semibold text-accentink">{getWorkspaceStatus(session)}</strong>
        </div>
      </div>
    </header>

    <main className="mx-auto mt-5 grid w-full max-w-[980px] gap-4" aria-label="方案工作区">
      <section className="overflow-hidden rounded-lg border border-border bg-white shadow-soft" aria-label="方案沟通">
```

- [ ] **Step 3: Replace conversation thread classes**

Convert the chat head, empty state, message bubbles, and thread containers to Tailwind equivalents:

```tsx
<div className="flex flex-col gap-3 border-b border-bordersoft px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
...
<div className="grid gap-4 bg-[linear-gradient(180deg,rgba(168,198,108,0.05),transparent_280px),#ffffff] p-5">
...
<article key={item.id} className="ml-auto grid max-w-full gap-2 sm:max-w-[84%]">
...
<div className="rounded-lg border border-[#1f2522] bg-[#1f2522] p-4 leading-7 text-white">{item.content}</div>
...
<article className="mr-auto grid max-w-full gap-2 sm:max-w-[84%]">
...
<div className="rounded-lg border border-[#e2e7e1] bg-[#f7f9f6] p-4 leading-7 text-[#303a34]">
```

Keep the current message mapping logic unchanged.

- [ ] **Step 4: Replace step, option, and final plan classes**

Convert every `styles.stepFlow`, `styles.stepBlock`, `styles.stepHead`, `styles.track`, `styles.resultBox`, `styles.sectionHead`, `styles.optionPreviewCard`, `styles.optionPreviewCardSelected`, `styles.finalPlan`, `styles.scene`, `styles.approval`, and related classes to Tailwind class strings. Use these stable patterns:

```tsx
className="grid gap-3 px-5 pb-5"
className="grid gap-3 rounded-lg border border-[#e1e6df] bg-white p-3"
className="flex items-center justify-between gap-3"
className="h-2 overflow-hidden rounded-full bg-[#edf1ed]"
className="block h-full rounded-full bg-gradient-to-r from-accentstrong to-accent"
className="rounded-lg border border-[#e4e8e3] bg-[#fbfcfa] p-3"
className="grid gap-3 sm:grid-cols-3"
className="w-full appearance-none rounded-lg border border-[#e4e8e3] bg-white p-3 text-left text-inherit outline-none transition hover:border-[#c7d3bf] hover:bg-[#fbfdf8] focus-visible:shadow-[inset_0_0_0_1px_rgba(168,198,108,0.55),0_0_0_3px_rgba(168,198,108,0.18)]"
className="border-accent bg-[#f6faef] shadow-[inset_0_0_0_1px_rgba(168,198,108,0.55)]"
className="grid gap-3"
className="grid gap-3 rounded-lg border border-[#e4e8e3] bg-white p-3 sm:grid-cols-[40px_minmax(0,1fr)_56px]"
className="flex flex-wrap gap-3"
```

Keep all existing data parsing and mapping logic unchanged.

- [ ] **Step 5: Replace composer and error classes**

Use:

```tsx
{errorText ? (
  <div className="mx-5 mb-4 rounded-lg border border-[#f5c2c7] bg-[#fff7f7] px-4 py-3 text-sm text-[#8b1f2d]">
    {errorText}
  </div>
) : null}

<form className="grid gap-3 border-t border-bordersoft bg-[#fcfdfb] p-4" onSubmit={submitMessage}>
  <textarea
    className="min-h-[92px] w-full resize-y rounded-lg border border-border bg-white p-3 font-inherit text-sm text-ink outline-none placeholder:text-secondary focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
...
  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <span className="text-xs text-secondary">底部输入区用于继续补充信息、修改方案，或推动下一轮细化。</span>
    <div className="flex flex-wrap gap-3">
```

- [ ] **Step 6: Delete the old CSS Module file**

Run:

```bash
git rm src/components/workspace/BriefWorkspacePage.module.css
```

Expected: the file is staged for deletion.

- [ ] **Step 7: Run the Tailwind migration contract test**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_workspace_page_is_tailwind_based
```

Expected: pass.

- [ ] **Step 8: Run frontend build**

Run:

```bash
npm run build
```

Expected: Next.js production build exits with code 0.

- [ ] **Step 9: Commit the Tailwind migration slice**

Run:

```bash
git add src/components/workspace/BriefWorkspacePage.tsx src/components/workspace/BriefWorkspacePage.module.css
git commit -m "feat: migrate workspace page to tailwind"
```

Expected: one commit containing the Tailwind migration and CSS Module deletion.

---

### Task 4: Add Execution Handoff, Result, And Failure UI

**Files:**
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
- Test: `./.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_workspace_handoff_renders_execution_steps_and_result_states`
- Test: `npm run build`

- [ ] **Step 1: Add execution handoff after the final plan result box**

After the final plan section inside the step flow, render this block outside the `workspaceSteps.map(...)` loop and before `{errorText ? ...}`:

```tsx
{showExecutionHandoff ? (
  <section className="mx-5 mb-5 grid gap-3 rounded-lg border border-border bg-[#fbfcfa] p-4" aria-label="执行交接">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">执行交接</span>
        <h2 className="mt-1 text-lg font-semibold text-ink">方案已进入任务执行</h2>
        <p className="mt-1 text-sm leading-6 text-secondary">
          后端会继续搜索素材、准备素材并渲染视频；更完整的事件时间线可以在任务页查看。
        </p>
      </div>
      <Link
        href="/tasks"
        className="inline-flex min-h-10 items-center justify-center rounded-lg border border-border bg-white px-4 text-sm font-semibold text-ink transition hover:bg-slate-50"
      >
        查看任务详情
      </Link>
    </div>

    <div className="rounded-lg border border-[#e4e8e3] bg-white p-3 text-sm text-secondary">
      <span className="font-bold text-ink">Job ID：</span>
      <span>{session?.activeJobId || '等待后端返回任务编号'}</span>
    </div>

    <div className="grid gap-3 sm:grid-cols-2">
      {executionSteps.map((step, index) => (
        <article key={step.id} className="grid gap-3 rounded-lg border border-[#e4e8e3] bg-white p-3">
          <div className="flex items-start justify-between gap-3">
            <strong className="text-sm text-ink">{EXECUTION_STEP_TITLES[step.id as (typeof EXECUTION_STEP_IDS)[number]]}</strong>
            <span className="whitespace-nowrap text-xs font-bold text-secondary">{getStepStatusText(step.status)}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-[#edf1ed]" aria-hidden="true">
            <span
              className="block h-full rounded-full bg-gradient-to-r from-accentstrong to-accent"
              style={{ width: `${getStepProgress(step, 10 + index * 8)}%` }}
            />
          </div>
          <p className="text-sm leading-6 text-secondary">{step.summary || step.description}</p>
        </article>
      ))}
    </div>
  </section>
) : null}
```

- [ ] **Step 2: Add result preview after the handoff block**

Immediately after the handoff section, add:

```tsx
{resultUrl ? (
  <section className="mx-5 mb-5 grid gap-3 rounded-lg border border-border bg-white p-4" aria-label="结果预览">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">结果预览</span>
        <h2 className="mt-1 text-lg font-semibold text-ink">视频已经生成</h2>
        <p className="mt-1 text-sm leading-6 text-secondary">可以在这里预览结果，也可以进入任务页查看完整事件和素材信息。</p>
      </div>
      <a
        href={resultUrl}
        className="inline-flex min-h-10 items-center justify-center rounded-lg bg-ink px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        打开视频
      </a>
    </div>
    <video className="aspect-video w-full rounded-lg border border-border bg-black" src={resultUrl} controls preload="metadata" />
  </section>
) : null}
```

- [ ] **Step 3: Add failed-step callout before request-level error text**

Immediately before `{errorText ? ...}` add:

```tsx
{session?.error || failedStep ? (
  <section className="mx-5 mb-5 rounded-lg border border-[#f5c2c7] bg-[#fff7f7] p-4 text-sm text-[#8b1f2d]" aria-label="失败步骤">
    <span className="text-xs font-bold uppercase tracking-[0.02em]">失败步骤</span>
    <h2 className="mt-1 text-base font-semibold">
      {failedStep
        ? WORKSPACE_STEP_TITLES[failedStep.id as (typeof WORKSPACE_STEP_IDS)[number]] ||
          EXECUTION_STEP_TITLES[failedStep.id as (typeof EXECUTION_STEP_IDS)[number]] ||
          failedStep.title
        : '执行失败'}
    </h2>
    <p className="mt-2 leading-6">{failedStep?.error?.message || session?.error?.message || '任务执行失败，请查看任务详情。'}</p>
    <p className="mt-2 leading-6">
      {failedStep?.error?.retryable || session?.error?.retryableStep
        ? '该问题可能可以重试，请先在任务页查看事件时间线。'
        : '请在任务页查看事件时间线和外部素材下载日志。'}
    </p>
  </section>
) : null}
```

- [ ] **Step 4: Run the handoff contract test**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_workspace_handoff_renders_execution_steps_and_result_states
```

Expected: pass.

- [ ] **Step 5: Run frontend build**

Run:

```bash
npm run build
```

Expected: build exits with code 0.

- [ ] **Step 6: Commit the handoff slice**

Run:

```bash
git add src/components/workspace/BriefWorkspacePage.tsx
git commit -m "feat: show workspace execution handoff"
```

Expected: one commit containing execution handoff, result preview, and failure callout.

---

### Task 5: Update Static Product Page Checks

**Files:**
- Modify: `scripts/check-product-pages.mjs`
- Test: `npm run build`
- Test: `node scripts/check-product-pages.mjs`

- [ ] **Step 1: Keep existing workspace assertions and add Tailwind-era labels visible in static HTML**

In `scripts/check-product-pages.mjs`, keep the existing workspace assertions and add these after the current `确认方案并生成任务` assertion:

```js
  assertIncludes(workspaceHtml, '方案工作区', 'workspace 页面缺少主工作区 aria 标签');
  assertIncludes(workspaceHtml, '描述你想完成的视频', 'workspace 页面缺少空态标题');
  assertIncludes(workspaceHtml, '底部输入区用于继续补充信息', 'workspace 页面缺少输入区说明');
```

Do not add static HTML assertions for `activeJobId`, `结果预览`, or `失败步骤`, because those depend on client-side session state and are covered by source-contract tests.

- [ ] **Step 2: Rebuild static pages**

Run:

```bash
npm run build
```

Expected: build exits with code 0.

- [ ] **Step 3: Run product page checks**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: `product page checks passed`.

- [ ] **Step 4: Commit structural check update**

Run:

```bash
git add scripts/check-product-pages.mjs
git commit -m "test: extend workspace page structure checks"
```

Expected: one commit containing only the static check update.

---

### Task 6: Add Real External Integration Runbook

**Files:**
- Modify: `README.md`
- Test: `git diff --check README.md`

- [ ] **Step 1: Add a dedicated integration section after Celery notes**

In `README.md`, after the existing Celery worktree queue example, add:

````markdown
### 真实外部素材联调

`/workspace` 到 `/tasks` 的真实联调必须启动 PostgreSQL、Redis、FastAPI、Celery worker 和 Next.js，并使用同一个 Celery 队列名。下面示例使用独立队列，避免多个 worker 抢任务：

```bash
docker compose up -d postgres redis
./.venv/bin/python -m alembic -c backend/alembic.ini upgrade head

export CLIPFORGE_CELERY_QUEUE=clipforge-agent-ws
export CELERY_BROKER_URL=redis://localhost:6379/1
export CELERY_RESULT_BACKEND=redis://localhost:6379/1

./.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8010
./.venv/bin/python -m celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO -Q clipforge-agent-ws
npm run dev
```

联调验收路径：

1. 打开 `http://localhost:3000/workspace`。
2. 输入真实短视频 brief。
3. 等待 Agent 返回方案和前四个标准步骤。
4. 点击“确认方案并生成任务”。
5. 确认 `/workspace` 展示执行交接和 Job ID。
6. 打开 `/tasks`，确认同一个任务出现。
7. 等待 worker 执行真实外部素材搜索、下载和渲染。
8. 如果生成 MP4，确认 `/workspace` 或 `/tasks` 能打开结果。
9. 如果外部素材失败，记录任务详情里的失败步骤、事件日志和 worker 错误，不把该次联调记为成功。
````

- [ ] **Step 2: Verify Markdown diff has no whitespace errors**

Run:

```bash
git diff --check README.md
```

Expected: no output and exit code 0.

- [ ] **Step 3: Commit runbook update**

Run:

```bash
git add README.md
git commit -m "docs: add workspace integration runbook"
```

Expected: one commit containing the README runbook update.

---

### Task 7: Run Automated Verification Suite

**Files:**
- Test: `./.venv/bin/python -m unittest tests.test_agent_api_p0 tests.test_agent_backend tests.test_agent_persistence tests.test_agent_jobs`
- Test: `npm run build`
- Test: `node scripts/check-product-pages.mjs`

- [ ] **Step 1: Run backend tests**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_api_p0 tests.test_agent_backend tests.test_agent_persistence tests.test_agent_jobs
```

Expected: `Ran 130+ tests` and `OK`. Deprecation warnings about `datetime.utcnow()` are acceptable for this stage if there are no failures.

- [ ] **Step 2: Run frontend production build**

Run:

```bash
npm run build
```

Expected: Next.js build exits with code 0.

- [ ] **Step 3: Run static product checks**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: `product page checks passed`.

- [ ] **Step 4: Inspect workspace migration diff**

Run:

```bash
git diff --stat HEAD~5..HEAD
git status --short
```

Expected: committed changes include workspace Tailwind migration, handoff UI, structure checks, and runbook. No accidental `/tasks` migration appears in the diff.

---

### Task 8: Run Real External Frontend-Backend Integration

**Files:**
- No code changes required unless verification exposes a real bug.
- Document any discovered command or environment correction in `README.md`.

- [ ] **Step 1: Start PostgreSQL and Redis**

Run:

```bash
docker compose up -d postgres redis
```

Expected: both services are up. If containers already exist, they should remain running.

- [ ] **Step 2: Run database migrations**

Run:

```bash
./.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
```

Expected: Alembic exits with code 0 and database schema contains agent/session/job tables.

- [ ] **Step 3: Export queue and Redis settings in both backend terminals**

Use these values for both API and worker:

```bash
export CLIPFORGE_CELERY_QUEUE=clipforge-agent-ws
export CELERY_BROKER_URL=redis://localhost:6379/1
export CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

Expected: API and worker use the same broker, result backend, and queue.

- [ ] **Step 4: Start FastAPI**

Run in one terminal:

```bash
./.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8010
```

Expected: API starts on `http://127.0.0.1:8010`.

- [ ] **Step 5: Start Celery worker**

Run in another terminal with the same exported variables:

```bash
./.venv/bin/python -m celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO -Q clipforge-agent-ws
```

Expected: worker starts and shows registered `backend.tasks.agent_tasks` tasks.

- [ ] **Step 6: Start Next.js**

Run:

```bash
npm run dev
```

Expected: frontend starts on `http://localhost:3000` and proxies `/api/agent/*` to FastAPI.

- [ ] **Step 7: Run a real workspace flow in the browser**

Open `http://localhost:3000/workspace` and submit this brief:

```text
做一个 20 秒的 AI 笔记产品宣传短视频，风格清爽专业，竖屏，面向职场用户，突出自动整理会议纪要和待办事项。
```

Expected:

- User message appears unchanged.
- AI returns a plan.
- The four planning steps render.
- Direction cards and final plan render.

- [ ] **Step 8: Confirm the plan and watch handoff**

Click `确认方案并生成任务`.

Expected:

- `/workspace` shows `执行交接`.
- `Job ID` appears when `activeJobId` is returned.
- Later execution steps show status/progress.
- `/tasks` contains the same task.

- [ ] **Step 9: Wait for real external素材搜索/下载/render**

Expected successful path:

- Celery logs show search/download/render progress.
- `/workspace` or `/tasks` receives a `videoUrl`.
- The generated MP4 opens in the browser.

Expected failure path:

- The failed standard step is visible.
- Worker/API logs contain a precise external-source error.
- The failure is documented as the real integration outcome rather than marked as success.

- [ ] **Step 10: Commit any runbook correction found during integration**

If the integration run reveals a missing environment variable, command correction, or external dependency note, update `README.md` and run:

```bash
git add README.md
git commit -m "docs: clarify workspace integration runbook"
```

Expected: only documentation corrections are committed. If a code bug is found, stop and create a focused bugfix task with a failing test before changing production code.

---

## Self-Review

- Spec coverage: Tasks cover `/workspace` Tailwind migration, current flow preservation, execution handoff, result/failure states, real backend integration, and runbook documentation.
- Scope control: `/tasks` Tailwind migration, Dashboard redesign, backend schema changes, local fixture fallback, and workflow-engine changes are excluded.
- Placeholder scan: no placeholder implementation steps remain.
- Type consistency: All helper names used by later tasks are defined before use: `EXECUTION_STEP_IDS`, `EXECUTION_STEP_TITLES`, `STEP_STATUS_LABELS`, `getStepStatusText`, `getStepProgress`, `findFailedStep`, `executionSteps`, `failedStep`, `showExecutionHandoff`, and `resultUrl`.
- Verification: Automated verification is separate from the real external integration run so failures can be attributed clearly.

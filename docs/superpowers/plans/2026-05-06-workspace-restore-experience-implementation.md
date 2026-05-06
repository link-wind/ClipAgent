# Workspace Restore Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve `/workspace` so restored sessions feel intentional, with restore acknowledgement, clear continuation actions, and an automatic jump to result, failure, or execution context.

**Architecture:** Keep all behavior changes inside `src/components/workspace/BriefWorkspacePage.tsx`, reuse the existing `activeSessionId -> getAgentSession(...) -> getAgentSessionEvents(...)` restore path, and add only local page state plus section refs. Do not change backend contracts or the shared store schema.

**Tech Stack:** Next.js 14, React 18, TypeScript, Zustand, Python `unittest`, Node structural checks.

---

## File Structure

- Modify: `tests/test_agent_backend.py`
  - Add source-contract tests for restore acknowledgement, continuation actions, and automatic jump wiring.
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
  - Add restore-local state, section refs, banner UI, focus handler, and one-shot scroll behavior.

Do not modify backend API files in this phase.
Do not modify `src/stores/useAgentStore.ts` unless implementation proves a new global field is strictly necessary.
Do not modify `src/components/tasks/TaskManagerPage.tsx` in this phase.

---

### Task 1: Lock Restore Experience With Failing Tests

**Files:**
- Modify: `tests/test_agent_backend.py`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_renders_resume_actions`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_can_jump_to_result_failure_or_execution`

- [ ] **Step 1: Add the failing source-contract tests**

Inside `FrontendClientContractTests`, after `test_workspace_handoff_renders_execution_steps_and_result_states`, add:

```python
    def test_workspace_restore_experience_renders_resume_actions(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("已恢复到当前方案会话", workspace_source)
        self.assertIn("查看任务列表", workspace_source)
        self.assertIn("继续补充方案", workspace_source)
        self.assertIn("textareaRef", workspace_source)
        self.assertIn("focus()", workspace_source)

    def test_workspace_restore_experience_can_jump_to_result_failure_or_execution(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("restoredSessionId", workspace_source)
        self.assertIn("scrollIntoView", workspace_source)
        self.assertIn("resultSectionRef", workspace_source)
        self.assertIn("failureSectionRef", workspace_source)
        self.assertIn("executionSectionRef", workspace_source)
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_renders_resume_actions \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_can_jump_to_result_failure_or_execution
```

Expected: fail because `BriefWorkspacePage.tsx` does not yet contain restore acknowledgement copy, composer focus wiring, or dedicated jump refs.

---

### Task 2: Add Restore State And Section Refs

**Files:**
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_can_jump_to_result_failure_or_execution`

- [ ] **Step 1: Expand the React import list with refs**

Update the import line in `BriefWorkspacePage.tsx` from:

```tsx
import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from 'react';
```

to:

```tsx
import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
```

- [ ] **Step 2: Add local restore state and refs inside the component**

Near the existing local `useState` declarations, add:

```tsx
  const [restoredSessionId, setRestoredSessionId] = useState<string | null>(null);
  const [hasAppliedRestoreJump, setHasAppliedRestoreJump] = useState(false);
  const executionSectionRef = useRef<HTMLElement | null>(null);
  const resultSectionRef = useRef<HTMLElement | null>(null);
  const failureSectionRef = useRef<HTMLElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
```

- [ ] **Step 3: Mark restore completion when the session is loaded from `activeSessionId`**

Inside the existing restore effect:

```tsx
  useEffect(() => {
    if (!activeSessionId || session) {
      return;
    }

    let isActive = true;

    const restoreSession = async () => {
      try {
        const [nextSession, nextEvents] = await Promise.all([
          getAgentSession(activeSessionId),
          getAgentSessionEvents(activeSessionId),
        ]);
        if (isActive) {
          setSession({ ...nextSession, events: nextEvents });
          setRestoredSessionId(activeSessionId);
          setHasAppliedRestoreJump(false);
        }
      } catch {
        // 恢复失败时保持当前空白状态。
      }
    };
```

- [ ] **Step 4: Reset restore markers when the active session changes through normal editing**

Add an effect after the restore logic:

```tsx
  useEffect(() => {
    if (!session?.id) {
      return;
    }

    if (restoredSessionId && session.id !== restoredSessionId) {
      setRestoredSessionId(null);
      setHasAppliedRestoreJump(false);
    }
  }, [restoredSessionId, session?.id]);
```

- [ ] **Step 5: Run the jump-wiring test**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_can_jump_to_result_failure_or_execution
```

Expected: still failing until Task 3 adds the actual scroll behavior and named refs to markup, or partially passing if the missing assertions are only the remaining UI strings.

---

### Task 3: Render Restore Banner And One-Shot Continuation Behavior

**Files:**
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_renders_resume_actions`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_can_jump_to_result_failure_or_execution`
- Test: `npm run build`

- [ ] **Step 1: Add a helper to focus the composer**

Inside `BriefWorkspacePage`, add:

```tsx
  function focusComposer() {
    textareaRef.current?.focus();
  }
```

- [ ] **Step 2: Add a one-shot restore jump effect**

After the existing derived values (`failedStep`, `showExecutionHandoff`, `resultUrl`), add:

```tsx
  useEffect(() => {
    if (!restoredSessionId || !session || session.id !== restoredSessionId || hasAppliedRestoreJump) {
      return;
    }

    const target =
      resultUrl
        ? resultSectionRef.current
        : session?.error || failedStep
          ? failureSectionRef.current
          : showExecutionHandoff
            ? executionSectionRef.current
            : null;

    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    setHasAppliedRestoreJump(true);
  }, [failedStep, hasAppliedRestoreJump, resultUrl, restoredSessionId, session, showExecutionHandoff]);
```

- [ ] **Step 3: Render the restore banner above the main workspace card**

Inside `<main ...>`, before the first `<section aria-label="方案沟通">`, add:

```tsx
          {restoredSessionId && session?.id === restoredSessionId ? (
            <section className="rounded-lg border border-[rgba(142,180,95,0.28)] bg-[#f6faef] p-4 shadow-soft" aria-label="恢复提示">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <span className="text-xs font-bold uppercase tracking-[0.02em] text-secondary">恢复提示</span>
                  <h2 className="mt-1 text-lg font-semibold text-ink">已恢复到当前方案会话</h2>
                  <p className="mt-1 text-sm leading-6 text-secondary">
                    你可以继续补充方案，或直接查看当前任务执行进度、结果与失败信息。
                  </p>
                </div>
                <div className="grid gap-2 sm:min-w-[220px]">
                  <div className="rounded-lg border border-[rgba(142,180,95,0.2)] bg-white px-3 py-2 text-sm text-secondary">
                    <span className="font-semibold text-ink">当前状态：</span>
                    {getWorkspaceStatus(session)}
                    {session.activeJobId ? ` · Job ID ${session.activeJobId}` : ''}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Link
                      href="/tasks"
                      className="inline-flex min-h-10 items-center justify-center rounded-lg border border-border bg-white px-4 text-sm font-semibold text-ink transition hover:bg-slate-50"
                    >
                      查看任务列表
                    </Link>
                    <Button type="button" variant="secondary" onClick={focusComposer}>
                      继续补充方案
                    </Button>
                  </div>
                </div>
              </div>
            </section>
          ) : null}
```

- [ ] **Step 4: Attach the refs to the relevant existing sections**

Update the existing sections like this:

```tsx
            {showExecutionHandoff ? (
              <section
                ref={executionSectionRef}
                className="mx-5 mb-5 grid gap-3 rounded-lg border border-border bg-[#fbfcfa] p-4"
                aria-label="执行交接"
              >
```

```tsx
            {resultUrl ? (
              <section
                ref={resultSectionRef}
                className="mx-5 mb-5 grid gap-3 rounded-lg border border-border bg-white p-4"
                aria-label="结果预览"
              >
```

```tsx
            {session?.error || failedStep ? (
              <section
                ref={failureSectionRef}
                className="mx-5 mb-5 rounded-lg border border-[#f5c2c7] bg-[#fff7f7] p-4 text-sm text-[#8b1f2d]"
                aria-label="失败步骤"
              >
```

Also attach the textarea ref:

```tsx
              <textarea
                ref={textareaRef}
                value={message}
```

- [ ] **Step 5: Run the focused tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_renders_resume_actions \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_can_jump_to_result_failure_or_execution
```

Expected: pass.

- [ ] **Step 6: Run the frontend build**

Run:

```bash
npm run build
```

Expected: pass with no type errors from section refs or textarea refs.

---

### Task 4: Full Verification

**Files:**
- Modify: `tests/test_agent_backend.py`
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`

- [ ] **Step 1: Run the focused restore tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_renders_resume_actions \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_can_jump_to_result_failure_or_execution
```

Expected: `OK`

- [ ] **Step 2: Run the full backend/frontend contract suite**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend
```

Expected: `OK`

- [ ] **Step 3: Run the production build**

Run:

```bash
npm run build
```

Expected: success

- [ ] **Step 4: Run the product page structural check**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: `product page checks passed`

---

## Self-Review

- Spec coverage:
  - restore acknowledgement -> Task 3
  - continuation actions -> Task 3
  - one-shot jump behavior -> Task 2 and Task 3
  - no backend/store contract expansion -> preserved in file scope
- Placeholder scan:
  - no `TODO`, `TBD`, or unresolved task references
- Type consistency:
  - `restoredSessionId`, `hasAppliedRestoreJump`, `executionSectionRef`, `resultSectionRef`, `failureSectionRef`, and `textareaRef` are named consistently across tasks

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-06-workspace-restore-experience-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

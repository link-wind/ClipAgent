# Tasks Actions Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `/tasks` modal actions partially real by wiring refresh + workspace jump and converting retry into a disabled explanatory action.

**Architecture:** Keep all behavioral changes in `TaskManagerPage.tsx`, reuse existing `getAgentTask(...)` detail fetch for refresh, and reuse the existing `useAgentStore` + `/workspace` restore path for plan navigation. Avoid any backend retry API work in this phase.

**Tech Stack:** Next.js 14, React 18, TypeScript, Zustand, Python `unittest`, Node structural checks.

---

## File Structure

- Modify: `tests/test_agent_backend.py`
  - Add source-contract tests for modal action behavior and copy.
- Modify: `src/components/tasks/TaskManagerPage.tsx`
  - Add refresh loading state, workspace navigation wiring, and retry disabled treatment.
- Verify existing usage: `src/stores/useAgentStore.ts`
  - Reuse `setActiveSessionId` without changing store schema.

Do not modify backend API files in this phase.
Do not modify `src/lib/taskApi.ts` unless implementation proves a new helper is strictly necessary.

---

### Task 1: Lock Action Wiring With Failing Tests

**Files:**
- Modify: `tests/test_agent_backend.py`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_modal_actions_wire_refresh_and_workspace_jump`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_retry_action_is_disabled_with_guidance_copy`

- [ ] **Step 1: Add the failing source-contract tests**

Inside `FrontendClientContractTests`, after `test_tasks_modal_renders_b1_sections`, add:

```python
    def test_tasks_modal_actions_wire_refresh_and_workspace_jump(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("const [isRefreshingTaskDetail, setIsRefreshingTaskDetail] = useState(false);", tasks_source)
        self.assertIn("setActiveSessionId(activeTask.sessionId);", tasks_source)
        self.assertIn("router.push('/workspace');", tasks_source)
        self.assertIn("刷新中", tasks_source)

    def test_tasks_retry_action_is_disabled_with_guidance_copy(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("任务级重新执行暂未开放，请返回方案页重新发起。", tasks_source)
        self.assertIn("disabled", tasks_source)
        self.assertIn("activeTask.status === 'failed' || activeTask.status === 'error'", tasks_source)
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_modal_actions_wire_refresh_and_workspace_jump \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_retry_action_is_disabled_with_guidance_copy
```

Expected: fail because `TaskManagerPage.tsx` does not yet contain refresh loading state, workspace jump wiring, or retry guidance copy.

---

### Task 2: Wire Refresh And Workspace Navigation

**Files:**
- Modify: `src/components/tasks/TaskManagerPage.tsx`
- Verify: `src/stores/useAgentStore.ts`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_modal_actions_wire_refresh_and_workspace_jump`

- [ ] **Step 1: Import router and shared store actions**

In `TaskManagerPage.tsx`, update imports to include:

```tsx
import { useRouter } from 'next/navigation';
import { useAgentStore } from '@/stores/useAgentStore';
```

- [ ] **Step 2: Add router and store bindings**

Inside `TaskManagerPage`, add:

```tsx
  const router = useRouter();
  const setActiveSessionId = useAgentStore((state) => state.setActiveSessionId);
  const setSession = useAgentStore((state) => state.setSession);
```

`setSession(null)` is used before workspace navigation so `/workspace` restores from `activeSessionId` instead of carrying stale task-page state.

- [ ] **Step 3: Add refresh loading state**

Inside `TaskManagerPage`, add:

```tsx
  const [isRefreshingTaskDetail, setIsRefreshingTaskDetail] = useState(false);
```

- [ ] **Step 4: Add a refresh handler for the active task**

Still in `TaskManagerPage.tsx`, add:

```tsx
  async function refreshActiveTaskDetail() {
    if (!activeTask) {
      return;
    }

    const requestId = detailRequestIdRef.current + 1;
    detailRequestIdRef.current = requestId;
    setIsRefreshingTaskDetail(true);
    setErrorText(null);

    try {
      const detail = await getAgentTask(activeTask.id);
      if (detailRequestIdRef.current !== requestId) {
        return;
      }
      setActiveTask(detail);
    } catch {
      if (detailRequestIdRef.current === requestId) {
        setErrorText('任务详情暂时加载失败。');
      }
    } finally {
      if (detailRequestIdRef.current === requestId) {
        setIsRefreshingTaskDetail(false);
      }
    }
  }
```

- [ ] **Step 5: Add workspace jump handler**

Add:

```tsx
  function openWorkspaceForActiveTask() {
    if (!activeTask?.sessionId) {
      setErrorText('当前任务缺少方案会话，暂时无法打开方案页。');
      return;
    }

    setActiveSessionId(activeTask.sessionId);
    setSession(null);
    router.push('/workspace');
  }
```

- [ ] **Step 6: Wire the two action buttons**

In the modal `结果与操作` section:

- connect `刷新状态` to `refreshActiveTaskDetail`
- connect `查看方案` to `openWorkspaceForActiveTask`
- disable `刷新状态` while `isRefreshingTaskDetail`
- label it `刷新中` while loading

Use a pattern like:

```tsx
                    <button
                      type="button"
                      onClick={() => void refreshActiveTaskDetail()}
                      disabled={isRefreshingTaskDetail}
                      className="inline-flex min-h-10 items-center rounded-lg border border-border bg-white px-4 text-sm font-medium text-ink transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45"
                    >
                      {isRefreshingTaskDetail ? '刷新中' : '刷新状态'}
                    </button>
                    <button
                      type="button"
                      onClick={openWorkspaceForActiveTask}
                      className="inline-flex min-h-10 items-center rounded-lg border border-border bg-white px-4 text-sm font-medium text-ink transition hover:bg-slate-50"
                    >
                      查看方案
                    </button>
```

- [ ] **Step 7: Run the action wiring test**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_modal_actions_wire_refresh_and_workspace_jump
```

Expected: pass.

---

### Task 3: Convert Retry Into A Disabled Guided Action

**Files:**
- Modify: `src/components/tasks/TaskManagerPage.tsx`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_retry_action_is_disabled_with_guidance_copy`

- [ ] **Step 1: Keep retry visibility scoped to failed/error tasks**

Retain the existing failed/error conditional:

```tsx
activeTask.status === 'failed' || activeTask.status === 'error'
```

- [ ] **Step 2: Render disabled retry button instead of active button**

Replace the current retry action with:

```tsx
                    {(activeTask.status === 'failed' || activeTask.status === 'error') ? (
                      <div className="grid gap-2">
                        <button
                          type="button"
                          disabled
                          className="inline-flex min-h-10 items-center rounded-lg bg-slate-300 px-4 text-sm font-medium text-slate-600"
                        >
                          重新执行
                        </button>
                        <p className="text-xs leading-5 text-secondary">
                          任务级重新执行暂未开放，请返回方案页重新发起。
                        </p>
                      </div>
                    ) : null}
```

- [ ] **Step 3: Run the retry guidance test**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_retry_action_is_disabled_with_guidance_copy
```

Expected: pass.

---

### Task 4: Full Verification

**Files:**
- Modify: `tests/test_agent_backend.py`
- Modify: `src/components/tasks/TaskManagerPage.tsx`

- [ ] **Step 1: Run the focused action tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_modal_actions_wire_refresh_and_workspace_jump \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_retry_action_is_disabled_with_guidance_copy
```

Expected: both pass.

- [ ] **Step 2: Run the broader frontend/backend contract file**

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

- [ ] **Step 4: Run static product page checks**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: `product page checks passed`.

## Self-Review

- Spec coverage: refresh behavior, workspace jump, and disabled retry guidance are each covered by dedicated tasks.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: all proposed APIs and store actions match current `TaskManagerPage`, `useAgentStore`, and `taskApi` contracts.

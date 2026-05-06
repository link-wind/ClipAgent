# ClipForge Tasks Actions Phase 1 Design

## Background

The `/tasks` page has already been migrated to the chosen B1 pattern: list + modal detail.

The modal currently exposes three action buttons:

1. `刷新状态`
2. `查看方案`
3. `重新执行`

At the moment they are presentational only. The next step is to connect the actions that already have stable system support, while avoiding a premature retry API design.

## Goal

Make the `/tasks` modal actions partially real and operational:

1. `刷新状态` should refresh the current task detail in place.
2. `查看方案` should return the user to `/workspace` using the task's existing session context.
3. `重新执行` should remain visible for failed tasks, but clearly communicate that task-level retry is not available yet.

## Why This Scope

This phase is intentionally narrow.

The frontend and backend already support:

- task detail reads via `GET /api/agent/tasks/{job_id}`
- workspace session restoration via `activeSessionId` + `getAgentSession(...)`

The system does not currently expose a dedicated task retry endpoint.

Instead of inventing a half-stable retry contract inside a UI polish step, this phase will connect the two real capabilities first and treat retry as a later product/API decision.

## Non-Goals

- Do not add a new backend retry endpoint.
- Do not change task execution orchestration.
- Do not redesign `/workspace`.
- Do not change task detail data contracts.
- Do not implement bulk actions in this phase.

## Chosen Interaction Model

### Refresh status

Inside the modal, `刷新状态` should:

1. request the latest task detail using the active task id,
2. keep the modal open,
3. replace the current modal content with the fresh detail payload,
4. show a loading/disabled state while the refresh request is in flight,
5. surface the existing `任务详情暂时加载失败。` style error if the request fails.

This action should not refetch the whole task list first. It is detail-scope refresh, not page-wide reload.

### View workspace plan

Inside the modal, `查看方案` should:

1. capture the current task `sessionId`,
2. write it into the shared agent store as `activeSessionId`,
3. navigate to `/workspace`.

`/workspace` already restores a session when `activeSessionId` exists and no current in-memory session is loaded. This phase should reuse that behavior rather than duplicating a task-to-workspace restore path inside `/tasks`.

### Retry execution

Inside the modal, `重新执行` should:

1. remain visible only for failed/error tasks,
2. render as disabled,
3. include nearby explanatory copy that task-level retry is not yet open and the user should return to the workspace if they want to re-run from the plan flow.

The goal is to avoid a misleading live button for a capability the backend does not yet provide.

## UI Behavior

### Refresh status button

- Default label: `刷新状态`
- Loading label: `刷新中`
- Disabled while request is in flight

### View workspace button

- Label remains `查看方案`
- Button stays enabled when `activeTask.sessionId` exists
- It may be disabled only if session context is somehow missing, though current task contract expects `sessionId`

### Retry execution button

- Only visible when `activeTask.status` is `failed` or `error`
- Disabled visual treatment should be explicit
- Supporting text should explain the current limitation in plain language

Recommended copy:

- button: `重新执行`
- helper text: `任务级重新执行暂未开放，请返回方案页重新发起。`

## Data and State Design

This phase adds only local UI state to `TaskManagerPage.tsx`:

- `isRefreshingTaskDetail: boolean`

No new backend fields are required.

No new store fields are required, because `useAgentStore` already exposes:

- `activeSessionId`
- `setActiveSessionId(...)`
- `setSession(...)`

## File Impact

### `src/components/tasks/TaskManagerPage.tsx`

Primary implementation surface for:

- modal action handlers
- local refresh loading state
- workspace navigation wiring
- retry disabled treatment and helper text

### `src/stores/useAgentStore.ts`

No schema changes expected. The page should consume existing store actions.

### `src/lib/taskApi.ts`

No changes expected. `getAgentTask(...)` already covers refresh status.

### `tests/test_agent_backend.py`

Add source-contract coverage for:

- modal action wiring language
- workspace jump wiring
- disabled retry explanation

## Error Handling

### Refresh failure

If refreshing detail fails:

- keep the modal open,
- preserve the previous `activeTask` detail,
- set the existing page error banner text or a task-detail-specific message,
- exit loading state cleanly.

### Workspace jump with missing session id

If task detail unexpectedly lacks `sessionId`:

- do not navigate,
- show a concise error,
- keep the modal open.

This should be defensive only; the current contract expects `sessionId`.

## Testing Strategy

This phase should use TDD.

Automated checks should include:

1. source-contract tests for action wiring and copy
2. `python -m unittest tests.test_agent_backend`
3. `npm run build`
4. `node scripts/check-product-pages.mjs`

Recommended source-contract signals:

- `setActiveSessionId(activeTask.sessionId)`
- `router.push('/workspace')`
- `刷新中`
- `任务级重新执行暂未开放，请返回方案页重新发起。`
- disabled retry button treatment

## Success Criteria

This phase is complete when:

1. `刷新状态` can refresh the current modal detail,
2. `查看方案` can return to `/workspace` with the relevant session context,
3. `重新执行` is visibly unavailable rather than misleadingly active,
4. no backend API contract is changed,
5. tests and build checks pass.

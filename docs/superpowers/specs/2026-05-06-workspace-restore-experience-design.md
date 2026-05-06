# ClipForge Workspace Restore Experience Design

## Background

The `/tasks` page now supports a real `查看方案` action. When the user clicks it from the task detail modal, the app writes `activeSessionId` into the shared store and navigates to `/workspace`.

`/workspace` already knows how to restore a session from that id:

- `getAgentSession(activeSessionId)`
- `getAgentSessionEvents(activeSessionId)`

So the data path is already functional. What is still missing is the user experience after the restore happens.

Right now the user lands on a valid `/workspace` page, but the page does not explicitly tell them:

1. that they have returned from task execution context,
2. which part of the page matters now,
3. whether they should inspect execution progress, a finished result, a failed step, or continue editing the plan.

That makes the handoff feel technically correct but contextually weak.

## Goal

Improve the `/workspace` restore experience so that users returning from task context immediately understand:

1. that their previous plan session has been restored,
2. what the current execution state is,
3. where to continue next inside the page.

## Why This Scope

This phase is intentionally narrow.

We do not need a new backend API, a new page, or a new restore protocol. The current store and session APIs are already enough.

The highest-value improvement is to make the restored page feel intentional:

- acknowledge the restored session,
- orient the user to execution/result/failure state,
- give them one-click continuation choices.

## Non-Goals

- Do not change backend session or task contracts.
- Do not add task retry APIs.
- Do not redesign `/workspace` layout from scratch.
- Do not add a new dedicated task detail route.
- Do not rebuild `/tasks` modal behavior in this phase.

## Approaches Considered

### Option A: Add restore context to the URL

Example direction:

- `/workspace?from=task`

Pros:

- explicit and inspectable,
- survives refresh,
- easy to reason about in isolation.

Cons:

- requires changing the route contract for the existing `查看方案` flow,
- would force us to update the recently-added `/tasks` action test and implementation again,
- still does not carry much more information than the current store-based restore.

### Option B: Add a dedicated restore-context field to Zustand

Example direction:

- `workspaceEntryContext = { source: 'task' }`

Pros:

- keeps URL clean,
- can carry richer context later.

Cons:

- introduces new global store surface for a short-lived UI state,
- adds lifecycle questions around when the flag should be cleared,
- is more machinery than this phase needs.

### Option C: Derive restore mode locally from the existing store/session flow

Detect the restore moment inside `/workspace` when:

- `activeSessionId` exists,
- `session` is empty,
- a fresh session is then restored into the page.

Pros:

- no backend or routing changes,
- no new global store schema,
- minimal implementation surface,
- keeps the work focused on experience rather than plumbing.

Cons:

- a manual reload of `/workspace` with only `activeSessionId` present may look similar to a task-return restore.

## Chosen Direction

Choose Option C.

This phase should treat restore experience as a local `/workspace` concern. `BriefWorkspacePage.tsx` already owns the restore fetch and the execution/result/failure surfaces, so it is the right place to add orientation behavior.

The page should:

1. detect when a session has just been restored from `activeSessionId`,
2. show a compact restore banner near the top of the workspace,
3. automatically bring the user to the most relevant lower section,
4. provide clear next actions.

## Restored Experience Model

### 1. Restore acknowledgement

After a session is restored from `activeSessionId`, `/workspace` should render a compact banner above the main workspace card flow.

The banner should tell the user:

- the current plan session has been restored,
- the page is now showing the latest known workspace + execution state.

Recommended headline:

- `已恢复到当前方案会话`

Recommended supporting copy:

- `你可以继续补充方案，或直接查看当前任务执行进度、结果与失败信息。`

### 2. State summary inside the banner

The banner should summarize the most relevant current state using existing session fields:

- workspace status label from `getWorkspaceStatus(session)`
- `activeJobId` when available
- whether there is a result video
- whether there is a failed step

This summary should not duplicate the full execution handoff cards. It is only a quick orientation layer.

### 3. Two continuation actions

The banner should expose two immediate actions:

1. `查看任务列表`
2. `继续补充方案`

`查看任务列表`:

- links to `/tasks`,
- does not try to reopen a modal automatically.

`继续补充方案`:

- moves focus to the bottom composer textarea,
- supports the case where the user returned only to refine the plan.

### 4. Automatic section jump

When the restore has just completed, `/workspace` should automatically scroll to the most relevant section once per restore event.

Priority order:

1. `结果预览` if `videoUrl` exists
2. `失败步骤` if `session.error` exists or a failed step exists
3. `执行交接` if execution handoff is visible
4. otherwise keep the user near the top flow

This makes the restored experience feel purposeful without changing the page structure.

## UI Behavior

### Restore banner visibility

Show the banner only when the page can tell that a restore has just occurred in the current page lifecycle.

The banner should not be shown for the initial empty `/workspace` state.

It is acceptable for the banner to reappear after a browser refresh if the page is restoring from `activeSessionId` again. That is slightly redundant but still truthful and low-risk.

### Composer focus action

`继续补充方案` should focus the existing textarea in the bottom composer area.

No new composer UI is needed.

### Automatic scroll behavior

The automatic scroll should happen once per restore completion, not on every subsequent poll update.

This avoids fighting the user's own scroll position while the page continues polling running sessions.

## Data And State Design

No backend changes are required.

No new Zustand store fields are required.

This phase should stay inside `BriefWorkspacePage.tsx` with local state/refs such as:

- a local marker that a restore just completed,
- refs for:
  - execution handoff section,
  - result section,
  - failure section,
  - composer textarea.

Possible local state shape:

- `restoredSessionId: string | null`
- `hasAppliedRestoreJump: boolean`

Exact naming can follow local code style, but the behavior should match the design.

## File Impact

### `src/components/workspace/BriefWorkspacePage.tsx`

Primary implementation surface for:

- detecting restore completion,
- rendering restore banner,
- managing focus/scroll targets,
- exposing continuation actions.

### `tests/test_agent_backend.py`

Add source-contract coverage for:

- restore acknowledgement copy,
- task list and composer continuation actions,
- automatic jump wiring for result/failure/execution sections.

### `scripts/check-product-pages.mjs`

No change is required unless implementation alters static `/workspace` copy that the script already checks.

## Error Handling

If session restore fails:

- keep the current empty or previous state,
- do not show a false restore banner,
- continue using the existing silent-failure behavior unless the page already has a user-facing error.

If the composer ref is unavailable:

- the `继续补充方案` action should fail quietly,
- the user still remains on the correct page.

## Testing Strategy

This phase should use TDD.

Automated checks should include:

1. focused source-contract tests for restore experience
2. `python -m unittest tests.test_agent_backend`
3. `npm run build`
4. `node scripts/check-product-pages.mjs`

Recommended source-contract signals:

- `已恢复到当前方案会话`
- `查看任务列表`
- `继续补充方案`
- `scrollIntoView`
- refs or handlers for result/failure/execution targeting

## Success Criteria

This phase is complete when:

1. returning to `/workspace` after a restore clearly acknowledges the restored session,
2. users can immediately choose between checking `/tasks` and continuing plan edits,
3. the page auto-jumps to result, failure, or execution context when appropriate,
4. no backend or task API contract is changed,
5. tests and build checks pass.

# ClipForge Tasks Operations Usability Design

## Background

ClipForge Dashboard and `/workspace` have already been moved onto the current Tailwind-based product direction. The next active surface is `/tasks`, which now serves as the operational follow-up page after a workspace session is confirmed and handed off to backend execution.

The current `/tasks` page already has a real B1 structure in code:

- task list as the primary surface,
- task detail in a modal,
- search and status filter controls,
- actions such as `查看详情` and `查看方案`,
- detail sections for status, steps, timeline, clips, and result.

That means this stage does not need to invent `/tasks` from scratch. The product shape is already chosen. The user has already selected `B1 列表 + 弹窗详情` as the preferred direction.

What is still missing is the next layer of product usefulness:

- the list is structurally present, but not yet optimized for fast daily scanning,
- the control bar still looks broader than the actual supported actions,
- result access is still too buried,
- the page needs to feel like a real operational console rather than an interim technical shell.

## Current Status

As of May 7, 2026:

1. `/tasks` is already Tailwind-based at the page level.
2. The chosen layout direction is B1 (`列表 + 弹窗详情`), not B2 or B3.
3. `/workspace -> confirm -> /tasks -> worker` has already been verified as a real product path.
4. Retry is intentionally not supported as a task-row action in the current phase.
5. The active product need is not backend expansion, but improving the operational usability of the existing `/tasks` surface.

## Goal

Turn `/tasks` into a genuinely usable daily task console for operations-oriented workflows by improving:

1. list scanability,
2. status filtering clarity,
3. high-frequency actions,
4. result access,
5. failure-state readability,

while keeping the existing B1 page structure and backend contracts unchanged.

## Why This Scope

This is the highest-value next step because `/tasks` is already the place where users verify whether a confirmed plan is progressing, failed, or completed.

At this point, the biggest gap is not missing infrastructure. It is decision speed:

- Can the user quickly see which tasks need attention?
- Can they open the right detail fast?
- Can they jump to the workspace session or result without unnecessary clicks?
- Can failed tasks feel actionable without pretending unsupported task-level retry exists?

This phase should solve those product questions before moving into heavier features such as batch actions or more advanced diagnostics.

## Non-Goals

- Do not redesign `/tasks` into B2 (`列表 + 右侧详情面板`).
- Do not redesign `/tasks` into B3 (`独立详情页`).
- Do not add task-level retry, cancel, or rerun actions.
- Do not implement real batch operations in this phase.
- Do not add new backend task fields or change API contracts.
- Do not turn `/tasks` into a long-form engineering log viewer.
- Do not migrate unrelated pages or redesign `/workspace`.

## Approaches Considered

### Option A: Keep B1 and improve operational usability in place

Direction:

- preserve list + modal detail,
- improve scanability and action density,
- expose high-value actions earlier,
- tighten unsupported controls so the page feels honest.

Pros:

- lowest implementation risk,
- reuses current tested structure,
- matches the already approved product direction,
- easiest to verify against current `/workspace -> /tasks` flow.

Cons:

- still relies on a modal for deeper context,
- does not optimize for heavy side-by-side task comparison.

### Option B: Shift toward a B2-style side panel

Direction:

- keep the list,
- replace modal-first detail with a persistent right-side panel.

Pros:

- faster repeated task switching,
- better for dense triage workflows.

Cons:

- reopens a layout decision that has already been made,
- creates larger page restructuring risk,
- would expand scope beyond “make current surface more usable”.

### Option C: Reframe `/tasks` as a mini operations board

Direction:

- group tasks by status sections such as running, failed, completed,
- reduce dependence on a linear list.

Pros:

- strong visual operations identity,
- easier status bucket scanning at a glance.

Cons:

- weaker fit for direct task lookup,
- would likely reduce detail-action clarity,
- too large a product shift for this stage.

## Chosen Direction

Choose Option A.

This stage should treat `/tasks` as an operational task console built on the existing B1 structure:

- the task list remains the main surface,
- the modal remains the deep-detail surface,
- the list becomes more informative on its own,
- the most common actions move closer to the row level,
- unsupported actions remain clearly out of scope.

## Core Product Model

The page should support a simple operational loop:

1. scan the list,
2. identify the task that needs attention,
3. take the most likely next action directly from the list when possible,
4. open the modal only when deeper judgment is needed.

This means the list must no longer act as a thin index. It should become the place where the user can already answer:

- Is this task still running?
- Is it blocked or failed?
- Does it already have a result?
- Should I inspect details, return to the plan, or open the output?

## Page Structure Direction

Keep the current page in four visible layers:

1. **Page header**
   - breadcrumb,
   - title,
   - short operational description.

2. **Control bar**
   - search,
   - status filter,
   - refresh-related action if already supported locally,
   - honest treatment for unsupported batch actions.

3. **Task list**
   - the primary operational surface,
   - each row should communicate status, phase, recency, and result availability clearly.

4. **Task detail modal**
   - the secondary surface for detailed reading,
   - still responsible for status summary, steps, timeline, materials, result, and failure context.

The page should remain list-first, not modal-first.

## List Scanability Requirements

### Row information priority

Each row should make the following information easy to scan without opening detail:

1. task title,
2. task status,
3. current step or current phase,
4. progress,
5. updated time,
6. whether a result is available,
7. whether the task is failed and needs attention.

### Visual emphasis rules

- Failed tasks should stand out more clearly than neutral tasks.
- Completed tasks with a result should visibly communicate that an output exists.
- Running tasks should show progress without overusing decorative UI.
- Empty or waiting states should remain quiet and readable.

### Operational summaries

The list-level summary chips above the table can stay lightweight, but they should help the user orient quickly:

- total visible tasks,
- selected count,
- current viewing mode or ordering hint if that text remains useful.

These chips should not pretend there are richer bulk workflows than the page actually supports.

## Control Bar Behavior

### Search

Search should stay simple and broad:

- task title,
- task id,
- session id,
- status,
- current step.

This phase should not add advanced query syntax.

The page copy around search should make it clear that this is quick filtering, not a complex search system.

### Status filter

Status filtering should remain the main structured filter.

It should prioritize operational categories the user can understand quickly:

- 全部状态,
- 进行中,
- 失败,
- 已完成,
- and any mapped backend statuses that still need to appear.

The exact backend values can remain unchanged internally as long as the displayed labels stay user-readable.

### Batch action treatment

Real batch actions are out of scope.

So this phase should avoid presenting `批量操作` as a strong primary action that looks ready for immediate use. The control may be:

- visually deemphasized,
- disabled with truthful copy,
- or reframed as a clearly unavailable future capability only if that is consistent with the page style.

The key requirement is honesty: the page should not imply that batch workflows already exist if they do not.

## Row-Level Actions

This phase should prioritize the three highest-value row actions:

1. `查看详情`
2. `查看方案`
3. `打开结果` when `videoUrl` exists

### `查看详情`

- opens the existing modal,
- remains the default path for deeper task inspection.

### `查看方案`

- jumps back to `/workspace` using the existing active-session restore path,
- supports users who want to continue or inspect the originating plan.

### `打开结果`

- should appear only when the task has a result URL,
- should give the user direct access to the generated output without forcing a modal open first.

This action is especially important for operational usability because completed tasks often need quick validation rather than deep inspection.

## Detail Modal Direction

The modal should remain the deep-detail layer, but its product role should stay narrow and clear:

- summarize current state,
- explain what happened,
- expose result and source materials,
- make failures understandable,
- link the user back to the right next place.

It should not become a dumping ground for every possible control.

### Modal sections to preserve

The current section grouping is directionally correct and should remain:

- status summary,
- standard steps,
- event timeline,
- materials and result,
- failure or guidance copy when relevant.

### Failure guidance

When a task fails:

- the modal should clearly state that the task failed,
- surface the best available error message,
- help the user understand whether the likely next step is to inspect the workspace plan or review provider/output context,
- avoid offering task-row retry if retry is not implemented.

The main rule is consistency: the list and modal should tell the same story about what the user can do next.

## Result Access Direction

Completed tasks should feel materially different from unfinished tasks.

If `videoUrl` exists:

- the list should signal result availability,
- the user should be able to reach the output directly,
- the modal should still preserve the richer result context.

This phase should optimize for “I want to quickly verify the output” rather than making the user reopen detail every time.

## Data And State Design

No backend schema changes are required.

No new page route is required.

This phase should stay within the existing front-end data model already used by `TaskManagerPage.tsx`:

- `AgentTaskSummary`
- `AgentTaskDetail`
- existing status mapping helpers,
- existing workspace jump path through the shared agent store.

Implementation can add local derived helpers for:

- row-level result availability labels,
- row-level action visibility,
- lightweight operational grouping copy,
- clearer failure emphasis.

## File Impact

### `src/components/tasks/TaskManagerPage.tsx`

Primary implementation surface for:

- control bar treatment,
- list row scanability improvements,
- row-level action additions,
- result access visibility,
- failure emphasis,
- modal copy tightening.

### `tests/test_agent_backend.py`

Add or update source-contract coverage for:

- row-level result action visibility or wording,
- row-level workspace jump wiring if moved or duplicated,
- truthful non-retry treatment,
- operational copy introduced by this phase.

### `scripts/check-product-pages.mjs`

Update only if static `/tasks` copy changes enough that the structural check should assert the new list-first operational wording.

## Error Handling

If task list loading fails:

- keep the current lightweight page error treatment,
- do not fabricate operational summaries from missing data.

If task detail fails to load:

- preserve the current inline error behavior,
- do not leave the user with a modal that implies valid detail was fetched.

If `sessionId` is missing for a workspace jump:

- keep the current truthful error message,
- do not render an active `查看方案` action when it cannot work reliably.

If `videoUrl` is missing:

- do not show a fake result action,
- continue surfacing task state as running, failed, or waiting based on real fields.

## Testing Strategy

Automated checks should stay focused on the current product contract:

- `npm run build`
- `node scripts/check-product-pages.mjs`
- targeted front-end contract tests in `tests/test_agent_backend.py`

Suggested contract coverage for this stage:

1. `/tasks` still renders as a Tailwind-based B1 page.
2. The list includes the key operational labels introduced in this phase.
3. A result-oriented action is surfaced when task output exists.
4. Unsupported retry is still not presented as an active path.
5. Workspace jump remains wired through the existing restore flow.

Manual verification should confirm:

1. the list is readable without opening any modal,
2. failed tasks stand out clearly,
3. completed tasks with results expose a faster output path,
4. `查看方案` still returns the user to `/workspace`,
5. the modal remains a useful secondary detail surface rather than the only way to understand the page.

## Implementation Boundaries

Expected primary file changes:

- modify `src/components/tasks/TaskManagerPage.tsx`
- update `tests/test_agent_backend.py` as needed
- update `scripts/check-product-pages.mjs` only if static wording changes require it

Avoid changing:

- backend task schema,
- `/workspace` layout,
- B2/B3 concept routes except where references must stay accurate,
- batch workflow architecture,
- retry backend behavior.

## Success Criteria

This stage is complete when:

1. `/tasks` remains on the approved B1 (`列表 + 弹窗详情`) structure.
2. Users can scan task status and next-likely action directly from the list.
3. Completed tasks with results provide a quicker path to output access.
4. Failed tasks are more legible without exposing unsupported retry behavior.
5. `查看方案` and `查看详情` still work within the current product flow.
6. The build, structural checks, and targeted contract tests pass.

## Open Follow-Up

Once this operational-usability pass is complete, the next `/tasks` follow-up can be chosen more cleanly from:

1. deeper diagnostics and provider-oriented failure interpretation,
2. real batch workflows,
3. a future layout shift only if B1 proves insufficient in practice.

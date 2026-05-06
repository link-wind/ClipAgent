# ClipForge Tasks B1 Modal Design

## Background

ClipForge now has three product surfaces with clearer roles:

1. Dashboard for overview.
2. `/workspace` for brief, plan, and execution handoff.
3. `/tasks` for job-level tracking and troubleshooting.

Dashboard and `/workspace` have already moved to Tailwind-oriented page structure. `/tasks` is the next frontend surface to bring into the same direction.

Before touching the real `/tasks` page, three static concept pages were produced:

- B1: list + modal detail
- B2: list + persistent side detail panel
- B3: list + dedicated detail route

After review, the chosen direction is **B1: list + modal detail**.

## Why B1

B1 is the best fit for the current stage because it keeps the `/tasks` page scoped and incremental:

- it preserves the existing mental model of a task list page,
- it avoids turning this stage into a larger route or information-architecture rewrite,
- it still allows the detail experience to become much richer than the current version,
- it is the lowest-risk path while the backend execution flow is still being hardened.

This matches the broader product preference already established in the repo: move page-by-page, reduce migration blast radius, and avoid pulling unrelated surfaces into the same step.

## Goals

1. Migrate the real `/tasks` page from CSS Modules to Tailwind-based page styling.
2. Keep `/tasks` as a single route in this stage.
3. Preserve the list-first workflow.
4. Upgrade the modal detail experience so it feels like a real troubleshooting surface rather than a thin pop-up.
5. Reflect the real agent task contract already exposed by `AgentTaskDetail`:
   - status
   - progress
   - currentStep
   - steps
   - events
   - clips
   - videoUrl
   - error

## Non-Goals

- Do not convert `/tasks` into a side-panel layout in this stage.
- Do not split `/tasks` into list page + detail route in this stage.
- Do not add new backend fields just for presentation.
- Do not redesign Dashboard or `/workspace`.
- Do not add bulk actions, retry orchestration, or admin-only tooling unless already supported.

## Chosen Interaction Model

The real `/tasks` page should remain a scan-and-open workflow:

1. User lands on a list of recent tasks.
2. User can scan status, step, progress, and update time quickly.
3. Selecting a task opens a modal overlay.
4. The modal becomes the focused troubleshooting surface for that task.
5. Closing the modal returns the user to the list with their context preserved.

This keeps the main page lightweight while letting the detail surface become significantly more complete.

## Page Structure

### Main `/tasks` page

The page should keep these sections:

1. Header / breadcrumb / page title.
2. Search and status filter tools.
3. Summary chips or lightweight counts.
4. Task list table or stacked list rows.
5. Lightweight row actions.

The list should prioritize scan speed over decoration. It is a control surface, not a marketing page.

### Modal detail

The modal should become the main information surface for a selected task.

Recommended section order:

1. **Header**
   - task title
   - session id
   - job id
   - created time
   - close button

2. **Status summary**
   - current status badge
   - progress bar
   - current step
   - last updated time
   - high-signal error message when present

3. **Standard steps**
   - `create_task`
   - `search_assets`
   - `prepare_assets`
   - `render_video`
   - each step shows status, progress, summary, and error if present

4. **Event timeline**
   - compact chronological event list
   - event type
   - step
   - message
   - timestamp

5. **Assets and result**
   - clips summary
   - per-scene clip cards when available
   - final `videoUrl` when available

6. **Actions**
   - refresh
   - open related workspace context when meaningful
   - retry button only when it matches real backend capability or remains clearly presentational

## Visual Direction

The visual tone should align with the Tailwind direction already established on Dashboard and `/workspace`:

- restrained white surfaces
- low-radius panels
- dense but readable spacing
- high-contrast status chips
- consistent progress bars
- no decorative hero treatment
- no nested card stacks that feel like marketing UI

The list page should feel operational.
The modal should feel like an inspection console.

## Responsive Behavior

Desktop:

- task list remains primary on the page
- modal opens centered with enough width for two-column internal structure when useful

Mobile:

- list remains stacked
- modal should still be usable as a full-height or nearly full-height overlay
- content sections should collapse to one column without horizontal overflow

## Data Contract Expectations

The frontend should continue to rely on the current task contract from `src/lib/taskApi.ts`.

No schema changes are required for this stage.

The design assumes:

- `AgentTaskSummary[]` powers the list
- `AgentTaskDetail` powers the modal
- `steps[]`, `events[]`, `clips[]`, `videoUrl`, and `error` already exist and remain the source of truth

## Error Handling Expectations

The upgraded modal should surface failure clearly:

- show the top-level task error prominently,
- show failed step information inline,
- keep event timeline visible for debugging context,
- do not hide external-provider failures like YouTube timeout or provider fallback issues.

This is especially important because `/tasks` is where users will go after `/workspace` handoff when execution fails.

## Testing Strategy

Automated checks for the real implementation stage should include:

- frontend source-contract tests for the new `/tasks` Tailwind structure
- `npm run build`
- `node scripts/check-product-pages.mjs`

The structure check should eventually verify:

- `/tasks` still has the list surface
- the chosen B1 modal detail language exists
- the modal covers status, steps, events, and result sections

## Success Criteria

This B1 stage is complete when:

1. the real `/tasks` page no longer depends on `TaskManagerPage.module.css`,
2. page-level styling is Tailwind-based,
3. the list-first flow is preserved,
4. the modal detail experience is upgraded to show status, steps, timeline, assets, and result clearly,
5. build and structural checks pass,
6. the page still works with the current backend task contract.

## Follow-Up After B1

After the B1 implementation lands, the next likely decisions become clearer:

- keep B1 as the long-term pattern,
- or promote `/tasks` to B2 or B3 later if operational usage shows the modal is too constrained.

That later decision should be driven by real usage and troubleshooting pain, not by preemptive redesign.

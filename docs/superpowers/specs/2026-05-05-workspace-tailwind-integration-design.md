# ClipForge Workspace Tailwind Integration Design

## Background

ClipForge Dashboard homepage has already moved to Tailwind CSS and now acts as the product overview entry. The next active product surface is `/workspace`, where users create a brief, review AI-generated plan steps, choose a direction, confirm the plan, and hand the session off to backend execution.

Today `/workspace` is still implemented with `BriefWorkspacePage.module.css`. It already has the right product flow and consumes the standard backend `steps[]` contract, but it needs to align with the Tailwind direction and prove that the frontend can work with the real backend execution path.

The project direction is to eventually use Tailwind CSS across the whole frontend. This stage should move one page at a time: Dashboard is done, `/workspace` is next, `/tasks` remains for a later stage.

## Current Status

As of May 6, 2026, the `/workspace` page-level Tailwind migration has already landed in code, including the execution handoff, result entry, and failed-step UI. The active work in this stage is no longer "do the migration from scratch", but "verify the real frontend-backend path, document the runbook, and record the exact external-provider outcome."

This also means `/tasks` is no longer part of this stage's implementation scope. It is now a separate follow-on surface, and any further `/tasks` work should be planned independently.

On May 6, 2026, the real integration result advanced one step further:

- the initial external-provider failure was traced to provider-search control flow rather than frontend/backend handoff,
- `search_and_download_agent_clips()` was searching later providers even after an earlier provider had already returned candidates,
- under `pexels,youtube`, this still triggered YouTube search and exposed the known external timeout,
- after changing the search loop to stop probing later providers once the current provider returns candidates, a fresh real run completed with Pexels clips and a rendered MP4.

## Goals

1. Migrate `/workspace` from CSS Modules to Tailwind CSS.
2. Preserve the current single-column Product Workspace flow.
3. Keep the existing `AgentSession`, `steps[]`, `events[]`, `activeJobId`, and `videoUrl` contracts.
4. Improve the post-confirmation workspace handoff so users can see task creation and execution progress.
5. Complete frontend-backend integration against real external video sources, including search, download, and render.
6. Document the exact local integration commands and verification outcomes.

## Non-Goals

- Do not migrate `/tasks` to Tailwind in this stage.
- Do not redesign Dashboard.
- Do not introduce a local fixture or fallback material pool as the main acceptance path.
- Do not replace the current FastAPI, Celery, PostgreSQL, Redis, yt-dlp, or FFmpeg execution architecture.
- Do not add authentication, permissions, billing, or collaboration features.
- Do not create a new workflow engine.

## Chosen Direction

Use a two-track stage:

1. **Frontend migration track:** convert `BriefWorkspacePage.tsx` to Tailwind classes while keeping the same page responsibility and data flow.
2. **Integration track:** run the real local stack and verify `/workspace` can trigger backend execution with real external素材下载 and render output.

This order keeps risk readable. First make `/workspace` Tailwind-based and structurally stable. Then run the full backend path so any remaining failures can be attributed to API, worker, external source, download, or render behavior rather than the styling migration.

## Tailwind Migration Direction

The long-term frontend direction is:

1. Dashboard: already Tailwind.
2. `/workspace`: migrate in this stage.
3. `/tasks`: migrate in a later stage.
4. Shared tokens remain in `src/app/globals.css` and `tailwind.config.ts`.
5. Page-level CSS Modules should gradually disappear as each page migrates.

This stage should not try to solve the whole migration at once. It should leave the project in a better intermediate state where two of the three product pages are Tailwind-based.

## Workspace UI Scope

Keep the existing single-column flow:

1. Header with breadcrumb, page title, and current session status.
2. Conversation thread with original user messages and latest assistant response.
3. AI analysis steps for the first four standard steps:
   - `understand_request`
   - `extract_requirements`
   - `generate_options`
   - `finalize_plan`
4. Direction cards based on backend step results.
5. Final plan summary and scene list.
6. Confirmation controls.
7. Composer for follow-up instructions.

The Tailwind migration should keep this structure recognizable. This is a migration and hardening stage, not a new layout exploration.

## Post-Confirmation Handoff

After the user confirms a plan, `/workspace` should make execution state clear instead of only changing the top-level session status.

Add a lightweight execution handoff area after the final plan section when a session has been confirmed or has an active job. It should display:

- Task creation status.
- `activeJobId` when available.
- Link to `/tasks` for deeper task detail.
- The later standard steps:
  - `create_task`
  - `search_assets`
  - `prepare_assets`
  - `render_video`
- Current status and progress for those steps.

This section should not duplicate the full task manager. It only tells the user that the confirmed plan is now being executed and where to inspect details.

## Result And Failure States

When `session.videoUrl` is available:

- Show a result preview or clear result entry in `/workspace`.
- Provide a way to open or download the output.
- Keep the `/tasks` detail link visible.

When `session.error` or a failed `AgentStep` exists:

- Show the failed step title if it can be identified.
- Show the user-facing error message.
- Show whether the step is retryable if the backend provides that information.
- Suggest checking `/tasks` for the event timeline.

Do not hide real external-source failures. If YouTube or another external source fails due to network, token, cookie, or format constraints, the UI and runbook should record that reality instead of treating the run as successful.

## Backend Integration Scope

The integration path must use real backend services:

- PostgreSQL
- Redis
- FastAPI
- Celery worker
- yt-dlp
- FFmpeg
- Next.js frontend proxying `/api/agent/*`

The acceptance path must use real external素材搜索/下载. Local fixture or fallback素材 may be discussed later, but it is not the main path for this stage.

## Local Integration Runbook

The implementation should verify and document a command sequence equivalent to:

```bash
docker compose up -d postgres redis
./.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
CLIPFORGE_CELERY_QUEUE=clipforge-agent-ws \
  ./.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8010
CLIPFORGE_CELERY_QUEUE=clipforge-agent-ws \
  ./.venv/bin/python -m celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO -Q clipforge-agent-ws
npm run dev
```

If environment variables such as `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `CLIPFORGE_DATABASE_URL`, `CLIPFORGE_REDIS_URL`, `CELERY_BROKER_URL`, or `CELERY_RESULT_BACKEND` are required, the runbook should state the expected values or source.

The verified user path is:

1. Open `/workspace`.
2. Submit a short-video brief.
3. Wait for the plan and four workspace steps.
4. Choose or review a direction.
5. Confirm the plan.
6. Watch the execution handoff update.
7. Confirm the task appears in `/tasks`.
8. Wait for real素材搜索/下载/render.
9. Confirm the final MP4 URL is visible and playable or record the exact real external failure.

The verified successful run on May 6, 2026 used `CLIPFORGE_ASSET_PROVIDER_ORDER=pexels,youtube` plus a valid `PEXELS_API_KEY`, and produced a completed job with four Pexels clips and a final MP4 output.

## Testing Strategy

Automated checks:

- `npm run build`
- `node scripts/check-product-pages.mjs`
- Backend unit/contract tests:

```bash
./.venv/bin/python -m unittest tests.test_agent_api_p0 tests.test_agent_backend tests.test_agent_persistence tests.test_agent_jobs
```

Structural checks should be updated to assert the Tailwind workspace still renders:

- Step 1 through Step 4 titles.
- Direction section.
- Final confirmation action.
- Execution handoff label.
- Task detail link.
- Result or failure state copy.

Manual integration checks:

- Full local stack starts successfully.
- Browser flow can create and confirm a workspace session.
- Celery receives the job.
- `/tasks` shows the job.
- The worker attempts real external search/download/render.
- Result MP4 appears, or the exact external-source failure is documented.

## Implementation Boundaries

Expected files:

- Modify `src/components/workspace/BriefWorkspacePage.tsx`
- Delete or stop importing `src/components/workspace/BriefWorkspacePage.module.css`
- Modify `scripts/check-product-pages.mjs`
- Modify `README.md` or add a focused runbook if integration commands need more detail
- Add or update tests only where they lock current contracts

Avoid changing:

- `/tasks` UI migration
- Dashboard UI
- Backend API schema unless integration reveals a necessary bug
- Search/render architecture unless real integration exposes a blocking issue

## Risks

1. Real external素材下载 can fail for reasons outside the app, including provider blocking, token/cookie requirements, unavailable formats, or network restrictions.
2. Tailwind migration can accidentally change responsive behavior or text overflow handling.
3. Running API and worker with different queue or Redis settings can make confirmed jobs appear stuck.
4. FFmpeg or yt-dlp local dependency drift can make integration fail even when the app logic is correct.

## Success Criteria

This stage is complete when:

1. `/workspace` uses Tailwind for page-level styling and no longer depends on `BriefWorkspacePage.module.css`.
2. Existing workspace behavior is preserved: brief submit, message display, step display, direction cards, final plan, confirmation, polling, and error messaging.
3. Confirmed sessions show task handoff and later execution steps in `/workspace`.
4. The frontend build and structural checks pass.
5. Backend unit/contract tests pass.
6. A real local integration run is completed using external素材搜索/下载.
7. The final outcome is documented as either a playable MP4 or a precise external-source failure with logs and next action.

## Open Follow-Up

After this stage, the next Tailwind migration candidate should be `/tasks`, because Dashboard and `/workspace` will already be on Tailwind.

# ClipForge Next Stage Task Map

## Current State

ClipForge now has a productized three-page flow:

1. Dashboard homepage for overview, entry points, metrics, trend proof, resource composition, and recent work.
2. `/workspace` for brief intake, plan generation, standard step snapshots, option selection, confirmation, polling, and result preview.
3. `/tasks` for task list management, filtering, selection, modal detail, step snapshots, events, clips, and result links.

The main `steps[]` contract is implemented across backend response models, read services, frontend API types, workspace rendering, and task detail rendering. The Dashboard Tailwind Home work is also substantially complete, so homepage polish should pause unless a new product direction reopens it.

## Recommended Next Stage

The next stage should be **P0 workflow hardening and release readiness**.

This means focusing on whether a real user can reliably go from brief to rendered MP4, understand failures, and recover without developer intervention.

## Priority 1: End-To-End Execution Verification

Goal: prove the happy path works with real local infrastructure.

Tasks:

1. Start PostgreSQL and Redis with `docker compose up -d postgres redis`.
2. Run Alembic migrations against the local database.
3. Start FastAPI on `127.0.0.1:8010`.
4. Start Celery with an explicit queue.
5. Start Next.js.
6. Create a real `/workspace` session, confirm the plan, wait for worker execution, and verify `/tasks` shows the same job.
7. Confirm the output MP4 exists, loads in the frontend, and is downloadable.
8. Record the exact command sequence and any environment assumptions in README or a runbook.

Success criteria:

- A fresh local checkout can run the full flow using documented commands.
- The UI shows plan, progress, task status, steps, events, clips, and result.
- Failure messages are understandable when external video download fails.

## Priority 2: Failure Handling And Recovery

Goal: make common failures visible and recoverable.

Tasks:

1. Normalize search/download/render errors into user-facing `AgentError` and step-level `AgentStepError`.
2. Ensure failed jobs map to the correct failing standard step.
3. Preserve enough event detail for debugging without exposing raw stack traces in the UI.
4. Add retry guidance for known external-source issues such as yt-dlp, JavaScript runtime, YouTube token/cookie requirements, and unavailable videos.
5. Decide whether retry is manual documentation only or a UI action in `/tasks`.

Success criteria:

- A failed search/download/render run shows a clear failed step.
- `/tasks` detail includes useful failure context.
- The next recommended action is obvious to the user.

## Priority 3: Asset Source Resilience

Goal: reduce dependence on a single external video source.

Options:

1. Local fixture pool: fastest and most reliable for demos and tests.
2. Pexels/Pixabay provider: better production fallback but requires API keys and provider-specific contracts.
3. Hybrid strategy: use local fixtures for dev/test and provider fallback for real runs.

Recommendation:

Start with a local fixture pool for deterministic P0 verification, then add one external fallback provider after the end-to-end flow is stable.

Success criteria:

- The worker can finish a demo render even when YouTube is unavailable.
- Tests can cover asset selection without relying on live external network behavior.

## Priority 4: Documentation And Release Hygiene

Goal: make the current branch understandable and shippable.

Tasks:

1. Keep `README.md` aligned with the current Dashboard, `/workspace`, and `/tasks` flow.
2. Keep completed superpowers plans as history and mark paused plans clearly.
3. Resolve or explicitly accept existing Python `datetime.utcnow()` deprecation warnings.
4. Run the backend test suite, frontend build, and product page structural checks before any release branch or PR.
5. Review the 27 local commits ahead of `origin/master` and decide whether to squash, push, or split.

Success criteria:

- A new developer can follow the docs without guessing which page starts the flow.
- The git history and untracked docs do not obscure the active next task.
- Verification commands are documented and current.

## Not Next

These should wait:

- More homepage redesign.
- Full CSS Module to Tailwind migration for `/workspace` and `/tasks`.
- New dashboard analytics fields.
- Large workflow-engine refactors.
- Authentication, multi-user permissions, or billing.

## Suggested Immediate Order

1. Commit the current test-contract fix and documentation updates.
2. Run a real local end-to-end worker-backed session.
3. Document the runbook gaps found during that session.
4. Add local fixture fallback if external asset download blocks repeatable verification.
5. Revisit UI polish only after the real execution path is predictable.

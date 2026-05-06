# P0 Workflow Hardening Design

Date: 2026-05-06

## Goal

Make ClipForge reliable enough for a real user to go from `/workspace` brief intake to `/tasks` execution tracking to a rendered MP4, with clear recovery guidance when the run fails.

This stage is about release readiness, not feature expansion. The product already has the three-page flow in place:

1. `/` for overview and entry points
2. `/workspace` for brief intake, plan generation, option selection, confirmation, and progress handoff
3. `/tasks` for task list management, detail review, events, clips, and result links

The next step is to prove that this flow works predictably in a real local environment and that failures are understandable without developer intervention.

## Non-Goals

- Do not reopen dashboard redesign work.
- Do not continue a broad Tailwind migration across unrelated pages.
- Do not add new dashboard metrics, backend schema fields, or analytics contracts in this stage.
- Do not introduce large workflow-engine refactors.
- Do not treat YouTube stability as the only gate for release readiness.

## Current Context

The current codebase already covers most of the product workflow surface:

- `src/components/workspace/BriefWorkspacePage.tsx` can restore a session, show execution handoff, and jump to relevant result or failure sections.
- `src/components/tasks/TaskManagerPage.tsx` now renders a Tailwind-based B1 list-plus-modal workflow, shows step snapshots, events, clips, and result links, and can jump back into `/workspace`.
- `backend/services/search_service.py` supports provider ordering and now stops searching fallback providers once a provider has returned usable candidates.
- `tests/test_agent_backend.py` contains frontend contract coverage for `/workspace`, `/tasks`, and backend provider behavior.
- `scripts/check-product-pages.mjs` checks the structural output of key product pages after a production build.

The unresolved gap is no longer page structure. It is operational confidence:

- Can a fresh local checkout run the full flow without tribal knowledge?
- Can a failed run be classified as search, download, render, or environment failure?
- Is the next recommended action obvious to the operator?

## Recommended Approach

Treat this stage as **P0 workflow hardening and release readiness** with four tightly scoped tracks:

1. End-to-end execution verification
2. Failure handling and recovery clarity
3. Asset-source reproducibility for dev/demo
4. Release hygiene and runbook alignment

This keeps the work focused on whether the system is usable in practice, not whether it looks more complete on paper.

## Track 1: End-To-End Execution Verification

The primary job is to prove the happy path in a real local environment.

Required environment components:

- PostgreSQL
- Redis
- FastAPI backend
- Celery worker on an explicit queue
- Next.js frontend
- FFmpeg
- Current asset-provider configuration

The workflow to verify is:

1. Start infrastructure and app services in a documented order.
2. Open `/workspace`.
3. Submit a real brief.
4. Wait for standard steps 1-4 to complete.
5. Confirm a direction and create a task.
6. Verify `/tasks` shows the same execution and linked session context.
7. Wait for the worker to search, download, render, and publish output.
8. Verify the MP4 exists, is playable, and is reachable through the frontend.

If the run fails, the verification is still valuable, but only if the exact failing phase and reproduction context are recorded.

## Track 2: Failure Handling And Recovery

The second job is to make failed runs legible.

The system should classify failures into a small set of understandable buckets:

- asset search failure
- asset download failure
- render failure
- environment or dependency failure
- configuration failure

The UI does not need a new retry system in this stage. It needs consistency:

- `/workspace` and `/tasks` should point to the same failing state
- failed step labels should match the real failing phase
- event details should preserve useful diagnostics without dumping raw stack traces into user-facing text
- known external-source issues should map to explicit guidance, such as:
  - YouTube anti-bot or PO token requirements
  - missing API keys
  - unavailable media
  - FFmpeg/runtime missing or misconfigured

This stage should prefer clear manual recovery guidance over half-implemented task-level retry controls.

## Track 3: Asset Source Reproducibility

The current product can use real external sources, but external volatility makes repeated verification expensive.

For this stage, the design should support two different operating modes:

1. **Real external mode**
   - used for proving the production-shaped flow
   - provider order can remain `pexels,youtube` or another configured order
   - demonstrates that a real run can produce a real MP4

2. **Deterministic dev/demo mode**
   - used for repeatable local verification and demos
   - should not depend entirely on live YouTube behavior

The recommended direction is a hybrid strategy:

- Keep real external providers for real-world validation
- Add or plan for a local fixture pool for deterministic demos and repeated P0 checks

This avoids over-investing in YouTube reliability while still keeping the product honest about real-source behavior.

## Track 4: Release Hygiene

Release readiness depends on making the current repo understandable and reproducible.

This stage should align:

- `README.md`
- superpowers design/plan docs for the current workflow phases
- environment assumptions
- verification command order

At the end of the stage, a collaborator should be able to answer:

- Which page starts the user journey?
- Which commands boot the local stack?
- Which queue should the worker listen on?
- Which environment variables are required for a successful real run?
- What counts as a successful integration run?
- What counts as an acceptable failure report?

## Implementation Boundaries

The design intentionally prefers narrow fixes over broad renovation.

Allowed work in this stage:

- runbook and README updates
- environment and startup verification
- failure-message clarification
- step-mapping fixes
- deterministic verification support for asset sourcing
- small UI copy or affordance adjustments tied directly to failed-run comprehension

Not allowed in this stage:

- redesigning `/workspace` or `/tasks` from scratch
- expanding the API contract for speculative future UI
- replacing Celery, workflow orchestration, or rendering architecture
- polishing unrelated visual details

## Testing And Verification Strategy

This stage should use both automated and manual verification.

Automated verification:

1. `python -m unittest tests.test_agent_backend`
2. `npm run build`
3. `node scripts/check-product-pages.mjs`

Manual verification:

1. start local infra and app services
2. run a real `/workspace` session
3. confirm `/tasks` reflects the same task/session
4. verify either:
   - final MP4 success, or
   - precise, user-readable failure with enough context to act on

The verification order matters. The structural page check must run after a fresh production build so it reads current `.next` output.

## Documentation Updates

At minimum, this stage should update:

- `README.md`
- the active implementation plan for workflow hardening
- any paused or superseded plan notes that would confuse the next operator

Documentation should explicitly cover:

- service startup order
- queue naming
- required environment variables
- expected local ports
- successful run evidence
- common failure signatures
- when to use real external providers versus deterministic local fixtures

## Acceptance Criteria

This stage is complete when all of the following are true:

1. A documented local setup can run the full workflow from `/workspace` to `/tasks` to result verification.
2. A successful run produces a real MP4 that can be opened from the product UI.
3. A failed run surfaces the correct failed step and a useful next action.
4. The verification command set is current and passes in the documented order.
5. README and stage docs reflect the actual product flow and environment assumptions.
6. The next engineer can tell whether a problem is in environment setup, asset sourcing, worker execution, or rendering without re-reading the whole codebase.

## Recommended Immediate Sequence

1. Write the implementation plan for P0 workflow hardening.
2. Run one real end-to-end local session with the current stack.
3. Record the exact success path or exact failure point.
4. Fix only the gaps exposed by that run.
5. Add deterministic asset verification support if repeated real runs remain too volatile.
6. Re-run the automated verification suite and update docs before any release-oriented merge.

## Resolved Decisions

The next stage is centered on **operational confidence**, not more UI breadth.

The preferred order is:

1. real workflow proof
2. failure clarity
3. deterministic dev/demo support
4. release hygiene

Further visual polish or broader Tailwind migration should wait until the real execution path is stable enough that polish work is not masking operational uncertainty.

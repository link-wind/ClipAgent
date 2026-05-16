# ClipForge Release Readiness Smoke Design

## Context

ClipForge `master` now has a stable three-surface product flow and a deterministic local asset provider:

- `/workspace` handles brief intake, plan generation, confirmation, and execution handoff.
- `/tasks` exposes task list, detail, events, clips, and result entry points.
- The backend supports `fixture`, `pexels`, and `youtube` asset providers, with `fixture` designed as a deterministic local fallback for demos and local validation.

Recent work has hardened the P0 workflow, improved failure handling, and aligned confirm behavior across the workspace and legacy agent chat surfaces. The next risk is no longer missing product flow; it is whether the core pipeline can be revalidated quickly and repeatably on `master`.

## Problem

The repo has tests, build checks, and runbook notes, but it does not yet have a clearly defined release-readiness smoke baseline that proves the integrated backend execution path still works end to end under a deterministic provider setup.

Without that baseline:

- developers cannot quickly distinguish a UI regression from a worker/config/render regression
- demo success depends too heavily on ad hoc local knowledge
- external provider instability can obscure whether the core product pipeline is actually healthy

## Goal

Add a minimum release-readiness smoke layer for `master` that proves ClipForge can reliably complete a worker-backed run in deterministic `fixture` mode and produce a final MP4 output.

This smoke layer must validate the integrated path across:

- API session creation and confirmation
- worker job consumption
- fixture asset selection and local copy flow
- render completion
- final result surfacing as a `videoUrl` and output file

## Non-Goals

This stage does not:

- add browser automation for `/workspace` or `/tasks`
- expand dashboard or homepage functionality
- rework the workflow engine or task model
- solve long-term YouTube anti-bot or PO token stability
- perform a broad CSS Module to Tailwind migration

## Recommended Approach

Use a three-layer smoke design:

1. **Contract tests** protect fixture-mode backend behavior and output expectations.
2. **An executable smoke script** runs a real integrated session through API + worker + fixture render flow.
3. **Runbook/documentation updates** define stable smoke mode separately from real external-provider validation.

This balances regression protection with operational usefulness. Tests keep the contract explicit; the script provides a concrete runnable smoke entry point; the docs explain when to use fixture mode versus real provider mode.

## Design

### 1. Test Layer

Add or extend backend-facing tests so the smoke baseline has explicit regression coverage for deterministic fixture runs.

The tests should verify:

- fixture-first provider order can complete a confirmed session
- completed sessions expose a usable `videoUrl`
- output artifacts resolve to expected local/public paths
- fixture provider fallback behavior remains deterministic when configured

These tests are not meant to replace a real smoke run. They exist to keep the expected integrated fixture behavior locked down in fast, repeatable automated checks.

### 2. Script Layer

Add a dedicated smoke runner under `scripts/` that exercises the integrated backend path using the running local services.

The script should:

1. create a session through the API
2. submit or confirm a deterministic fixture-friendly brief
3. poll session or job state until completion or timeout
4. inspect the final session/task payload
5. verify that the reported result file exists locally
6. print a compact success or failure summary

The script should not drive the browser. Its responsibility is backend integration verification only.

The output should be readable by a developer and should clearly report which layer failed:

- API create/confirm failure
- worker did not pick up the job
- fixture provider returned no usable candidate
- asset copy/download failed
- render failed
- result file missing despite completed status

### 3. Documentation Layer

Update `README.md` so ClipForge’s operating modes are clearly separated:

- **Smoke / demo mode:** `fixture,pexels,youtube`
- **Real external-provider validation:** `pexels,youtube`
- **Single-provider debugging:** one provider explicitly enabled while others are disabled or removed from order

The smoke runbook should document:

- required services
- required environment variables
- recommended queue isolation
- backend / worker / frontend startup commands
- the smoke script command
- what counts as success
- what counts as fixture-smoke success versus external-provider success

## Data and Interface Expectations

No new product-facing API schema is required.

This stage should reuse the current session/task contracts and backend result model. If a small helper structure is needed for the smoke script output, it should remain script-local rather than forcing a new API field.

The script may read:

- session status
- current step
- job id
- events
- clips
- `videoUrl`

The script may also check the local output path implied by the result or known output conventions, but it should not mutate backend code paths just to make the script easier to write unless that change also improves production clarity.

## Failure Handling

The smoke layer must make failures easier to classify, not just easier to observe.

Expected behavior:

- Timeouts are reported separately from explicit failed states.
- Failed states include the highest-signal step name and recent event context when available.
- Missing output artifacts after a reported success are surfaced as a distinct failure class.

This classification is especially important because one of the main reasons for this stage is to separate deterministic core-flow breakage from flaky external-provider behavior.

## Testing Strategy

Before considering this stage complete, the following should be true:

- backend contract tests pass
- frontend build passes
- product page structural checks still pass
- the smoke script succeeds in fixture-first mode against a correctly started local stack

The smoke script itself should be documented as a manual or CI-friendly command, even if CI wiring is deferred to a later phase.

## Acceptance Criteria

This stage is complete when:

1. A developer can follow the docs on `master` and run a deterministic smoke flow without relying on tribal knowledge.
2. The smoke script can validate API + worker + fixture + render integration and report a clear outcome.
3. The automated test suite contains explicit regression coverage for the expected deterministic fixture behavior.
4. The documented success criteria clearly distinguish fixture smoke success from real external-provider validation.

## Deferred Work

The following remain valid next steps, but are intentionally deferred:

- CI integration for the smoke script
- browser-driven user-flow automation
- stronger `/workspace -> /tasks` UI-level acceptance automation
- broader provider diagnostics or retry UX
- additional external providers beyond the current stack

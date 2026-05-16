# Execution Feedback Query Rewrite Design

Date: 2026-05-09

## Goal

Make Phase 4 execution-feedback replanning smarter than the current unconditional `"alternative"` suffix by letting the deterministic planner rewrite failed-scene search queries based on the observed failure reason.

This stage should improve the quality of automatic retry plans without changing the existing worker queue flow, API shape, or overall LangGraph orchestration.

## Current Context

The current Phase 4 loop on branch `codex/model-driven-agent-phase0-1` already supports:

1. Worker-side detection of retryable search failures
2. Persistence of execution feedback observations
3. Automatic creation of a replanned plan version
4. Automatic creation and redispatch of a replacement queued job
5. Scene-level `failedSceneIds` propagation from search/download failures into execution feedback

The remaining weakness is inside `backend/services/planner_runtime_deterministic.py`.

`replan_after_execution_feedback(...)` currently rewrites every failed scene the same way:

- append `"alternative"` to `keywords`
- rebuild `searchQuery` from that updated keyword list

This means the planner can tell *which* scenes failed, but it still cannot react differently to *why* they failed.

Examples:

- A YouTube anti-bot or PO token failure should encourage a more stock-footage-friendly fallback query.
- A no-results / no-downloadable-candidates failure should keep scene intent but broaden it.
- A generic transient download failure can stay closer to the current alternative-candidate behavior.

## Non-Goals

This design does not include:

- enabling OpenAI/LangChain-driven execution-feedback replanning yet
- changing the `SearchExecutionFeedback` schema
- adding provider-level structured diagnostics to persisted execution feedback
- changing worker dispatch, queue semantics, or retry limits
- modifying provider fallback behavior in `search_service`
- changing public API response models

This is a narrow planner-runtime improvement only.

## Recommended Approach

Add a small deterministic failure-classification and query-rewrite layer inside `backend/services/planner_runtime_deterministic.py`.

The runtime should:

1. classify `execution_feedback.failureReason` into a small number of stable categories
2. rewrite only the failed scenes
3. preserve untouched scenes exactly as they are
4. record the classification and rewrite strategy in `replanHistory`

This keeps the current architecture intact:

- `search_service` and worker produce feedback
- `PlannerOrchestrator` persists observations and plan versions
- LangGraph continues to orchestrate replanning
- the deterministic runtime becomes a better local stand-in for the future LangChain/OpenAI runtime

## Approaches Considered

### Approach A: Keep the unconditional `"alternative"` suffix

Pros:

- no extra logic
- minimal maintenance

Cons:

- does not use the richer execution feedback now available
- produces weak or repetitive replans
- does not move the system meaningfully closer to a model-driven planning loop

This is no longer enough.

### Approach B: Deterministic failure-aware rewrite rules

Pros:

- very small scope
- immediate product value
- preserves explainability and testability
- creates stable semantics that a future OpenAI runtime can later emulate or replace

Cons:

- still heuristic
- rule quality is bounded by the failure text available today

This is the recommended approach.

### Approach C: Replace execution-feedback replanning with OpenAI runtime now

Pros:

- closest to the long-term “model-driven agent plan” direction
- potentially more flexible query rewriting

Cons:

- materially larger scope
- requires prompt design, output-structure constraints, and new failure handling
- mixes a runtime migration with a behavior tweak

This should come later, after the deterministic loop is sharper.

## Failure Categories

The deterministic runtime should classify failure reasons into four categories:

1. `platform_blocked`
   - examples: `PO Token`, `Sign in`, `not a bot`, `challenge`, `signature`, `401`, `403`
   - meaning: the current query/provider path is likely too platform-specific or blocked

2. `no_inventory`
   - examples: `没有返回候选素材`, `没有可下载候选素材`, `没有下载到可用素材`
   - meaning: the query is too narrow or the provider inventory is too sparse

3. `download_transient`
   - examples: `download failed`, `timeout`, `connection reset`
   - meaning: the scene intent is probably still valid, but the candidate path should change

4. `generic_retry`
   - catch-all fallback for any other failure reason

The category names should stay stable and implementation-local. They do not need to become new API fields in this stage.

## Rewrite Strategies

Only scenes whose `id` appears in `execution_feedback.failedSceneIds` should be rewritten.

### `platform_blocked`

Goal: stop leaning on the existing provider-specific or brand-heavy search path and move toward more generic stock-footage language.

Recommended behavior:

- if the failed scene keywords are interface/product oriented, rewrite toward terms like `software dashboard laptop`
- if the failed scene keywords are workflow/feature oriented, rewrite toward terms like `team workflow laptop`
- otherwise, keep the leading scene intent and add a generic stock-footage style fallback such as `stock footage`

This category is the most aggressive rewrite.

### `no_inventory`

Goal: preserve the original scene intent but broaden the search slightly.

Recommended behavior:

- keep the original core keywords
- append one broadening token such as `generic`
- rebuild `searchQuery` from the expanded list

This category is a mild semantic broadening, not a full pivot.

### `download_transient`

Goal: keep the scene intent mostly intact while forcing a new candidate path.

Recommended behavior:

- preserve the existing core keywords
- append `alternative`

This category is closest to the current behavior.

### `generic_retry`

Goal: provide a safe fallback when the failure text does not match any known category.

Recommended behavior:

- same behavior as `download_transient` for now

This keeps the system predictable and avoids overfitting ambiguous errors.

## Replan History Contract

The execution-feedback replan history entry should be extended from:

- `triggerType`
- `summary`
- `failedSceneIds`
- `failureReason`

to include:

- `failureCategory`
- `rewriteStrategy`

This keeps the planner trace explainable without inflating the payload with per-scene before/after snapshots in this stage.

`queryBefore` / `queryAfter` are explicitly deferred. They may be useful later, but they are not necessary for this narrow change.

## Testing Strategy

Use TDD and focus on planner-runtime behavior first.

Required new tests:

1. `platform_blocked` rewrites a failed scene to a more generic stock-footage-friendly query instead of only appending `"alternative"`
2. `no_inventory` broadens the failed scene while preserving its original semantic core
3. only scenes listed in `failedSceneIds` are changed; untouched scenes remain exactly the same
4. `replanHistory` records `failureCategory` and `rewriteStrategy`

Suggested test locations:

- `tests/test_planner_runtime.py` for the main red-green loop
- optionally `tests/test_agent_planner_phase4.py` for one integration-style assertion that the replanned plan version contains the smarter rewritten query

Regression verification after implementation:

- `python -m unittest tests.test_planner_runtime -v`
- `python -m unittest tests.test_agent_planner_phase4 -v`
- `python -m unittest tests.test_agent_jobs tests.test_agent_planner_phase4 tests.test_agent_api_p0 -v`

## Acceptance Criteria

1. Failed scenes no longer all receive the same unconditional `"alternative"` rewrite.
2. Failure reasons associated with provider blocking produce a more generic fallback query.
3. No-inventory failures broaden the query without discarding the original scene intent.
4. Only failed scenes are rewritten.
5. `replanHistory` records both the failure category and the rewrite strategy.
6. Existing Phase 4 worker requeue/redispatch behavior remains unchanged.
7. Existing focused planner, worker, and API regression tests continue to pass.

## Resolved Decisions

The first improvement stays entirely inside the deterministic runtime even though the broader architecture is LangChain/LangGraph-oriented. This is intentional: the deterministic layer is currently the lowest-risk place to sharpen behavior while keeping the orchestration contract stable.

We also intentionally keep failure classification text-driven rather than introducing a larger structured diagnostics schema. That schema work may still be valuable later, but it is a separate step from this targeted planner improvement.

# Model-Driven Agent Plan Phase 2 (Grounding Replan) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace template-based grounding confirmation plan generation with planner-driven `replan_after_grounding`, while keeping `/api/agent/sessions/{id}/grounding/confirm` request/response contract stable.

**Architecture:** Keep the current API surface and DB schema, but extend the planner runtime/graph so grounding confirmation runs through a dedicated replanning path. `AgentSessionService.confirm_grounding_candidates()` should persist a grounding observation, invoke planner graph replanning, create immutable `agent_plans` v2 with `parent_plan_id` and `trigger_type`, update `current_plan_id`/`planner_trace_json`, and return the same frontend-compatible `EditPlan` projection from `execution_plan_json`.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, LangGraph, LangChain runtime abstraction, unittest

---

## File Structure

### New files

- `tests/test_agent_planner_phase2.py`
  - Integration coverage for grounding confirmation -> observation -> plan v2 persistence chain.

### Modified files

- `backend/services/planner_models.py`
  - Add grounding feedback contracts used by runtime and graph replan nodes.
- `backend/services/planner_runtime_deterministic.py`
  - Implement deterministic `replan_after_grounding(...)`.
- `backend/services/planner_runtime_openai.py`
  - Add `replan_after_grounding(...)` method signature (stub for now) to keep runtime contract consistent.
- `backend/services/planner_graph.py`
  - Add replanning state and `run_grounding_replan(...)` path.
- `backend/services/planner_orchestrator.py`
  - Add `persist_grounding_replan(...)` orchestration that writes observation + new immutable plan version.
- `backend/services/agent_session_service.py`
  - Replace `_build_grounded_plan_from_candidates(...)` usage in confirm flow with planner-orchestrated replan.
- `tests/test_planner_models.py`
  - Add model tests for grounding feedback payload structure.
- `tests/test_planner_runtime.py`
  - Add deterministic runtime replanning tests.
- `tests/test_planner_graph.py`
  - Add graph-level grounding replanning test.
- `tests/test_agent_backend.py`
  - Update confirm-candidates expectations to assert planner-driven version metadata.
- `tests/test_agent_persistence.py`
  - Assert confirmed grounding path writes observation + versioned plan linkage correctly.
- `tests/test_agent_api_p0.py`
  - Keep API response contract checks intact while validating planner-backed confirm behavior.

## Scope Guardrails

- This phase only implements `replan_after_grounding`; no `replan_after_user_revision` and no execution-feedback auto-replan.
- This phase does not change frontend routes/components or confirmation payload shape.
- This phase does not add new DB columns; it uses existing `current_plan_id`, `planner_trace_json`, `agent_observations`, and `agent_plans` version fields.
- If runtime mode is `openai`, grounding replan may stay explicit `NotImplementedError` in this phase; deterministic mode remains primary execution path for tests and local dev.

### Task 1: Add grounding feedback contracts and deterministic replan runtime

**Files:**
- Modify: `backend/services/planner_models.py`
- Modify: `backend/services/planner_runtime_deterministic.py`
- Modify: `backend/services/planner_runtime_openai.py`
- Test: `tests/test_planner_models.py`
- Test: `tests/test_planner_runtime.py`

- [ ] **Step 1: Write failing model and runtime tests**

Add tests:

```python
def test_grounding_feedback_contract_defaults(self):
    from backend.services.planner_models import (
        CandidateConfirmationFeedback,
        GroundingFeedback,
    )

    feedback = GroundingFeedback(
        productName="Notion",
        audience="销售团队",
        styleHint="快节奏社媒短片",
        selectedCandidateIds=["fixture:1", "fixture:2"],
        candidates=[{"id": "fixture:1", "title": "Notion product demo"}],
    )
    confirmation = CandidateConfirmationFeedback(
        selectedCandidateIds=["fixture:1", "fixture:2"],
        confirmationSource="user_select",
    )

    self.assertEqual(feedback.selectedCandidateIds, ["fixture:1", "fixture:2"])
    self.assertEqual(confirmation.confirmationSource, "user_select")
```

```python
def test_deterministic_runtime_replans_after_grounding(self):
    from backend.services.planner_models import (
        CandidateConfirmationFeedback,
        GroundingFeedback,
    )
    from backend.services.planner_runtime_deterministic import (
        DeterministicPlannerRuntime,
    )

    runtime = DeterministicPlannerRuntime()
    current_agent, current_execution = runtime.build_plan_from_brief("给 Notion AI 做一个产品短片")
    next_agent, next_execution, change_summary = runtime.replan_after_grounding(
        current_agent=current_agent,
        current_execution=current_execution,
        grounding_feedback=GroundingFeedback(
            productName="Notion",
            audience="销售团队",
            styleHint="商务演示风格",
            featureHints=["协作", "看板"],
            selectedCandidateIds=["fixture:1", "fixture:2"],
            candidates=[{"id": "fixture:1", "title": "Notion dashboard"}],
        ),
        confirmation_feedback=CandidateConfirmationFeedback(
            selectedCandidateIds=["fixture:1", "fixture:2"],
            confirmationSource="user_select",
        ),
    )

    self.assertIn("grounding", change_summary)
    self.assertEqual(next_execution.style, "商务演示风格")
    self.assertEqual(next_execution.scenes[0].groundingCandidateIds, ["fixture:1", "fixture:2"])
    self.assertGreaterEqual(len(next_agent.replanHistory), 1)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models tests.test_planner_runtime -v
```

Expected: FAIL because `GroundingFeedback` / `CandidateConfirmationFeedback` / `replan_after_grounding` do not exist yet.

- [ ] **Step 3: Implement feedback models and deterministic replanning**

Update `backend/services/planner_models.py` with:

```python
class GroundingFeedback(BaseModel):
    productName: str = ""
    audience: str = ""
    styleHint: str = ""
    featureHints: list[str] = Field(default_factory=list)
    selectedCandidateIds: list[str] = Field(default_factory=list)
    candidates: list[dict] = Field(default_factory=list)


class CandidateConfirmationFeedback(BaseModel):
    selectedCandidateIds: list[str] = Field(default_factory=list)
    confirmationSource: Literal["user_select", "api_confirm"] = "api_confirm"
```

Update `backend/services/planner_runtime_deterministic.py` with:

```python
def replan_after_grounding(
    self,
    *,
    current_agent: AgentPlan,
    current_execution: ExecutionPlan,
    grounding_feedback: GroundingFeedback,
    confirmation_feedback: CandidateConfirmationFeedback,
) -> tuple[AgentPlan, ExecutionPlan, str]:
    selected_ids = (
        confirmation_feedback.selectedCandidateIds
        or grounding_feedback.selectedCandidateIds
    )
    style = grounding_feedback.styleHint or current_execution.style
    feature_hints = grounding_feedback.featureHints or ["product", "workflow"]

    next_execution = current_execution.model_copy(
        update={
            "style": style,
            "scenes": [
                scene.model_copy(
                    update={
                        "keywords": feature_hints[:2] or scene.keywords,
                        "searchQuery": " ".join(feature_hints[:2] or scene.keywords),
                        "groundingCandidateIds": selected_ids,
                    }
                )
                for scene in current_execution.scenes
            ],
        }
    )
    next_agent = current_agent.model_copy(
        update={
            "replanHistory": [
                *current_agent.replanHistory,
                {
                    "triggerType": "grounding_confirmation",
                    "selectedCandidateIds": selected_ids,
                    "summary": "基于候选确认完成重规划",
                },
            ],
            "scenes": [
                scene.model_copy(
                    update={
                        "groundingCandidateIds": selected_ids,
                        "status": "grounded",
                    }
                )
                for scene in current_agent.scenes
            ],
            "grounding": {
                **current_agent.grounding,
                "selectedCandidateIds": selected_ids,
                "productName": grounding_feedback.productName,
                "audience": grounding_feedback.audience,
            },
        }
    )
    return next_agent, next_execution, "grounding 确认后已重规划"
```

Update `backend/services/planner_runtime_openai.py` with:

```python
def replan_after_grounding(...):
    raise NotImplementedError(
        "OpenAI grounding replanning runtime is enabled in later tasks of the rollout"
    )
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models tests.test_planner_runtime -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/planner_models.py backend/services/planner_runtime_deterministic.py backend/services/planner_runtime_openai.py tests/test_planner_models.py tests/test_planner_runtime.py
git commit -m "feat: add grounding feedback contracts and deterministic replan"
```

### Task 2: Add LangGraph grounding replan path and orchestrator persistence

**Files:**
- Modify: `backend/services/planner_graph.py`
- Modify: `backend/services/planner_orchestrator.py`
- Test: `tests/test_planner_graph.py`
- Test: `tests/test_agent_planner_phase2.py`

- [ ] **Step 1: Write failing graph/orchestrator tests**

Add graph test:

```python
def test_run_grounding_replan_returns_replanning_complete_state(self):
    from backend.services.planner_graph import run_grounding_replan
    from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

    runtime = DeterministicPlannerRuntime()
    current_agent, current_execution = runtime.build_plan_from_brief("做一个产品视频")
    state = run_grounding_replan(
        session_id="session-1",
        current_agent_plan=current_agent.model_dump(mode="json"),
        current_execution_plan=current_execution.model_dump(mode="json"),
        grounding_feedback={
            "productName": "Notion",
            "selectedCandidateIds": ["fixture:1"],
            "candidates": [{"id": "fixture:1", "title": "Notion demo"}],
        },
        confirmation_feedback={
            "selectedCandidateIds": ["fixture:1"],
            "confirmationSource": "user_select",
        },
    )

    self.assertEqual(state["status"], "replanning_complete")
    self.assertEqual(state["triggerType"], "grounding_confirmation")
    self.assertIn("changeSummary", state)
```

Add integration test skeleton in `tests/test_agent_planner_phase2.py`:

```python
def test_confirm_grounding_persists_observation_and_plan_v2(self):
    service = AgentSessionService(session_factory=self.session_factory)
    session = service.create_session()
    awaiting = service.add_user_message(session.id, "给 Notion AI 做一个 30 秒产品亮点视频")
    selected_ids = [candidate.id for candidate in awaiting.grounding.candidates[:2]]

    grounded = service.confirm_grounding_candidates(session.id, selected_ids)

    self.assertEqual(grounded.grounding.status, "confirmed")
    self.assertEqual(grounded.grounding.selectedCandidateIds, selected_ids)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_graph tests.test_agent_planner_phase2 -v
```

Expected: FAIL because `run_grounding_replan` and phase2 orchestration are missing.

- [ ] **Step 3: Implement graph replan node**

Update `backend/services/planner_graph.py`:

```python
class PlanningState(TypedDict, total=False):
    sessionId: str
    brief: str
    status: str
    triggerType: str
    agentPlan: dict
    executionPlan: dict
    groundingFeedback: dict
    confirmationFeedback: dict
    changeSummary: str


def _replan_after_grounding_node(state: PlanningState) -> PlanningState:
    runtime = get_planner_runtime()
    current_agent = AgentPlan.model_validate(state["agentPlan"])
    current_execution = ExecutionPlan.model_validate(state["executionPlan"])
    next_agent, next_execution, change_summary = runtime.replan_after_grounding(
        current_agent=current_agent,
        current_execution=current_execution,
        grounding_feedback=GroundingFeedback.model_validate(state["groundingFeedback"]),
        confirmation_feedback=CandidateConfirmationFeedback.model_validate(state["confirmationFeedback"]),
    )
    return {
        **state,
        "status": "replanning_complete",
        "triggerType": "grounding_confirmation",
        "agentPlan": next_agent.model_dump(mode="json"),
        "executionPlan": next_execution.model_dump(mode="json"),
        "changeSummary": change_summary,
    }
```

and add:

```python
def run_grounding_replan(... ) -> PlanningState:
    graph = build_planning_graph()
    return graph.invoke({...})
```

- [ ] **Step 4: Implement orchestrator persist method**

Update `backend/services/planner_orchestrator.py`:

```python
def persist_grounding_replan(self, db, session_record, candidate_ids: list[str]):
    plan_repo = AgentPlanRepository(db)
    observation_repo = AgentObservationRepository(db)
    settings = get_settings()

    latest_plan = plan_repo.get_latest_for_session(session_record.id)
    if latest_plan is None:
        raise RuntimeError("Grounding replan requires an existing plan version")

    grounding_summary = session_record.grounding_summary_json or {}
    state = run_grounding_replan(
        session_id=session_record.id,
        current_agent_plan=latest_plan.plan_json,
        current_execution_plan=latest_plan.execution_plan_json,
        grounding_feedback={
            **grounding_summary,
            "selectedCandidateIds": candidate_ids,
        },
        confirmation_feedback={
            "selectedCandidateIds": candidate_ids,
            "confirmationSource": "user_select",
        },
    )

    observation_repo.create(
        session_id=session_record.id,
        plan_id=latest_plan.id,
        observation_type="grounding_confirmation",
        summary="用户确认候选产品画面并触发重规划",
        payload_json={"selectedCandidateIds": candidate_ids},
    )

    next_plan = plan_repo.create(
        session_id=session_record.id,
        version=latest_plan.version + 1,
        parent_plan_id=latest_plan.id,
        trigger_type="grounding_confirmation",
        planner_mode=settings.planner_mode,
        planner_model=settings.planner_model,
        title=state["executionPlan"]["title"],
        target_duration=int(state["executionPlan"]["targetDuration"]),
        style=state["executionPlan"]["style"],
        plan_json=state["agentPlan"],
        execution_plan_json=state["executionPlan"],
        change_summary=state["changeSummary"],
        status="ready",
    )
    session_record.current_plan_id = next_plan.id
    session_record.planner_trace_json = {
        "lastPlanningState": state["status"],
        "triggerType": state["triggerType"],
    }
    return next_plan
```

- [ ] **Step 5: Run tests and verify pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_graph tests.test_agent_planner_phase2 -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/planner_graph.py backend/services/planner_orchestrator.py tests/test_planner_graph.py tests/test_agent_planner_phase2.py
git commit -m "feat: add grounding replan graph and orchestrator persistence"
```

### Task 3: Migrate confirm grounding flow to planner-driven replan

**Files:**
- Modify: `backend/services/agent_session_service.py`
- Modify: `tests/test_agent_backend.py`
- Modify: `tests/test_agent_persistence.py`
- Modify: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Write failing confirm-flow regression tests**

Add/adjust tests so they assert planner version lineage instead of template-only plan creation:

```python
def test_confirm_candidates_creates_replan_version_with_parent_link(self):
    from backend.db.repositories import AgentObservationRepository, AgentPlanRepository

    created = self.session_service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
    self.assertIsNotNone(created.plan)
    with self.session_factory() as db:
        latest = AgentPlanRepository(db).get_latest_for_session(created.id)
        self.assertEqual(latest.version, 1)
        parent_id = latest.id

    follow_up = self.session_service.add_user_message(created.id, "补充真实产品画面候选确认")
    selected_ids = [candidate.id for candidate in follow_up.grounding.candidates[:2]]
    grounded = self.session_service.confirm_grounding_candidates(created.id, selected_ids)

    self.assertEqual(grounded.grounding.selectedCandidateIds, selected_ids)
    with self.session_factory() as db:
        latest = AgentPlanRepository(db).get_latest_for_session(created.id)
        observations = AgentObservationRepository(db).list_for_session(created.id)
        self.assertEqual(latest.version, 2)
        self.assertEqual(latest.parent_plan_id, parent_id)
        self.assertEqual(latest.trigger_type, "grounding_confirmation")
        self.assertEqual(observations[-1].observation_type, "grounding_confirmation")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend tests.test_agent_persistence tests.test_agent_api_p0 -v
```

Expected: FAIL because confirm flow still calls `_build_grounded_plan_from_candidates(...)` and does not persist planner-driven replan metadata.

- [ ] **Step 3: Replace confirm flow implementation**

Update `backend/services/agent_session_service.py` `confirm_grounding_candidates(...)`:

```python
planner_orchestrator = PlannerOrchestrator()
latest_plan = plan_repo.get_latest_for_session(session_id)

if latest_plan is None:
    # compatibility fallback for sessions created before planner-first path
    grounded_plan = self._build_grounded_plan_from_candidates(...)
    ...
else:
    plan_record = planner_orchestrator.persist_grounding_replan(
        db=db,
        session_record=session_record,
        candidate_ids=candidate_ids,
    )
    grounded_plan = execution_plan_to_edit_plan(plan_record.execution_plan_json)
    self._apply_plan_to_session(session_record, grounded_plan)
    session_repo.set_current_plan(session_id, plan_record.id)
```

Keep existing grounding-state update:

```python
session_repo.update_grounding_state(
    session_id,
    grounding_status="confirmed",
    grounding_summary_json={
        **grounding_summary,
        "status": "confirmed",
        "selectedCandidateIds": candidate_ids,
    },
    selected_candidate_ids_json=candidate_ids,
)
```

Do not change endpoint path or request shape.

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend tests.test_agent_persistence tests.test_agent_api_p0 -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/agent_session_service.py tests/test_agent_backend.py tests/test_agent_persistence.py tests/test_agent_api_p0.py
git commit -m "feat: route grounding confirm through planner replan"
```

### Task 4: End-to-end verification and regression safety net

**Files:**
- Modify: `tests/test_agent_jobs.py`
- Modify: `tests/test_agent_planner_phase2.py`

- [ ] **Step 1: Add job-flow regression assertions**

Ensure execution path still works after planner-driven confirm:

```python
def test_confirm_session_still_queues_job_after_planner_replan(self):
    session = self.session_service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
    selected_ids = [candidate.id for candidate in session.grounding.candidates[:2]]
    grounded = self.session_service.confirm_grounding_candidates(session.id, selected_ids)

    confirmed = self.execution_service.confirm_session(grounded.id)
    self.assertEqual(confirmed.status.value, "queued")
    self.assertIsNotNone(confirmed.activeJobId)
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_jobs tests.test_agent_planner_phase2 -v
```

Expected: PASS

- [ ] **Step 3: Run full planner + backend regression suite**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models tests.test_planner_runtime tests.test_planner_graph tests.test_agent_planner_phase1 tests.test_agent_planner_phase2 tests.test_agent_backend tests.test_agent_persistence tests.test_agent_api_p0 tests.test_agent_jobs -v
```

Expected: All PASS.

- [ ] **Step 4: Commit verification-driven test hardening**

```bash
git add tests/test_agent_jobs.py tests/test_agent_planner_phase2.py
git commit -m "test: harden grounding replan execution regressions"
```

---

## Spec Coverage Self-Review

- Phase 2 requirement “grounding confirmation triggers replan”: covered by Task 2 + Task 3.
- Observation write before/with replan: covered by Task 2 `persist_grounding_replan`.
- New immutable plan version with parent linkage and trigger metadata: covered by Task 2 + Task 3 assertions.
- Keep API contract stable: covered by Task 3 tests and no route/payload changes.
- Execution-compatible response surface (`execution_plan_json` -> `EditPlan`): covered by Task 3 conversion path and Task 4 regressions.

## Placeholder Scan

- No `TODO`/`TBD`.
- All code-modifying steps include concrete code snippets.
- All validation steps include exact commands and expected outcomes.

## Type/Name Consistency

- Uses existing naming conventions: `current_plan_id`, `trigger_type`, `execution_plan_json`, `planner_trace_json`.
- New names are consistent across tasks: `GroundingFeedback`, `CandidateConfirmationFeedback`, `replan_after_grounding`, `run_grounding_replan`, `persist_grounding_replan`.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-09-model-driven-agent-plan-phase2-grounding-replan.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

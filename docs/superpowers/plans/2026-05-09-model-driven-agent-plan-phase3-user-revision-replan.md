# Model-Driven Agent Plan Phase 3 (User Revision Replan) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy post-plan message revision path with planner-driven `replan_after_user_revision`, so normal user edits create an observation, trigger LangGraph replanning, and persist a new immutable plan version.

**Architecture:** Keep the current `/api/agent/sessions/{id}/messages` contract stable, but stop treating post-plan user edits as in-place keyword patches or no-op plan clones. `AgentSessionService.add_user_message()` should continue to handle grounding-pre-confirmation messages as today; once a planner-backed plan exists, revisions flow through planner feedback models, LangGraph replanning, observation persistence, and `execution_plan_json` projection.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, LangGraph, LangChain runtime abstraction, unittest

---

## File Structure

### New files

- `tests/test_agent_planner_phase3.py`
  - Integration coverage for user revision observation -> replanning -> immutable vNext persistence.

### Modified files

- `backend/services/planner_models.py`
  - Add planner feedback contract for user revision input.
- `backend/services/planner_runtime_deterministic.py`
  - Implement deterministic `replan_after_user_revision(...)`.
- `backend/services/planner_runtime_openai.py`
  - Add `replan_after_user_revision(...)` method signature (stub in this phase).
- `backend/services/planner_graph.py`
  - Add user revision replanning state and `run_user_revision_replan(...)`.
- `backend/services/planner_orchestrator.py`
  - Add `persist_user_revision_replan(...)` that writes observation + plan vNext.
- `backend/services/agent_session_service.py`
  - Replace the legacy post-plan revision path in `add_user_message(...)`.
- `tests/test_planner_models.py`
  - Add feedback model coverage for revision payloads.
- `tests/test_planner_runtime.py`
  - Add deterministic runtime revision replanning coverage.
- `tests/test_planner_graph.py`
  - Add graph-level revision replanning test.
- `tests/test_agent_backend.py`
  - Update message-edit expectations from legacy clone behavior to planner-backed replan behavior.
- `tests/test_agent_persistence.py`
  - Assert observation linkage, version lineage, and `current_plan_id` updates for revision replans.
- `tests/test_agent_api_p0.py`
  - Keep API response contract stable while validating message-driven plan revision behavior.

## Scope Guardrails

- This phase only implements `replan_after_user_revision`; it does not introduce execution-feedback auto-replan.
- Empty-session + first-message grounding flow stays unchanged.
- Pre-confirmation grounding edits stay unchanged: they still refresh grounding summary/candidates instead of creating plans.
- Post-plan user revisions must create a new immutable planner plan version; no in-place mutation of prior plan rows.
- Keep `execution_plan_json` as the frontend/execution truth surface.
- Preserve support for scene-specific keyword syntax such as `场景1：城市 车流 黄昏`, but route it through planner revision feedback instead of direct `EditPlan` mutation.
- If runtime mode is `openai`, `replan_after_user_revision(...)` may remain `NotImplementedError` in this phase; deterministic mode remains the primary tested path.

### Task 1: Add revision feedback contract and deterministic runtime support

**Files:**
- Modify: `backend/services/planner_models.py`
- Modify: `backend/services/planner_runtime_deterministic.py`
- Modify: `backend/services/planner_runtime_openai.py`
- Test: `tests/test_planner_models.py`
- Test: `tests/test_planner_runtime.py`

- [ ] **Step 1: Write the failing planner model and runtime tests**

Add to `tests/test_planner_models.py`:

```python
    def test_user_revision_feedback_defaults(self):
        from backend.services.planner_models import UserRevisionFeedback

        feedback = UserRevisionFeedback(
            message="整体再商务一点，品牌感再强一点",
            sceneKeywordUpdates={1: ["城市", "车流", "黄昏"]},
        )

        self.assertEqual(feedback.message, "整体再商务一点，品牌感再强一点")
        self.assertEqual(feedback.sceneKeywordUpdates[1], ["城市", "车流", "黄昏"])
        self.assertEqual(feedback.revisionSource, "user_message")
```

Add to `tests/test_planner_runtime.py`:

```python
    def test_deterministic_runtime_replans_after_user_revision(self):
        from backend.services.planner_models import UserRevisionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        next_agent, next_execution, change_summary = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="整体再商务一点，目标受众改成销售团队，场景1：城市 车流 黄昏",
                sceneKeywordUpdates={1: ["城市", "车流", "黄昏"]},
            ),
        )

        self.assertIn("revision", change_summary)
        self.assertEqual(next_execution.style, "商务演示风格")
        self.assertEqual(next_execution.scenes[0].keywords, ["城市", "车流", "黄昏"])
        self.assertEqual(next_execution.scenes[0].searchQuery, "城市 车流 黄昏")
        self.assertEqual(next_agent.understanding.audience, "销售团队")
        self.assertGreaterEqual(len(next_agent.replanHistory), 1)
```

- [ ] **Step 2: Run the focused tests and verify they fail for the expected reason**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models tests.test_planner_runtime -v
```

Expected: FAIL because `UserRevisionFeedback` and `replan_after_user_revision(...)` do not exist yet.

- [ ] **Step 3: Add the planner feedback model**

Update `backend/services/planner_models.py`:

```python
class UserRevisionFeedback(BaseModel):
    message: str
    sceneKeywordUpdates: dict[int, list[str]] = Field(default_factory=dict)
    revisionSource: Literal["user_message", "api_message"] = "user_message"
```

Also export/import it alongside the existing grounding feedback models wherever planner runtime code needs it.

- [ ] **Step 4: Implement deterministic revision replanning**

Update `backend/services/planner_runtime_deterministic.py` with a new method:

```python
    def replan_after_user_revision(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        revision_feedback: UserRevisionFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        message = revision_feedback.message.strip()
        updated_style = current_execution.style
        if "商务" in message:
            updated_style = "商务演示风格"
        elif "品牌感" in message:
            updated_style = "品牌展示风格"

        updated_audience = current_agent.understanding.audience
        if "销售团队" in message:
            updated_audience = "销售团队"

        updated_execution_scenes = []
        for scene in current_execution.scenes:
            override_keywords = revision_feedback.sceneKeywordUpdates.get(scene.id)
            if override_keywords:
                updated_execution_scenes.append(
                    scene.model_copy(
                        update={
                            "keywords": override_keywords,
                            "searchQuery": " ".join(override_keywords),
                        }
                    )
                )
            else:
                updated_execution_scenes.append(scene.model_copy(deep=True))

        next_execution = current_execution.model_copy(
            update={
                "style": updated_style,
                "scenes": updated_execution_scenes,
            }
        )
        next_agent = current_agent.model_copy(
            update={
                "summary": f"{current_agent.summary}；已根据最新 revision 调整",
                "understanding": current_agent.understanding.model_copy(
                    update={"audience": updated_audience}
                ),
                "replanHistory": [
                    *current_agent.replanHistory,
                    {
                        "triggerType": "user_revision",
                        "summary": "基于最新用户 revision 完成重规划",
                        "message": message,
                    },
                ],
            }
        )
        return next_agent, next_execution, "revision 驱动的计划重规划已完成"
```

Keep the implementation conservative:

- Only adjust fields the deterministic runtime can infer reliably now.
- Preserve all existing scene ids and durations.
- Reuse scene keyword overrides when they are explicitly provided.
- Do not mutate `current_agent` / `current_execution` in place.

- [ ] **Step 5: Add the OpenAI runtime method stub for contract parity**

Update `backend/services/planner_runtime_openai.py`:

```python
    def replan_after_user_revision(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        revision_feedback: UserRevisionFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        raise NotImplementedError(
            "OpenAI user revision replanning runtime is enabled in later tasks of the rollout"
        )
```

- [ ] **Step 6: Run the focused tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models tests.test_planner_runtime -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/services/planner_models.py backend/services/planner_runtime_deterministic.py backend/services/planner_runtime_openai.py tests/test_planner_models.py tests/test_planner_runtime.py
git commit -m "feat: add user revision planner feedback"
```

### Task 2: Add LangGraph revision replan path and orchestrator persistence

**Files:**
- Modify: `backend/services/planner_graph.py`
- Modify: `backend/services/planner_orchestrator.py`
- Test: `tests/test_planner_graph.py`
- Create: `tests/test_agent_planner_phase3.py`

- [ ] **Step 1: Write the failing graph and integration tests**

Add to `tests/test_planner_graph.py`:

```python
    def test_run_user_revision_replan_returns_replanning_complete_state(self):
        from backend.services.planner_graph import run_user_revision_replan
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief("做一个产品视频")

        state = run_user_revision_replan(
            session_id="session-1",
            current_agent_plan=current_agent.model_dump(mode="json"),
            current_execution_plan=current_execution.model_dump(mode="json"),
            revision_feedback={
                "message": "更商务一点，目标受众改成销售团队",
                "sceneKeywordUpdates": {1: ["城市", "车流", "黄昏"]},
                "revisionSource": "user_message",
            },
        )

        self.assertEqual(state["status"], "replanning_complete")
        self.assertEqual(state["triggerType"], "user_revision")
        self.assertIn("changeSummary", state)
```

Create `tests/test_agent_planner_phase3.py`:

```python
import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.base import Base
from backend.db.repositories import (
    AgentObservationRepository,
    AgentPlanRepository,
    AgentSessionRepository,
)
from backend.services.agent_session_service import AgentSessionService


class AgentPlannerPhase3Tests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def test_post_plan_user_revision_persists_observation_and_plan_vnext(self):
        service = AgentSessionService(session_factory=self.session_factory)

        session = service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
        updated = service.add_user_message(
            session.id,
            "整体再商务一点，目标受众改成销售团队，场景1：城市 车流 黄昏",
        )

        self.assertEqual(updated.status.value, "plan_ready")
        self.assertIsNotNone(updated.plan)

        with self.session_factory() as db:
            plan_repo = AgentPlanRepository(db)
            observation_repo = AgentObservationRepository(db)
            session_repo = AgentSessionRepository(db)

            plans = plan_repo.list_for_session(session.id)
            latest = plans[-1]
            previous = plans[-2]
            observations = observation_repo.list_for_session(session.id)
            session_record = session_repo.get(session.id)

            self.assertEqual(len(plans), 2)
            self.assertEqual(previous.version, 1)
            self.assertEqual(latest.version, 2)
            self.assertEqual(latest.parent_plan_id, previous.id)
            self.assertEqual(latest.trigger_type, "user_revision")
            self.assertEqual(observations[-1].observation_type, "user_revision")
            self.assertEqual(session_record.current_plan_id, latest.id)
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_graph tests.test_agent_planner_phase3 -v
```

Expected: FAIL because revision replanning graph/orchestrator path does not exist yet.

- [ ] **Step 3: Add the revision replanning LangGraph path**

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
    revisionFeedback: dict
    changeSummary: str


def _replan_after_user_revision_node(state: PlanningState) -> PlanningState:
    runtime = get_planner_runtime()
    current_agent = AgentPlan.model_validate(state["agentPlan"])
    current_execution = ExecutionPlan.model_validate(state["executionPlan"])
    next_agent, next_execution, change_summary = runtime.replan_after_user_revision(
        current_agent=current_agent,
        current_execution=current_execution,
        revision_feedback=UserRevisionFeedback.model_validate(state["revisionFeedback"]),
    )
    return {
        **state,
        "status": "replanning_complete",
        "triggerType": "user_revision",
        "agentPlan": next_agent.model_dump(mode="json"),
        "executionPlan": next_execution.model_dump(mode="json"),
        "changeSummary": change_summary,
    }


def build_user_revision_replan_graph():
    graph = StateGraph(PlanningState)
    graph.add_node("replan_after_user_revision", _replan_after_user_revision_node)
    graph.add_edge(START, "replan_after_user_revision")
    graph.add_edge("replan_after_user_revision", END)
    return graph.compile()


def run_user_revision_replan(
    session_id: str,
    current_agent_plan: dict,
    current_execution_plan: dict,
    revision_feedback: dict,
) -> PlanningState:
    graph = build_user_revision_replan_graph()
    return graph.invoke(
        {
            "sessionId": session_id,
            "status": "replanning",
            "triggerType": "user_revision",
            "agentPlan": current_agent_plan,
            "executionPlan": current_execution_plan,
            "revisionFeedback": revision_feedback,
        }
    )
```

- [ ] **Step 4: Add orchestrator persistence for user revision**

Update `backend/services/planner_orchestrator.py`:

```python
    def persist_user_revision_replan(self, db, session_record, message_record, scene_keyword_updates: dict[int, list[str]]):
        plan_repo = AgentPlanRepository(db)
        observation_repo = AgentObservationRepository(db)
        settings = get_settings()

        latest_plan = plan_repo.get_latest_for_session(session_record.id)
        if latest_plan is None:
            raise RuntimeError("User revision replan requires an existing plan version")

        state = run_user_revision_replan(
            session_id=session_record.id,
            current_agent_plan=latest_plan.plan_json,
            current_execution_plan=latest_plan.execution_plan_json,
            revision_feedback={
                "message": message_record.content,
                "sceneKeywordUpdates": scene_keyword_updates,
                "revisionSource": "user_message",
            },
        )

        observation_repo.create(
            session_id=session_record.id,
            plan_id=latest_plan.id,
            observation_type="user_revision",
            summary="用户提交 plan revision 并触发重规划",
            payload_json={
                "message": message_record.content,
                "sceneKeywordUpdates": scene_keyword_updates,
            },
            source_message_id=message_record.id,
        )

        next_plan = plan_repo.create(
            session_id=session_record.id,
            version=latest_plan.version + 1,
            parent_plan_id=latest_plan.id,
            trigger_type="user_revision",
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

- [ ] **Step 5: Run the focused tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_graph tests.test_agent_planner_phase3 -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/planner_graph.py backend/services/planner_orchestrator.py tests/test_planner_graph.py tests/test_agent_planner_phase3.py
git commit -m "feat: add planner-backed user revision replan"
```

### Task 3: Rewire `add_user_message()` off the legacy revision path

**Files:**
- Modify: `backend/services/agent_session_service.py`
- Test: `tests/test_agent_backend.py`
- Test: `tests/test_agent_persistence.py`
- Test: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Write the failing service/API regression tests**

Update `tests/test_agent_backend.py` so post-plan free-text edits no longer expect a no-op clone:

```python
    def test_add_message_after_grounding_confirmation_triggers_revision_replan(self):
        from backend.db.repositories import AgentPlanRepository

        created = self.session_service.create_session()
        awaiting = self.session_service.add_user_message(created.id, "给 Notion AI 做一个 30 秒产品亮点视频")
        grounded = self.session_service.confirm_grounding_candidates(
            created.id,
            [candidate.id for candidate in awaiting.grounding.candidates[:2]],
        )

        updated = self.session_service.add_user_message(
            created.id,
            "更商务一点，品牌感再强一点",
        )

        self.assertIsNotNone(updated.plan)
        self.assertEqual(updated.grounding.status, "confirmed")
        self.assertEqual(updated.plan.style, "商务演示风格")

        with self.session_factory() as db:
            latest_plan = AgentPlanRepository(db).get_latest_for_session(created.id)

        self.assertEqual(latest_plan.version, 3)
        self.assertEqual(latest_plan.trigger_type, "user_revision")
        self.assertEqual(latest_plan.execution_plan_json["style"], "商务演示风格")
```

Update `tests/test_agent_persistence.py` to assert version lineage and observation linkage after post-plan revision:

```python
    def test_add_user_message_after_plan_persists_revision_observation_and_updates_current_plan(self):
        from backend.db.repositories import AgentObservationRepository, AgentPlanRepository, AgentSessionRepository
        from backend.services.agent_session_service import AgentSessionService

        service = AgentSessionService(session_factory=self.SessionLocal)
        session = service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
        updated = service.add_user_message(session.id, "整体再商务一点，目标受众改成销售团队")

        self.assertEqual(updated.plan.style, "商务演示风格")

        db = self.SessionLocal()
        try:
            plan_repo = AgentPlanRepository(db)
            observation_repo = AgentObservationRepository(db)
            session_repo = AgentSessionRepository(db)

            plans = plan_repo.list_for_session(session.id)
            self.assertEqual(plans[-1].trigger_type, "user_revision")
            self.assertEqual(plans[-1].parent_plan_id, plans[-2].id)
            self.assertEqual(observation_repo.list_for_session(session.id)[-1].observation_type, "user_revision")
            self.assertEqual(session_repo.get(session.id).current_plan_id, plans[-1].id)
        finally:
            db.close()
```

Update `tests/test_agent_api_p0.py` so the `/messages` round trip asserts that a post-plan message updates the latest plan instead of only appending chat:

```python
                message_response = await client.post(
                    f"/api/agent/sessions/{session_id}/messages",
                    json={"message": "再加一点品牌感，更商务一点"},
                )
                self.assertEqual(message_response.status_code, 200)
                updated_session = message_response.json()
                self.assertEqual(updated_session["status"], "plan_ready")
                self.assertEqual(updated_session["plan"]["style"], "商务演示风格")
                self.assertEqual(updated_session["messages"][-1]["role"], "assistant")
```

- [ ] **Step 2: Run the focused regression tests and verify failure**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend tests.test_agent_persistence tests.test_agent_api_p0 -v
```

Expected: FAIL because `add_user_message()` still uses `_build_next_plan(...)` and does not write revision observations.

- [ ] **Step 3: Replace the legacy path inside `AgentSessionService.add_user_message()`**

Update `backend/services/agent_session_service.py` with three focused changes:

1. Capture the created message row so the orchestrator can store `source_message_id`.
2. Leave `_should_start_grounding(...)` branch untouched.
3. For sessions that already have `latest_plan`, call planner-backed revision replan instead of `_build_next_plan(...)`.

Target structure:

```python
                message_record = message_repo.create(session_id=session_id, role="user", content=content)
                latest_plan = plan_repo.get_latest_for_session(session_id)
                if self._should_start_grounding(session_record, latest_plan):
                    ...

                if latest_plan is not None:
                    planner_orchestrator = PlannerOrchestrator()
                    next_plan = planner_orchestrator.persist_user_revision_replan(
                        db=db,
                        session_record=session_record,
                        message_record=message_record,
                        scene_keyword_updates=self._extract_scene_keyword_updates(content),
                    )
                    plan = execution_plan_to_edit_plan(next_plan.execution_plan_json)
                    self._apply_plan_to_session(session_record, plan)
                    session_repo.set_current_plan(session_id, next_plan.id)
                    self._append_plan_ready_message(message_repo, session_id)
                    db.commit()
                    return self.read_service.read_session(session_id)

                plan = self._build_next_plan(None, content)
```

Then simplify the legacy helpers:

- Keep `_fallback_plan(...)` for the no-plan compatibility path only.
- Keep `_extract_scene_keyword_updates(...)` and `_split_keywords(...)` because the deterministic planner runtime still consumes that structured hint.
- Remove `_apply_scene_keyword_updates(...)`.
- Make `_build_next_plan(...)` only handle the no-existing-plan fallback path or delete it entirely if unused after refactor.

- [ ] **Step 4: Run the focused regression tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend tests.test_agent_persistence tests.test_agent_api_p0 -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/agent_session_service.py tests/test_agent_backend.py tests/test_agent_persistence.py tests/test_agent_api_p0.py
git commit -m "feat: route post-plan edits through planner replan"
```

### Task 4: Full regression pass and cleanup

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-model-driven-agent-plan-phase3-user-revision-replan.md`
  - Check off completed steps during execution if the worker updates plan status inline.
- Verify: full targeted backend planner suite

- [ ] **Step 1: Run the planner/backend regression suite**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models tests.test_planner_runtime tests.test_planner_graph tests.test_agent_planner_phase1 tests.test_agent_planner_phase2 tests.test_agent_planner_phase3 tests.test_agent_backend tests.test_agent_persistence tests.test_agent_api_p0 tests.test_agent_jobs -v
```

Expected: PASS, with only pre-existing warnings such as SQLAlchemy `datetime.utcnow()` deprecation or LangGraph pending deprecation warnings.

- [ ] **Step 2: Sanity-check changed behavior against spec**

Verify manually from test expectations and code review:

- post-plan free-text revision creates a new plan version
- prior plan rows remain immutable
- a `user_revision` observation is written and linked to the previous plan
- `current_plan_id` advances to the latest revision plan
- API response shape remains unchanged
- grounding-pre-confirmation flow still returns candidates instead of plans

- [ ] **Step 3: Commit plan doc status updates if maintained inline**

```bash
git add docs/superpowers/plans/2026-05-09-model-driven-agent-plan-phase3-user-revision-replan.md
git commit -m "docs: track phase3 user revision replan rollout"
```

Only make this commit if the execution workflow updates the checklist in the plan file.

## Self-Review

- Spec coverage:
  - `replan_after_user_revision`: covered by Tasks 1-2
  - observation persistence + new immutable plan version: covered by Tasks 2-3
  - `/messages` contract stability: covered by Task 3
  - planner/backend regression coverage: covered by Task 4
- Placeholder scan:
  - No `TODO`/`TBD` placeholders remain.
  - Each task includes concrete tests, commands, and target edits.
- Type consistency:
  - `UserRevisionFeedback`, `revisionFeedback`, `trigger_type="user_revision"`, and `observation_type="user_revision"` are used consistently throughout the plan.

## Recommended Execution Path

This phase is a good fit for **Subagent-Driven** execution because the tasks have clear ownership boundaries:

- Task 1: planner models/runtime
- Task 2: planner graph/orchestrator
- Task 3: session service + API/service regressions
- Task 4: verification and integration

If executed inline instead, keep the order exactly as written so TDD remains intact and the runtime/orchestrator contracts land before `AgentSessionService` is rewired.

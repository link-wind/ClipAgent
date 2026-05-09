# Model-Driven Agent Plan Phase 4 (Execution Feedback Replan) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first execution-feedback-driven planner loop so search/download failures can create an execution observation, trigger limited automatic replanning, and enqueue one replacement job against a new immutable plan version.

**Architecture:** Keep the existing Celery job execution and session/task API contracts stable, but intercept retryable execution failures inside the worker path before they become terminal. Phase 4 is intentionally scoped to search/download-side failures only: the worker should persist an execution feedback observation, invoke planner-backed `replan_after_execution_feedback`, create a successor `agent_plans` version, create a new queued job bound to that plan, and only fall back to the current failed-session behavior when automatic replanning is not allowed.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, LangGraph, LangChain runtime abstraction, Celery task worker, unittest

---

## File Structure

### New files

- `tests/test_agent_planner_phase4.py`
  - Integration coverage for execution feedback observation -> replan -> replacement job persistence.

### Modified files

- `backend/services/planner_models.py`
  - Add execution feedback contracts for planner runtime input.
- `backend/services/planner_runtime_deterministic.py`
  - Implement deterministic `replan_after_execution_feedback(...)`.
- `backend/services/planner_runtime_openai.py`
  - Add `replan_after_execution_feedback(...)` method signature (stub in this phase).
- `backend/services/planner_graph.py`
  - Add execution feedback replanning state and `run_execution_feedback_replan(...)`.
- `backend/services/planner_orchestrator.py`
  - Add `persist_execution_feedback_replan(...)` plus auto-replan policy bookkeeping.
- `backend/services/agent_progress_service.py`
  - Add a session/job transition for “replacement job queued after replanning”.
- `backend/tasks/agent_tasks.py`
  - Route eligible search/download failures through the planner replan path before marking terminal failure.
- `tests/test_planner_models.py`
  - Add model coverage for execution feedback payloads.
- `tests/test_planner_runtime.py`
  - Add deterministic runtime execution-feedback replanning coverage.
- `tests/test_planner_graph.py`
  - Add graph-level execution-feedback replanning test.
- `tests/test_agent_jobs.py`
  - Add worker-level replan-and-requeue coverage and preserve existing failure behavior for out-of-scope cases.
- `tests/test_agent_backend.py`
  - Add service/API-facing assertions for replacement-job behavior where useful.
- `tests/test_agent_persistence.py`
  - Assert observation linkage, plan lineage, and replacement job persistence after auto-replan.
- `tests/test_agent_api_p0.py`
  - Keep failed/running task response contracts stable while exposing requeued jobs on the same session/task surfaces.

## Scope Guardrails

- This phase only covers retryable search/download-side failures, represented as execution feedback from the worker before any clips are ready.
- Render failures remain on the existing failed-session path in this phase.
- Automatic replanning is capped at one replacement job for the same session in this implementation slice, even though the long-term design allows up to two auto-replans.
- No new database columns in this phase; use existing `planner_trace_json`, `current_plan_id`, `agent_observations`, `agent_plans`, `agent_jobs`, and `agent_events`.
- `execution_plan_json` remains the execution/frontend truth surface.
- The existing `/api/agent/sessions/{id}` and task detail APIs must stay shape-compatible.
- If the worker cannot safely auto-replan, it must preserve the current terminal-failure behavior rather than half-transitioning the session.

### Task 1: Add execution feedback contracts and deterministic runtime support

**Files:**
- Modify: `backend/services/planner_models.py`
- Modify: `backend/services/planner_runtime_deterministic.py`
- Modify: `backend/services/planner_runtime_openai.py`
- Test: `tests/test_planner_models.py`
- Test: `tests/test_planner_runtime.py`

- [ ] **Step 1: Write the failing planner model and runtime tests**

Add to `tests/test_planner_models.py`:

```python
    def test_search_execution_feedback_defaults(self):
        from backend.services.planner_models import SearchExecutionFeedback

        feedback = SearchExecutionFeedback(
            failedSceneIds=[1, 2],
            failureReason="素材检索失败",
            retryable=True,
        )

        self.assertEqual(feedback.failedSceneIds, [1, 2])
        self.assertEqual(feedback.failureReason, "素材检索失败")
        self.assertEqual(feedback.feedbackSource, "worker_failure")
```

Add to `tests/test_planner_runtime.py`:

```python
    def test_deterministic_runtime_replans_after_execution_feedback(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        next_agent, next_execution, change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[1],
                failureReason="素材检索失败",
                retryable=True,
            ),
        )

        self.assertIn("execution", change_summary)
        self.assertEqual(next_execution.scenes[0].searchQuery, "product interface alternative")
        self.assertEqual(next_execution.scenes[0].keywords, ["product", "interface", "alternative"])
        self.assertGreaterEqual(len(next_agent.replanHistory), 1)
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models tests.test_planner_runtime -v
```

Expected: FAIL because `SearchExecutionFeedback` and `replan_after_execution_feedback(...)` do not exist yet.

- [ ] **Step 3: Add the execution feedback models**

Update `backend/services/planner_models.py`:

```python
class SearchExecutionFeedback(BaseModel):
    failedSceneIds: list[int] = Field(default_factory=list)
    failureReason: str = ""
    retryable: bool = True
    feedbackSource: Literal["worker_failure", "api_retry"] = "worker_failure"


class RenderReadinessFeedback(BaseModel):
    missingSceneIds: list[int] = Field(default_factory=list)
    summary: str = ""
    retryable: bool = True
```

- [ ] **Step 4: Implement deterministic execution-feedback replanning**

Update `backend/services/planner_runtime_deterministic.py`:

```python
    def replan_after_execution_feedback(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        execution_feedback: SearchExecutionFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        failed_scene_ids = set(execution_feedback.failedSceneIds)

        updated_execution_scenes = []
        for scene in current_execution.scenes:
            if scene.id in failed_scene_ids:
                next_keywords = [*scene.keywords[:2], "alternative"]
                updated_execution_scenes.append(
                    scene.model_copy(
                        update={
                            "keywords": next_keywords,
                            "searchQuery": " ".join(next_keywords),
                        }
                    )
                )
            else:
                updated_execution_scenes.append(scene.model_copy(deep=True))

        updated_agent_scenes = []
        for scene in current_agent.scenes:
            if scene.id in failed_scene_ids:
                updated_agent_scenes.append(
                    scene.model_copy(
                        update={
                            "status": "draft",
                            "keywords": [*scene.keywords[:2], "alternative"],
                        }
                    )
                )
            else:
                updated_agent_scenes.append(scene.model_copy(deep=True))

        next_execution = current_execution.model_copy(update={"scenes": updated_execution_scenes})
        next_agent = current_agent.model_copy(
            update={
                "scenes": updated_agent_scenes,
                "replanHistory": [
                    *current_agent.replanHistory,
                    {
                        "triggerType": "execution_feedback",
                        "summary": "基于执行失败反馈重写检索查询",
                        "failedSceneIds": sorted(failed_scene_ids),
                        "failureReason": execution_feedback.failureReason,
                    },
                ],
            }
        )
        return next_agent, next_execution, "execution feedback 驱动的重规划已完成"
```

- [ ] **Step 5: Add the OpenAI runtime method stub**

Update `backend/services/planner_runtime_openai.py`:

```python
    def replan_after_execution_feedback(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        execution_feedback: SearchExecutionFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        raise NotImplementedError(
            "OpenAI execution feedback replanning runtime is enabled in later tasks of the rollout"
        )
```

- [ ] **Step 6: Run the focused tests and verify pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models tests.test_planner_runtime -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/services/planner_models.py backend/services/planner_runtime_deterministic.py backend/services/planner_runtime_openai.py tests/test_planner_models.py tests/test_planner_runtime.py
git commit -m "feat: add execution feedback planner contracts"
```

### Task 2: Add LangGraph execution-feedback replan path and planner persistence

**Files:**
- Modify: `backend/services/planner_graph.py`
- Modify: `backend/services/planner_orchestrator.py`
- Create: `tests/test_agent_planner_phase4.py`
- Test: `tests/test_planner_graph.py`

- [ ] **Step 1: Write the failing graph and planner integration tests**

Add to `tests/test_planner_graph.py`:

```python
    def test_run_execution_feedback_replan_returns_replanning_complete_state(self):
        from backend.services.planner_graph import run_execution_feedback_replan
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief("做一个产品视频")

        state = run_execution_feedback_replan(
            session_id="session-1",
            current_agent_plan=current_agent.model_dump(mode="json"),
            current_execution_plan=current_execution.model_dump(mode="json"),
            execution_feedback={
                "failedSceneIds": [1],
                "failureReason": "素材检索失败",
                "retryable": True,
                "feedbackSource": "worker_failure",
            },
        )

        self.assertEqual(state["status"], "replanning_complete")
        self.assertEqual(state["triggerType"], "execution_feedback")
        self.assertIn("changeSummary", state)
```

Create `tests/test_agent_planner_phase4.py`:

```python
import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.base import Base
from backend.db.repositories import (
    AgentJobRepository,
    AgentObservationRepository,
    AgentPlanRepository,
    AgentSessionRepository,
)
from backend.services.agent_execution_service import AgentExecutionService
from backend.services.agent_session_service import AgentSessionService
from backend.tasks.agent_tasks import run_agent_job


class AgentPlannerPhase4Tests(unittest.TestCase):
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

    def test_execution_feedback_replan_creates_plan_vnext_and_replacement_job(self):
        from unittest.mock import patch

        session_service = AgentSessionService(session_factory=self.session_factory)
        execution_service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=lambda _job_id: None,
        )

        session = session_service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
        confirmed = execution_service.confirm_session(session.id)
        job_id = confirmed.activeJobId

        async def failing_search_runner(_session_id, _scenes):
            raise RuntimeError("素材检索失败")

        with patch("backend.tasks.agent_tasks.SessionLocal", self.session_factory), patch(
            "backend.tasks.agent_tasks.search_and_download_agent_clips",
            failing_search_runner,
        ):
            run_agent_job(job_id)

        with self.session_factory() as db:
            job_repo = AgentJobRepository(db)
            plan_repo = AgentPlanRepository(db)
            observation_repo = AgentObservationRepository(db)
            session_repo = AgentSessionRepository(db)

            jobs = job_repo.list_recent(limit=10)
            plans = plan_repo.list_for_session(session.id)
            observations = observation_repo.list_for_session(session.id)
            session_record = session_repo.get(session.id)

            self.assertEqual(plans[-1].trigger_type, "execution_feedback")
            self.assertEqual(plans[-1].parent_plan_id, plans[-2].id)
            self.assertEqual(observations[-1].observation_type, "execution_feedback")
            self.assertEqual(jobs[0].status, "queued")
            self.assertEqual(jobs[0].plan_id, plans[-1].id)
            self.assertEqual(session_record.current_plan_id, plans[-1].id)
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_graph tests.test_agent_planner_phase4 -v
```

Expected: FAIL because execution-feedback graph/orchestrator path does not exist yet.

- [ ] **Step 3: Add the execution-feedback LangGraph path**

Update `backend/services/planner_graph.py`:

```python
class PlanningState(TypedDict, total=False):
    ...
    executionFeedback: dict


def _replan_after_execution_feedback_node(state: PlanningState) -> PlanningState:
    runtime = get_planner_runtime()
    current_agent = AgentPlan.model_validate(state["agentPlan"])
    current_execution = ExecutionPlan.model_validate(state["executionPlan"])
    next_agent, next_execution, change_summary = runtime.replan_after_execution_feedback(
        current_agent=current_agent,
        current_execution=current_execution,
        execution_feedback=SearchExecutionFeedback.model_validate(state["executionFeedback"]),
    )
    return {
        **state,
        "status": "replanning_complete",
        "triggerType": "execution_feedback",
        "agentPlan": next_agent.model_dump(mode="json"),
        "executionPlan": next_execution.model_dump(mode="json"),
        "changeSummary": change_summary,
    }


def build_execution_feedback_replan_graph():
    graph = StateGraph(PlanningState)
    graph.add_node("replan_after_execution_feedback", _replan_after_execution_feedback_node)
    graph.add_edge(START, "replan_after_execution_feedback")
    graph.add_edge("replan_after_execution_feedback", END)
    return graph.compile()


def run_execution_feedback_replan(
    session_id: str,
    current_agent_plan: dict,
    current_execution_plan: dict,
    execution_feedback: dict,
) -> PlanningState:
    graph = build_execution_feedback_replan_graph()
    return graph.invoke(
        {
            "sessionId": session_id,
            "status": "replanning",
            "triggerType": "execution_feedback",
            "agentPlan": current_agent_plan,
            "executionPlan": current_execution_plan,
            "executionFeedback": execution_feedback,
        }
    )
```

- [ ] **Step 4: Add orchestrator persistence and auto-replan policy bookkeeping**

Update `backend/services/planner_orchestrator.py`:

```python
    def persist_execution_feedback_replan(self, db, session_record, failed_job_record, execution_feedback: dict):
        plan_repo = AgentPlanRepository(db)
        observation_repo = AgentObservationRepository(db)
        settings = get_settings()

        latest_plan = plan_repo.get_latest_for_session(session_record.id)
        if latest_plan is None:
            raise RuntimeError("Execution feedback replan requires an existing plan version")

        planner_trace = session_record.planner_trace_json or {}
        auto_replan_count = int(planner_trace.get("autoExecutionReplanCount", 0) or 0)
        if auto_replan_count >= 1:
            raise RuntimeError("Execution feedback replan limit reached")

        state = run_execution_feedback_replan(
            session_id=session_record.id,
            current_agent_plan=latest_plan.plan_json,
            current_execution_plan=latest_plan.execution_plan_json,
            execution_feedback=execution_feedback,
        )

        observation_repo.create(
            session_id=session_record.id,
            plan_id=latest_plan.id,
            observation_type="execution_feedback",
            summary="执行失败反馈触发自动重规划",
            payload_json=execution_feedback,
            source_job_id=failed_job_record.id,
        )

        next_plan = plan_repo.create(
            session_id=session_record.id,
            version=latest_plan.version + 1,
            parent_plan_id=latest_plan.id,
            trigger_type="execution_feedback",
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
            **planner_trace,
            "lastPlanningState": state["status"],
            "triggerType": state["triggerType"],
            "autoExecutionReplanCount": auto_replan_count + 1,
        }
        return next_plan
```

- [ ] **Step 5: Run the focused tests and verify pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_graph tests.test_agent_planner_phase4 -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/planner_graph.py backend/services/planner_orchestrator.py tests/test_planner_graph.py tests/test_agent_planner_phase4.py
git commit -m "feat: add execution feedback planner replan path"
```

### Task 3: Requeue a replacement job from worker failure

**Files:**
- Modify: `backend/tasks/agent_tasks.py`
- Modify: `backend/services/agent_progress_service.py`
- Test: `tests/test_agent_jobs.py`
- Test: `tests/test_agent_backend.py`
- Test: `tests/test_agent_persistence.py`
- Test: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Write the failing worker and persistence regression tests**

Add to `tests/test_agent_jobs.py`:

```python
    def test_run_agent_job_requeues_replanned_job_after_retryable_search_failure(self):
        from backend.db.repositories import AgentEventRepository, AgentJobRepository, AgentPlanRepository
        from backend.tasks.agent_tasks import run_agent_job

        session_id, job_id = self._create_queued_job()

        async def failing_search_runner(_session_id, _scenes):
            raise RuntimeError("素材检索失败")

        with patch("backend.tasks.agent_tasks.SessionLocal", self.session_factory), patch(
            "backend.tasks.agent_tasks.search_and_download_agent_clips",
            failing_search_runner,
        ):
            run_agent_job(job_id)

        with self.session_factory() as db:
            job_repo = AgentJobRepository(db)
            plan_repo = AgentPlanRepository(db)
            event_repo = AgentEventRepository(db)

            jobs = job_repo.list_recent(limit=10)
            latest_plan = plan_repo.list_for_session(session_id)[-1]
            event_types = [row.event_type for row in event_repo.list_for_session(session_id)]

            self.assertEqual(jobs[0].status, "queued")
            self.assertEqual(jobs[0].plan_id, latest_plan.id)
            self.assertEqual(latest_plan.trigger_type, "execution_feedback")
            self.assertIn("job_requeued_after_replan", event_types)
```

Add to `tests/test_agent_persistence.py`:

```python
    def test_execution_feedback_replan_persists_replacement_job_linked_to_new_plan(self):
        ...
        self.assertEqual(replacement_job.plan_id, plans[-1].id)
        self.assertEqual(session_repo.get(session.id).active_job_id, replacement_job.id)
```

Add to `tests/test_agent_api_p0.py`:

```python
    def test_failed_search_replan_keeps_session_in_queued_state_with_new_active_job(self):
        ...
        self.assertEqual(reloaded["status"], "queued")
        self.assertIsNotNone(reloaded["activeJobId"])
```

- [ ] **Step 2: Run the focused regression tests and verify failure**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_jobs tests.test_agent_persistence tests.test_agent_api_p0 -v
```

Expected: FAIL because the worker still marks search failures terminally.

- [ ] **Step 3: Add a progress/session transition for replacement-job queueing**

Update `backend/services/agent_progress_service.py`:

```python
    def mark_job_requeued_after_replan(self, session_id: str, failed_job_id: str, replacement_job_id: str):
        session_record = self.session_repo.get(session_id)
        session_record.status = "queued"
        session_record.progress = 25
        session_record.current_step = "任务已重新规划并重新入队"
        session_record.active_job_id = replacement_job_id
        session_record.error_message = None
        session_record.error_retryable_step = None
        self.record_event(
            session_id=session_id,
            job_id=replacement_job_id,
            event_type="job_requeued_after_replan",
            step="queued",
            message="执行失败后已自动重规划并重新入队",
            progress=25,
            payload={
                "failedJobId": failed_job_id,
                "replacementJobId": replacement_job_id,
            },
        )
```

- [ ] **Step 4: Intercept retryable search failures in `run_agent_job()`**

Update `backend/tasks/agent_tasks.py` with a narrow helper path:

```python
def _should_attempt_execution_replan(job_record, retryable_step: str) -> bool:
    return retryable_step == "searching"
```

In the `except` block:

```python
            if job_record is not None and job_record.session_id:
                progress_service = AgentProgressService(db)
                retryable_step = "rendering" if job_record.progress >= 80 else "searching"
                if _should_attempt_execution_replan(job_record, retryable_step):
                    from backend.db.repositories import AgentSessionRepository
                    from backend.services.planner_orchestrator import PlannerOrchestrator

                    session_record = AgentSessionRepository(db).get(job_record.session_id)
                    planner_orchestrator = PlannerOrchestrator()
                    next_plan = planner_orchestrator.persist_execution_feedback_replan(
                        db=db,
                        session_record=session_record,
                        failed_job_record=job_record,
                        execution_feedback={
                            "failedSceneIds": [],
                            "failureReason": str(exc),
                            "retryable": True,
                            "feedbackSource": "worker_failure",
                        },
                    )
                    replacement_job = job_repo.create(
                        session_id=job_record.session_id,
                        plan_id=next_plan.id,
                        job_type=job_record.job_type,
                        status="queued",
                        progress=0,
                        current_step="任务已重新入队",
                        max_attempts=job_record.max_attempts,
                    )
                    progress_service.mark_job_failed(
                        session_id=job_record.session_id,
                        job_id=job_id,
                        message=str(exc),
                        retryable_step=retryable_step,
                    )
                    progress_service.mark_job_requeued_after_replan(
                        session_id=job_record.session_id,
                        failed_job_id=job_id,
                        replacement_job_id=replacement_job.id,
                    )
                    db.commit()
                    return

                progress_service.mark_job_failed(...)
```

Keep the first slice conservative:

- original failed job remains `failed`
- replacement job is a fresh `queued` record bound to the new plan
- session pivots back to `queued` with the replacement job as `active_job_id`
- render failures still use the old terminal path

- [ ] **Step 5: Run the focused regression tests and verify pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_jobs tests.test_agent_persistence tests.test_agent_api_p0 -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/tasks/agent_tasks.py backend/services/agent_progress_service.py tests/test_agent_jobs.py tests/test_agent_persistence.py tests/test_agent_api_p0.py tests/test_agent_backend.py
git commit -m "feat: auto requeue jobs after execution feedback replan"
```

### Task 4: Full regression pass and plan sanity check

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-model-driven-agent-plan-phase4-execution-feedback-replan.md`
  - Check off completed steps during rollout execution if you are tracking status inline.
- Verify: planner/backend regression suite

- [ ] **Step 1: Run the full target suite**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models tests.test_planner_runtime tests.test_planner_graph tests.test_agent_planner_phase1 tests.test_agent_planner_phase2 tests.test_agent_planner_phase3 tests.test_agent_planner_phase4 tests.test_agent_backend tests.test_agent_persistence tests.test_agent_api_p0 tests.test_agent_jobs -v
```

Expected: PASS, with only pre-existing warnings such as LangGraph pending deprecation and SQLAlchemy `datetime.utcnow()` deprecation.

- [ ] **Step 2: Sanity-check behavior against scope guardrails**

Verify from tests and code review:

- retryable search/download failures create `execution_feedback` observations
- automatic replanning creates a new immutable plan version
- replacement jobs bind to the new plan id and become the session’s `active_job_id`
- the original failed job remains visible in task history
- render failures still follow the existing terminal-failure path
- no API response shape changes are required on `/api/agent/sessions`, `/api/agent/tasks`, or `/api/agent/tasks/{id}`

- [ ] **Step 3: Commit plan doc status updates if maintained inline**

```bash
git add docs/superpowers/plans/2026-05-09-model-driven-agent-plan-phase4-execution-feedback-replan.md
git commit -m "docs: track phase4 execution feedback replan rollout"
```

Only make this commit if the rollout process updates the checklist inside the plan file.

## Self-Review

- Spec coverage:
  - `replan_after_execution_feedback`: covered by Tasks 1-2
  - execution feedback observation + immutable plan version: covered by Task 2
  - limited automatic requeue flow: covered by Task 3
  - regression coverage and guardrail verification: covered by Task 4
- Placeholder scan:
  - No `TODO`/`TBD` placeholders remain.
  - Each task includes concrete tests, commands, and target edits.
- Type consistency:
  - `SearchExecutionFeedback`, `executionFeedback`, `trigger_type="execution_feedback"`, and `observation_type="execution_feedback"` are used consistently throughout the plan.

## Recommended Execution Path

This phase is a good fit for **Inline Execution** if we want to keep the worker/session/planner wiring in one head, because Task 3 spans the failure path across repositories, planner orchestration, and progress/session aggregation. If we do use subagents, split only after Task 1 lands so the shared runtime contracts are already stable.

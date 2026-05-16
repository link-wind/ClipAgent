# Structured Execution Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a structured diagnostics contract for execution feedback so worker failures can be normalized once and consumed consistently by the planner runtime.

**Architecture:** Keep the current execution flow intact, but enrich `SearchExecutionFeedback` with structured diagnostics fields and teach the worker to populate them from search/download failures. The deterministic planner should prefer structured diagnostics when rewriting failed scenes, with `failureReason` retained only as a compatibility fallback. The OpenAI runtime stays API-compatible by exposing the same method signature.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, LangGraph, LangChain runtime abstraction, Celery task worker, unittest

---

### Task 1: Expand the execution feedback contract

**Files:**
- Modify: `backend/services/planner_models.py`
- Test: `tests/test_planner_models.py`

- [ ] **Step 1: Write the failing model test**

```python
    def test_search_execution_feedback_supports_structured_diagnostics(self):
        from backend.services.planner_models import SearchExecutionFeedback

        feedback = SearchExecutionFeedback(
            failedSceneIds=[1],
            failureReason="YouTube 当前要求 PO Token，公开视频下载被平台策略限制。",
            failureCategory="platform_blocked",
            primaryProvider="youtube",
            providerDiagnostics=[
                {
                    "provider": "youtube",
                    "message": "YouTube 当前要求 PO Token，公开视频下载被平台策略限制。",
                }
            ],
            sceneDiagnostics=[
                {
                    "sceneId": 1,
                    "retryable": True,
                    "summary": "YouTube blocked the download path",
                }
            ],
            retryStrategyHint="stock_footage_fallback",
        )

        self.assertEqual(feedback.failureCategory, "platform_blocked")
        self.assertEqual(feedback.primaryProvider, "youtube")
        self.assertEqual(feedback.retryStrategyHint, "stock_footage_fallback")
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models -v
```

Expected: FAIL because `SearchExecutionFeedback` does not yet expose the structured diagnostics fields.

- [ ] **Step 3: Add the structured diagnostics fields**

Update `backend/services/planner_models.py`:

```python
class SearchExecutionFeedback(BaseModel):
    failedSceneIds: list[int] = Field(default_factory=list)
    failureReason: str = ""
    failureCategory: str = ""
    primaryProvider: str = ""
    providerDiagnostics: list[dict] = Field(default_factory=list)
    sceneDiagnostics: list[dict] = Field(default_factory=list)
    retryStrategyHint: str = ""
    retryable: bool = True
    feedbackSource: Literal["worker_failure", "api_retry"] = "worker_failure"
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/planner_models.py tests/test_planner_models.py
git commit -m "feat: add structured execution feedback contract"
```

### Task 2: Normalize worker failures into structured diagnostics

**Files:**
- Modify: `backend/services/search_service.py`
- Modify: `backend/tasks/agent_tasks.py`
- Test: `tests/test_agent_backend.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing worker tests**

Add a repository-facing contract test in `tests/test_agent_backend.py` that asserts the search failure exception exposes the structured fields needed for diagnostics:

```python
    def test_all_scene_failures_expose_structured_diagnostics(self):
        from backend.services.search_service import AgentSceneSearchFailure

        exc = AgentSceneSearchFailure(
            "没有下载到可用素材",
            failed_scene_ids=[1, 2],
        )
        exc.failure_category = "no_inventory"
        exc.primary_provider = "youtube"
        exc.provider_diagnostics = [
            {"provider": "youtube", "message": "没有返回候选素材"}
        ]

        self.assertEqual(exc.failed_scene_ids, [1, 2])
        self.assertEqual(exc.failure_category, "no_inventory")
        self.assertEqual(exc.primary_provider, "youtube")
```

Add a worker-level persistence test in `tests/test_agent_jobs.py` that verifies the worker writes structured feedback into the planner replan input:

```python
    def test_run_agent_job_persists_structured_execution_feedback(self):
        from backend.db.repositories import AgentObservationRepository
        from backend.tasks.agent_tasks import run_agent_job

        session_id, job_id = self._create_queued_job()

        class FakeSceneSearchFailure(RuntimeError):
            def __init__(self, message: str, failed_scene_ids: list[int]):
                super().__init__(message)
                self.failed_scene_ids = failed_scene_ids
                self.failure_category = "no_inventory"
                self.primary_provider = "youtube"
                self.provider_diagnostics = [
                    {"provider": "youtube", "message": "没有返回候选素材"}
                ]
                self.scene_diagnostics = [
                    {
                        "sceneId": 1,
                        "retryable": True,
                        "summary": "youtube returned no candidates",
                    }
                ]
                self.retry_strategy_hint = "inventory_broaden"

        async def failing_search_runner(_session_id, _scenes):
            raise FakeSceneSearchFailure("没有下载到可用素材", [1])

        with patch("backend.tasks.agent_tasks.SessionLocal", self.session_factory), patch(
            "backend.tasks.agent_tasks.search_and_download_agent_clips",
            failing_search_runner,
        ):
            run_agent_job(job_id)

        with self.session_factory() as db:
            observations = AgentObservationRepository(db).list_for_session(session_id)
            execution_feedback = next(
                row for row in observations if row.observation_type == "execution_feedback"
            )

        self.assertEqual(
            execution_feedback.payload_json,
            {
                "failedSceneIds": [1],
                "failureReason": "没有下载到可用素材",
                "failureCategory": "no_inventory",
                "primaryProvider": "youtube",
                "providerDiagnostics": [
                    {"provider": "youtube", "message": "没有返回候选素材"}
                ],
                "sceneDiagnostics": [
                    {
                        "sceneId": 1,
                        "retryable": True,
                        "summary": "youtube returned no candidates",
                    }
                ],
                "retryStrategyHint": "inventory_broaden",
                "retryable": True,
                "feedbackSource": "worker_failure",
            },
        )
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend tests.test_agent_jobs -v
```

Expected: FAIL because the worker still only passes `failedSceneIds`, `failureReason`, `retryable`, and `feedbackSource`.

- [ ] **Step 3: Add structured diagnostics to the search failure exception and worker payload**

Update `backend/services/search_service.py`:

```python
class AgentSceneSearchFailure(RuntimeError):
    def __init__(self, message: str, failed_scene_ids: Optional[List[int]] = None):
        super().__init__(message)
        unique_scene_ids = []
        for scene_id in failed_scene_ids or []:
            if scene_id not in unique_scene_ids:
                unique_scene_ids.append(scene_id)
        self.failed_scene_ids = unique_scene_ids
        self.failure_category = ""
        self.primary_provider = ""
        self.provider_diagnostics: list[dict] = []
        self.scene_diagnostics: list[dict] = []
        self.retry_strategy_hint = ""
```

Update `backend/tasks/agent_tasks.py` to pass through the new structured fields when present:

```python
                            planner_orchestrator.persist_execution_feedback_replan(
                                db=db,
                                session_record=session_record,
                                failed_job_record=job_record,
                                execution_feedback={
                                    "failedSceneIds": _extract_failed_scene_ids(exc),
                                    "failureReason": str(exc),
                                    "failureCategory": getattr(exc, "failure_category", ""),
                                    "primaryProvider": getattr(exc, "primary_provider", ""),
                                    "providerDiagnostics": getattr(exc, "provider_diagnostics", []),
                                    "sceneDiagnostics": getattr(exc, "scene_diagnostics", []),
                                    "retryStrategyHint": getattr(exc, "retry_strategy_hint", ""),
                                    "retryable": True,
                                    "feedbackSource": "worker_failure",
                                },
                            )
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend tests.test_agent_jobs -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/search_service.py backend/tasks/agent_tasks.py tests/test_agent_backend.py tests/test_agent_jobs.py
git commit -m "feat: normalize structured execution diagnostics"
```

### Task 3: Teach the planner runtime to consume structured diagnostics

**Files:**
- Modify: `backend/services/planner_runtime_deterministic.py`
- Modify: `backend/services/planner_runtime_openai.py`
- Test: `tests/test_planner_runtime.py`

- [ ] **Step 1: Write the failing planner tests**

Add tests that confirm structured diagnostics win over `failureReason` text and control the rewrite path directly:

```python
    def test_deterministic_runtime_prefers_structured_diagnostics_for_rewrite(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        _next_agent, next_execution, _change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[1],
                failureReason="素材检索失败",
                failureCategory="platform_blocked",
                primaryProvider="youtube",
                providerDiagnostics=[
                    {"provider": "youtube", "message": "PO Token required"}
                ],
                retryStrategyHint="stock_footage_fallback",
                retryable=True,
            ),
        )

        self.assertEqual(next_execution.scenes[0].searchQuery, "software dashboard laptop")
```

```python
    def test_deterministic_runtime_uses_structured_failure_category_before_text_reason(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief("给 Notion AI 做一个 30 秒产品亮点视频")

        _next_agent, next_execution, _change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[1],
                failureReason="素材检索失败",
                failureCategory="no_inventory",
                retryStrategyHint="inventory_broaden",
                retryable=True,
            ),
        )

        self.assertEqual(next_execution.scenes[0].searchQuery, "product interface generic")
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_runtime.PlannerRuntimeTests.test_deterministic_runtime_prefers_structured_diagnostics_for_rewrite tests.test_planner_runtime.PlannerRuntimeTests.test_deterministic_runtime_uses_structured_failure_category_before_text_reason -v
```

Expected: FAIL because the runtime still classifies from `failureReason` only and does not yet consume `retryStrategyHint`.

- [ ] **Step 3: Update the deterministic runtime to read structured fields first**

Update `backend/services/planner_runtime_deterministic.py` so execution feedback classification prefers `failureCategory` and rewrite direction prefers `retryStrategyHint`, while `failureReason` remains the fallback when structured fields are empty.

- [ ] **Step 4: Add the OpenAI runtime stub signature**

Update `backend/services/planner_runtime_openai.py` so the `replan_after_execution_feedback(...)` signature stays aligned with the deterministic runtime.

- [ ] **Step 5: Run the focused tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_runtime -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/planner_runtime_deterministic.py backend/services/planner_runtime_openai.py tests/test_planner_runtime.py
git commit -m "feat: make execution feedback rewrites diagnostics-aware"
```

### Task 4: Run the regression suite and verify the full flow still holds

**Files:**
- Verify only

- [ ] **Step 1: Run the cross-layer regression suite**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models tests.test_planner_runtime tests.test_agent_backend tests.test_agent_jobs tests.test_agent_api_p0 -v
```

Expected: PASS

- [ ] **Step 2: Verify the worker still requeues only when allowed**

Check that search/download failures still replan and requeue once, while render failures continue on the existing terminal path.

- [ ] **Step 3: Commit any final cleanups**

```bash
git add backend/services/planner_models.py backend/services/planner_runtime_deterministic.py backend/services/planner_runtime_openai.py backend/services/search_service.py backend/tasks/agent_tasks.py tests/test_planner_models.py tests/test_planner_runtime.py tests/test_agent_backend.py tests/test_agent_jobs.py
git commit -m "feat: add structured execution diagnostics"
```

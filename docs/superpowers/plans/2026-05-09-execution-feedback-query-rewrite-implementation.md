# Execution Feedback Query Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Phase 4 automatic execution-feedback replanning rewrite failed-scene search queries according to failure reason categories instead of always appending `"alternative"`.

**Architecture:** Keep the existing LangGraph orchestration, worker requeue flow, and persisted execution-feedback contract unchanged. Implement a small deterministic failure-classification and query-rewrite layer inside `backend/services/planner_runtime_deterministic.py`, then lock it with unit tests in `tests/test_planner_runtime.py` and one Phase 4 integration-style assertion in `tests/test_agent_planner_phase4.py`.

**Tech Stack:** Python 3.12, Pydantic, LangGraph, SQLAlchemy, Python `unittest`.

---

## File Structure

- Modify: `backend/services/planner_runtime_deterministic.py`
  - Add deterministic failure classification and failure-aware query rewrite helpers.
- Modify: `tests/test_planner_runtime.py`
  - Add red/green unit tests for failure-category query rewrites and replan history metadata.
- Modify: `tests/test_agent_planner_phase4.py`
  - Add a focused Phase 4 contract test proving the replacement plan carries the smarter rewritten query through the worker/orchestrator path.

Do not modify:

- `backend/tasks/agent_tasks.py`
- `backend/services/search_service.py`
- public API response models
- queue semantics, retry limits, or render failure handling

---

### Task 1: Lock Failure-Aware Runtime Behavior With Failing Unit Tests

**Files:**
- Modify: `tests/test_planner_runtime.py`
- Test: `tests/test_planner_runtime.py`

- [ ] **Step 1: Add a failing test for platform-blocked execution feedback**

In `tests/test_planner_runtime.py`, after `test_deterministic_runtime_replans_after_execution_feedback`, add:

```python
    def test_deterministic_runtime_rewrites_platform_blocked_scene_to_stock_fallback_query(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        next_agent, next_execution, _change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[1],
                failureReason="YouTube 当前要求 PO Token，公开视频下载被平台策略限制。",
                retryable=True,
            ),
        )

        self.assertEqual(
            next_execution.scenes[0].searchQuery,
            "software dashboard laptop",
        )
        self.assertEqual(
            next_execution.scenes[0].keywords,
            ["software", "dashboard", "laptop"],
        )
        self.assertEqual(next_agent.replanHistory[-1]["failureCategory"], "platform_blocked")
        self.assertEqual(next_agent.replanHistory[-1]["rewriteStrategy"], "stock_footage_fallback")
```

- [ ] **Step 2: Add a failing test for no-inventory broadening**

In the same `PlannerRuntimeTests` class, add:

```python
    def test_deterministic_runtime_broadens_no_inventory_scene_without_dropping_core_intent(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        next_agent, next_execution, _change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[2],
                failureReason="pexels: 没有可下载候选素材",
                retryable=True,
            ),
        )

        self.assertEqual(
            next_execution.scenes[1].searchQuery,
            "feature workflow generic",
        )
        self.assertEqual(
            next_execution.scenes[1].keywords,
            ["feature", "workflow", "generic"],
        )
        self.assertEqual(next_agent.replanHistory[-1]["failureCategory"], "no_inventory")
        self.assertEqual(next_agent.replanHistory[-1]["rewriteStrategy"], "inventory_broaden")
```

- [ ] **Step 3: Add a failing test proving untouched scenes remain exactly unchanged**

Still in `PlannerRuntimeTests`, add:

```python
    def test_deterministic_runtime_only_rewrites_failed_scenes_after_execution_feedback(self):
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
                failureReason="YouTube said: Sign in to confirm you're not a bot.",
                retryable=True,
            ),
        )

        self.assertEqual(next_execution.scenes[0].searchQuery, "software dashboard laptop")
        self.assertEqual(next_execution.scenes[1].searchQuery, current_execution.scenes[1].searchQuery)
        self.assertEqual(next_execution.scenes[1].keywords, current_execution.scenes[1].keywords)
```

- [ ] **Step 4: Run the unit tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_runtime.PlannerRuntimeTests.test_deterministic_runtime_rewrites_platform_blocked_scene_to_stock_fallback_query tests.test_planner_runtime.PlannerRuntimeTests.test_deterministic_runtime_broadens_no_inventory_scene_without_dropping_core_intent tests.test_planner_runtime.PlannerRuntimeTests.test_deterministic_runtime_only_rewrites_failed_scenes_after_execution_feedback -v
```

Expected: FAIL because `replan_after_execution_feedback(...)` still appends `"alternative"` and does not record `failureCategory` or `rewriteStrategy`.

- [ ] **Step 5: Commit the failing test baseline**

```bash
git add tests/test_planner_runtime.py
git commit -m "test: lock failure-aware execution feedback rewrites"
```

---

### Task 2: Lock The Phase 4 Worker-Orchestrator Contract With A Failing Integration Test

**Files:**
- Modify: `tests/test_agent_planner_phase4.py`
- Test: `tests/test_agent_planner_phase4.py`

- [ ] **Step 1: Add a failing Phase 4 integration-style test for platform-blocked replanning**

In `tests/test_agent_planner_phase4.py`, after `test_execution_feedback_replan_creates_plan_vnext_and_replacement_job`, add:

```python
    def test_execution_feedback_replan_persists_platform_blocked_query_rewrite(self):
        session_service = AgentSessionService(session_factory=self.session_factory)
        execution_service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=lambda _job_id: None,
        )

        session = session_service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
        confirmed = execution_service.confirm_session(session.id)
        job_id = confirmed.activeJobId

        class FakeSceneSearchFailure(RuntimeError):
            def __init__(self, message: str, failed_scene_ids: list[int]):
                super().__init__(message)
                self.failed_scene_ids = failed_scene_ids

        async def failing_search_runner(_session_id, _scenes):
            raise FakeSceneSearchFailure(
                "YouTube 当前要求 PO Token，公开视频下载被平台策略限制。",
                [1],
            )

        with patch("backend.tasks.agent_tasks.SessionLocal", self.session_factory), patch(
            "backend.tasks.agent_tasks.search_and_download_agent_clips",
            failing_search_runner,
        ):
            run_agent_job(job_id)

        with self.session_factory() as db:
            plans = AgentPlanRepository(db).list_for_session(session.id)

        self.assertEqual(
            plans[-1].execution_plan_json["scenes"][0]["searchQuery"],
            "software dashboard laptop",
        )
        self.assertEqual(
            plans[-1].plan_json["replanHistory"][-1]["failureCategory"],
            "platform_blocked",
        )
        self.assertEqual(
            plans[-1].plan_json["replanHistory"][-1]["rewriteStrategy"],
            "stock_footage_fallback",
        )
```

- [ ] **Step 2: Run the Phase 4 test and verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_planner_phase4.AgentPlannerPhase4Tests.test_execution_feedback_replan_persists_platform_blocked_query_rewrite -v
```

Expected: FAIL because the replanned execution query is still `"product interface alternative"` and the history entry does not yet include failure metadata.

- [ ] **Step 3: Commit the integration test baseline**

```bash
git add tests/test_agent_planner_phase4.py
git commit -m "test: lock phase4 execution feedback query rewrite contract"
```

---

### Task 3: Implement Deterministic Failure Classification And Query Rewrites

**Files:**
- Modify: `backend/services/planner_runtime_deterministic.py`
- Test: `tests/test_planner_runtime.py`
- Test: `tests/test_agent_planner_phase4.py`

- [ ] **Step 1: Add deterministic failure-classification and rewrite helpers**

Near the top of `backend/services/planner_runtime_deterministic.py`, above `class DeterministicPlannerRuntime:`, add:

```python
def _classify_execution_failure(failure_reason: str) -> str:
    text = (failure_reason or "").lower()
    if any(token in text for token in ("po token", "sign in", "not a bot", "challenge", "signature", "401", "403")):
        return "platform_blocked"
    if any(token in failure_reason for token in ("没有返回候选素材", "没有可下载候选素材", "没有下载到可用素材")):
        return "no_inventory"
    if any(token in text for token in ("download failed", "timeout", "connection reset")):
        return "download_transient"
    return "generic_retry"


def _rewrite_strategy_for_failure_category(category: str) -> str:
    if category == "platform_blocked":
        return "stock_footage_fallback"
    if category == "no_inventory":
        return "inventory_broaden"
    return "candidate_alternative"


def _rewrite_keywords_for_failed_scene(scene_keywords: list[str], category: str) -> list[str]:
    core_keywords = [keyword for keyword in scene_keywords[:2] if keyword]
    keyword_set = set(core_keywords)

    if category == "platform_blocked":
        if {"product", "interface"} & keyword_set:
            return ["software", "dashboard", "laptop"]
        if {"feature", "workflow"} & keyword_set:
            return ["team", "workflow", "laptop"]
        lead = core_keywords[:1] or ["product"]
        return [*lead, "stock", "footage"]

    if category == "no_inventory":
        return [*core_keywords, "generic"]

    return [*core_keywords, "alternative"]
```

- [ ] **Step 2: Replace the hard-coded `"alternative"` logic inside `replan_after_execution_feedback(...)`**

In `replan_after_execution_feedback(...)`, replace the current failed-scene rewrite block with:

```python
        failed_scene_ids = set(execution_feedback.failedSceneIds)
        failure_category = _classify_execution_failure(execution_feedback.failureReason)
        rewrite_strategy = _rewrite_strategy_for_failure_category(failure_category)

        updated_execution_scenes = []
        for scene in current_execution.scenes:
            if scene.id in failed_scene_ids:
                next_keywords = _rewrite_keywords_for_failed_scene(scene.keywords, failure_category)
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
                next_keywords = _rewrite_keywords_for_failed_scene(scene.keywords, failure_category)
                updated_agent_scenes.append(
                    scene.model_copy(
                        update={
                            "status": "draft",
                            "keywords": next_keywords,
                        }
                    )
                )
            else:
                updated_agent_scenes.append(scene.model_copy(deep=True))
```

and update the `replanHistory` payload to:

```python
                    {
                        "triggerType": "execution_feedback",
                        "summary": "基于执行失败反馈重写检索查询",
                        "failedSceneIds": sorted(failed_scene_ids),
                        "failureReason": execution_feedback.failureReason,
                        "failureCategory": failure_category,
                        "rewriteStrategy": rewrite_strategy,
                    },
```

- [ ] **Step 3: Run the unit and Phase 4 tests to verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_runtime -v
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_planner_phase4 -v
```

Expected: both commands report `OK`.

- [ ] **Step 4: Commit the runtime implementation**

```bash
git add backend/services/planner_runtime_deterministic.py tests/test_planner_runtime.py tests/test_agent_planner_phase4.py
git commit -m "feat: add failure-aware execution feedback query rewrites"
```

---

### Task 4: Run Phase 4 Regression Verification

**Files:**
- Modify: none
- Test: `tests/test_agent_jobs.py`
- Test: `tests/test_agent_planner_phase4.py`
- Test: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Run the focused Phase 4 regression suite**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_jobs tests.test_agent_planner_phase4 tests.test_agent_api_p0 -v
```

Expected: `OK`, including the existing job requeue/redispatch and API task-state contracts.

- [ ] **Step 2: Inspect the git diff for scope control**

Run:

```bash
git diff -- backend/services/planner_runtime_deterministic.py tests/test_planner_runtime.py tests/test_agent_planner_phase4.py
```

Expected: only deterministic execution-feedback rewrite logic and its tests have changed.

- [ ] **Step 3: Create the final checkpoint commit**

```bash
git add backend/services/planner_runtime_deterministic.py tests/test_planner_runtime.py tests/test_agent_planner_phase4.py
git commit -m "test: verify phase4 failure-aware query rewrite regression"
```

- [ ] **Step 4: Report the verification evidence**

Capture in the implementation handoff:

```text
- tests.test_planner_runtime: OK
- tests.test_agent_planner_phase4: OK
- tests.test_agent_jobs tests.test_agent_planner_phase4 tests.test_agent_api_p0: OK
```

Do not claim success without the green test output.

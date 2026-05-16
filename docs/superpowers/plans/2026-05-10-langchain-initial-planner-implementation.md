# LangChain Initial Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LangChain the default initial planner so prompt-based session creation produces a model-driven `AgentPlan` and `ExecutionPlan`, while all replanning paths continue to use the deterministic runtime.

**Architecture:** Add a dedicated `LangChainPlannerRuntime` that owns only `build_plan_from_brief()` and delegates every `replan_*` method to `DeterministicPlannerRuntime`. Keep `PlannerOrchestrator` and `planner_graph.py` stable, switch the default selector mode to `langchain`, and use test-only deterministic defaults so existing suites stay stable without requiring live OpenAI calls.

**Tech Stack:** FastAPI, Pydantic v2, LangChain, LangGraph, langchain-openai, SQLAlchemy, unittest

---

### Task 1: Add the structured initial-planning wrapper model

**Files:**
- Modify: `backend/services/planner_models.py`
- Test: `tests/test_planner_models.py`

- [ ] **Step 1: Write the failing model test**

Add this test to `tests/test_planner_models.py`:

```python
    def test_initial_planning_result_wraps_agent_and_execution_plan(self):
        from backend.services.planner_models import InitialPlanningResult

        result = InitialPlanningResult(
            agentPlan={
                "title": "Notion AI 产品介绍",
                "goal": "生成 30 秒产品介绍视频",
                "summary": "突出真实产品体验",
                "scenes": [
                    {
                        "id": 1,
                        "description": "展示产品首页",
                        "keywords": ["product", "interface"],
                        "duration": 6,
                    }
                ],
            },
            executionPlan={
                "title": "Notion AI 产品介绍",
                "targetDuration": 30,
                "style": "快节奏社媒短片",
                "scenes": [
                    {
                        "id": 1,
                        "description": "展示产品首页",
                        "keywords": ["product", "interface"],
                        "searchQuery": "product interface",
                        "duration": 6,
                    }
                ],
            },
        )

        self.assertEqual(result.agentPlan.title, "Notion AI 产品介绍")
        self.assertEqual(result.executionPlan.scenes[0].searchQuery, "product interface")
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models.PlannerModelTests.test_initial_planning_result_wraps_agent_and_execution_plan -v
```

Expected: FAIL because `InitialPlanningResult` does not exist yet.

- [ ] **Step 3: Add the wrapper model**

Update `backend/services/planner_models.py` by inserting this class after `ExecutionPlan`:

```python
class InitialPlanningResult(BaseModel):
    agentPlan: AgentPlan
    executionPlan: ExecutionPlan
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models.PlannerModelTests.test_initial_planning_result_wraps_agent_and_execution_plan -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/planner_models.py tests/test_planner_models.py
git commit -m "feat: add initial planning result contract"
```

### Task 2: Implement the LangChain planner runtime

**Files:**
- Create: `backend/services/planner_runtime_langchain.py`
- Modify: `tests/test_planner_runtime.py`

- [ ] **Step 1: Write the failing runtime tests**

Add these helper fakes and tests to `tests/test_planner_runtime.py`:

```python
class _FakeStructuredPlanner:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error

    def invoke(self, _messages):
        if self.error is not None:
            raise self.error
        return self.result


class _FakeChatModel:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.schema = None

    def with_structured_output(self, schema):
        self.schema = schema
        return _FakeStructuredPlanner(result=self.result, error=self.error)
```

```python
    def test_langchain_runtime_builds_initial_plan_from_structured_output(self):
        from backend.services.planner_models import InitialPlanningResult
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        fake_llm = _FakeChatModel(
            result=InitialPlanningResult(
                agentPlan={
                    "title": "Notion AI 产品介绍",
                    "goal": "生成 30 秒产品介绍视频",
                    "summary": "突出真实产品体验",
                    "scenes": [
                        {
                            "id": 1,
                            "purpose": "建立产品识别",
                            "description": "展示产品首页",
                            "keywords": ["product", "interface"],
                            "duration": 6,
                        }
                    ],
                },
                executionPlan={
                    "title": "Notion AI 产品介绍",
                    "targetDuration": 30,
                    "style": "快节奏社媒短片",
                    "scenes": [
                        {
                            "id": 1,
                            "description": "展示产品首页",
                            "keywords": ["product", "interface"],
                            "searchQuery": "product interface",
                            "duration": 6,
                        }
                    ],
                },
            )
        )

        runtime = LangChainPlannerRuntime(model_name="gpt-4o-mini", llm=fake_llm)
        agent_plan, execution_plan = runtime.build_plan_from_brief("给 Notion AI 做一个视频")

        self.assertEqual(agent_plan.title, "Notion AI 产品介绍")
        self.assertEqual(execution_plan.scenes[0].searchQuery, "product interface")
```

```python
    def test_langchain_runtime_rejects_mismatched_scene_ids(self):
        from backend.services.planner_models import InitialPlanningResult
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        fake_llm = _FakeChatModel(
            result=InitialPlanningResult(
                agentPlan={
                    "title": "Mismatch",
                    "goal": "Goal",
                    "summary": "Summary",
                    "scenes": [
                        {"id": 1, "description": "A", "keywords": ["product"], "duration": 6}
                    ],
                },
                executionPlan={
                    "title": "Mismatch",
                    "targetDuration": 30,
                    "style": "快节奏社媒短片",
                    "scenes": [
                        {"id": 2, "description": "A", "keywords": ["product"], "searchQuery": "product", "duration": 6}
                    ],
                },
            )
        )

        runtime = LangChainPlannerRuntime(model_name="gpt-4o-mini", llm=fake_llm)

        with self.assertRaisesRegex(ValueError, "scene ids"):
            runtime.build_plan_from_brief("给 Notion AI 做一个视频")
```

```python
    def test_langchain_runtime_bubbles_up_model_failures(self):
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=_FakeChatModel(error=RuntimeError("LangChain planning failed")),
        )

        with self.assertRaisesRegex(RuntimeError, "LangChain planning failed"):
            runtime.build_plan_from_brief("给 Notion AI 做一个视频")
```

```python
    def test_langchain_runtime_delegates_grounding_replan_to_deterministic_runtime(self):
        from unittest.mock import Mock

        from backend.services.planner_models import CandidateConfirmationFeedback, GroundingFeedback
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        delegate = Mock()
        delegate.replan_after_grounding.return_value = ("agent", "execution", "summary")
        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=_FakeChatModel(),
            deterministic_delegate=delegate,
        )

        result = runtime.replan_after_grounding(
            current_agent="agent-plan",
            current_execution="execution-plan",
            grounding_feedback=GroundingFeedback(),
            confirmation_feedback=CandidateConfirmationFeedback(),
        )

        self.assertEqual(result, ("agent", "execution", "summary"))
        delegate.replan_after_grounding.assert_called_once()
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_builds_initial_plan_from_structured_output tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_rejects_mismatched_scene_ids tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_bubbles_up_model_failures tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_delegates_grounding_replan_to_deterministic_runtime -v
```

Expected: FAIL because `backend/services/planner_runtime_langchain.py` does not exist yet.

- [ ] **Step 3: Write the minimal runtime**

Create `backend/services/planner_runtime_langchain.py`:

```python
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.services.planner_models import (
    AgentPlan,
    CandidateConfirmationFeedback,
    ExecutionPlan,
    GroundingFeedback,
    InitialPlanningResult,
    SearchExecutionFeedback,
    UserRevisionFeedback,
)
from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime


INITIAL_PLANNER_SYSTEM_PROMPT = """你是一个短视频 planning assistant。
输出 2 到 4 个 scene。
AgentPlan 与 ExecutionPlan 的 scene 数量和 id 必须一致。
searchQuery 必须是可用于素材检索的英文短语。
keywords 保持简短、可检索、不要为空。
"""


class LangChainPlannerRuntime:
    def __init__(self, model_name: str, llm=None, deterministic_delegate=None):
        self.model_name = model_name
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0)
        self.deterministic_delegate = deterministic_delegate or DeterministicPlannerRuntime()

    def _planner_runnable(self):
        return self.llm.with_structured_output(InitialPlanningResult)

    def build_plan_from_brief(self, brief: str) -> tuple[AgentPlan, ExecutionPlan]:
        result = self._planner_runnable().invoke(
            [
                SystemMessage(content=INITIAL_PLANNER_SYSTEM_PROMPT),
                HumanMessage(content=brief.strip() or "生成产品介绍视频"),
            ]
        )
        normalized = self._normalize_result(result)
        self._validate_result(normalized)
        return normalized.agentPlan, normalized.executionPlan

    def _normalize_result(self, result: InitialPlanningResult) -> InitialPlanningResult:
        agent_plan = result.agentPlan.model_copy(
            update={
                "title": result.agentPlan.title.strip(),
                "goal": result.agentPlan.goal.strip(),
                "summary": result.agentPlan.summary.strip(),
                "scenes": [
                    scene.model_copy(
                        update={
                            "keywords": [keyword.strip() for keyword in scene.keywords if keyword.strip()],
                        }
                    )
                    for scene in result.agentPlan.scenes
                ],
            }
        )
        execution_plan = result.executionPlan.model_copy(
            update={
                "title": result.executionPlan.title.strip(),
                "style": result.executionPlan.style.strip(),
                "scenes": [
                    scene.model_copy(
                        update={
                            "keywords": [keyword.strip() for keyword in scene.keywords if keyword.strip()],
                            "searchQuery": " ".join(scene.searchQuery.split()),
                        }
                    )
                    for scene in result.executionPlan.scenes
                ],
            }
        )
        return InitialPlanningResult(agentPlan=agent_plan, executionPlan=execution_plan)

    def _validate_result(self, result: InitialPlanningResult) -> None:
        agent_scene_ids = [scene.id for scene in result.agentPlan.scenes]
        execution_scene_ids = [scene.id for scene in result.executionPlan.scenes]
        if not agent_scene_ids or not execution_scene_ids:
            raise ValueError("LangChain planner returned no scenes")
        if agent_scene_ids != execution_scene_ids:
            raise ValueError("LangChain planner returned mismatched scene ids")
        if agent_scene_ids != list(range(1, len(agent_scene_ids) + 1)):
            raise ValueError("LangChain planner returned non-sequential scene ids")
        if not result.agentPlan.title or not result.agentPlan.goal or not result.agentPlan.summary:
            raise ValueError("LangChain planner returned blank plan metadata")
        if any(not scene.keywords for scene in result.agentPlan.scenes):
            raise ValueError("LangChain planner returned blank agent-scene keywords")
        if any(not scene.searchQuery for scene in result.executionPlan.scenes):
            raise ValueError("LangChain planner returned blank execution search queries")
        if any(scene.duration <= 0 for scene in result.executionPlan.scenes):
            raise ValueError("LangChain planner returned non-positive scene duration")
        if result.executionPlan.targetDuration < sum(scene.duration for scene in result.executionPlan.scenes):
            raise ValueError("LangChain planner returned target duration shorter than scene sum")

    def replan_after_grounding(self, **kwargs):
        return self.deterministic_delegate.replan_after_grounding(**kwargs)

    def replan_after_user_revision(self, **kwargs):
        return self.deterministic_delegate.replan_after_user_revision(**kwargs)

    def replan_after_execution_feedback(self, **kwargs):
        return self.deterministic_delegate.replan_after_execution_feedback(**kwargs)
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_builds_initial_plan_from_structured_output tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_rejects_mismatched_scene_ids tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_bubbles_up_model_failures tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_delegates_grounding_replan_to_deterministic_runtime -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/planner_runtime_langchain.py tests/test_planner_runtime.py
git commit -m "feat: add langchain initial planner runtime"
```

### Task 3: Switch the default selector to LangChain and harden planner graph tests

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/services/planner_runtime.py`
- Modify: `tests/test_planner_runtime.py`
- Modify: `tests/test_planner_graph.py`
- Modify: `tests/test_agent_persistence.py`

- [ ] **Step 1: Write the failing selector and settings tests**

Update `tests/test_planner_runtime.py`:

```python
    def test_selector_returns_langchain_runtime_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            from backend.config import get_settings
            from backend.services.planner_runtime import get_planner_runtime

            get_settings.cache_clear()
            runtime = get_planner_runtime()
            self.assertEqual(runtime.__class__.__name__, "LangChainPlannerRuntime")
            get_settings.cache_clear()
```

```python
    def test_selector_returns_deterministic_runtime_when_overridden(self):
        with patch.dict("os.environ", {"CLIPFORGE_PLANNER_MODE": "deterministic"}, clear=True):
            from backend.config import get_settings
            from backend.services.planner_runtime import get_planner_runtime

            get_settings.cache_clear()
            runtime = get_planner_runtime()
            self.assertEqual(runtime.__class__.__name__, "DeterministicPlannerRuntime")
            get_settings.cache_clear()
```

Update `tests/test_agent_persistence.py`:

```python
    def test_planner_settings_support_default_and_override(self):
        env = {}
        settings = self._load_settings(env)
        self.assertEqual(settings.planner_mode, "langchain")
        self.assertEqual(settings.planner_model, "gpt-4o-mini")

        env = {
            "CLIPFORGE_PLANNER_MODE": "deterministic",
            "CLIPFORGE_PLANNER_MODEL": "gpt-4.1",
        }
        settings = self._load_settings(env)
        self.assertEqual(settings.planner_mode, "deterministic")
        self.assertEqual(settings.planner_model, "gpt-4.1")
```

Update `tests/test_planner_graph.py` so the initial-planning graph test patches the runtime instead of depending on the process default:

```python
    def test_build_plan_graph_returns_initial_plan_state(self):
        from unittest.mock import Mock, patch

        from backend.services.planner_graph import run_initial_planning
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

        runtime = DeterministicPlannerRuntime()
        agent_plan, execution_plan = runtime.build_plan_from_brief("给 Notion AI 做一个 30 秒产品视频")
        fake_runtime = Mock()
        fake_runtime.build_plan_from_brief.return_value = (agent_plan, execution_plan)

        with patch("backend.services.planner_graph.get_planner_runtime", return_value=fake_runtime):
            state = run_initial_planning(
                session_id="session-1",
                brief="给 Notion AI 做一个 30 秒产品视频",
            )

        self.assertEqual(state["status"], "planning_complete")
        self.assertIn("agentPlan", state)
        self.assertIn("executionPlan", state)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_runtime tests.test_planner_graph tests.test_agent_persistence -v
```

Expected: FAIL because the default config still says `deterministic` and the selector still imports `planner_runtime_openai.py`.

- [ ] **Step 3: Switch the defaults and selector**

Update `backend/config.py`:

```python
        planner_mode=os.getenv("CLIPFORGE_PLANNER_MODE", "langchain"),
```

Update `backend/services/planner_runtime.py`:

```python
from backend.config import get_settings
from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime


def get_planner_runtime():
    settings = get_settings()
    if settings.planner_mode == "deterministic":
        return DeterministicPlannerRuntime()
    if settings.planner_mode == "langchain":
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        return LangChainPlannerRuntime(model_name=settings.planner_model)
    raise ValueError(f"Unknown planner mode: {settings.planner_mode}")
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_runtime tests.test_planner_graph tests.test_agent_persistence -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/services/planner_runtime.py tests/test_planner_runtime.py tests/test_planner_graph.py tests/test_agent_persistence.py
git commit -m "feat: default planner selector to langchain"
```

### Task 4: Stabilize tests around the new default and add planning-failure contracts

**Files:**
- Create: `tests/__init__.py`
- Modify: `tests/test_agent_backend.py`

- [ ] **Step 1: Write the failing service and API contract tests**

Add this service-level rollback test to `tests/test_agent_backend.py` inside `AgentApiTests`:

```python
    def test_create_session_rolls_back_when_langchain_planning_fails(self):
        from sqlalchemy import select, func

        from backend.db.models import AgentPlanRecord, AgentSessionRecord

        class FailingRuntime:
            def build_plan_from_brief(self, _brief):
                raise RuntimeError("LangChain planning failed")

        with patch.dict("os.environ", {"CLIPFORGE_PLANNER_MODE": "langchain"}, clear=False), patch(
            "backend.services.planner_graph.get_planner_runtime",
            return_value=FailingRuntime(),
        ):
            from backend.config import get_settings

            get_settings.cache_clear()
            with self.assertRaisesRegex(RuntimeError, "LangChain planning failed"):
                self.session_service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
            get_settings.cache_clear()

        with self.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AgentSessionRecord)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(AgentPlanRecord)), 0)
```

Change `_make_test_client(...)` at the top of `tests/test_agent_backend.py` to accept a flag:

```python
def _make_test_client(app, raise_server_exceptions=True):
    from fastapi.testclient import TestClient

    original_init = httpx.Client.__init__

    def compatible_init(self, *args, **kwargs):
        kwargs.pop("app", None)
        return original_init(self, *args, **kwargs)

    httpx.Client.__init__ = compatible_init
    try:
        return TestClient(app, raise_server_exceptions=raise_server_exceptions)
    finally:
        httpx.Client.__init__ = original_init
```

Add this API-level failure test:

```python
    def test_create_session_api_returns_500_when_langchain_planning_fails(self):
        from backend.main import app

        class FailingRuntime:
            def build_plan_from_brief(self, _brief):
                raise RuntimeError("LangChain planning failed")

        with patch.dict("os.environ", {"CLIPFORGE_PLANNER_MODE": "langchain"}, clear=False), patch(
            "backend.services.planner_graph.get_planner_runtime",
            return_value=FailingRuntime(),
        ):
            from backend.config import get_settings

            get_settings.cache_clear()
            client = _make_test_client(app, raise_server_exceptions=False)
            response = client.post(
                "/api/agent/sessions",
                json={"message": "给 Notion AI 做一个 30 秒产品亮点视频"},
            )
            get_settings.cache_clear()

        self.assertEqual(response.status_code, 500)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.AgentApiTests.test_create_session_rolls_back_when_langchain_planning_fails tests.test_agent_backend.AgentApiTests.test_create_session_api_returns_500_when_langchain_planning_fails -v
```

Expected: FAIL because the test harness still defaults to real `langchain` mode nowhere, and there is no deterministic default for the broader suite.

- [ ] **Step 3: Add a deterministic test-harness default**

Create `tests/__init__.py`:

```python
import os

os.environ.setdefault("CLIPFORGE_PLANNER_MODE", "deterministic")
```

This keeps the broad test suite stable while still allowing LangChain-specific tests to override `CLIPFORGE_PLANNER_MODE` with `patch.dict(..., clear=False)` and `get_settings.cache_clear()`.

- [ ] **Step 4: Run the focused tests and a stability subset**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend tests.test_agent_api_p0 tests.test_agent_jobs tests.test_agent_planner_phase1 tests.test_agent_planner_phase2 tests.test_agent_planner_phase3 tests.test_agent_planner_phase4 -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/__init__.py tests/test_agent_backend.py
git commit -m "test: isolate langchain default from legacy planner suites"
```

### Task 5: Update docs and run final regression

**Files:**
- Modify: `README.md`
- Test: `tests/test_planner_models.py`
- Test: `tests/test_planner_runtime.py`
- Test: `tests/test_planner_graph.py`
- Test: `tests/test_agent_backend.py`
- Test: `tests/test_agent_persistence.py`
- Test: `tests/test_agent_api_p0.py`
- Test: `tests/test_agent_jobs.py`
- Test: `tests/test_agent_planner_phase1.py`
- Test: `tests/test_agent_planner_phase2.py`
- Test: `tests/test_agent_planner_phase3.py`
- Test: `tests/test_agent_planner_phase4.py`

- [ ] **Step 1: Write the failing docs test expectation**

Update the existing README/config coverage in `tests/test_agent_persistence.py` so the planner settings test is already asserting the new default:

```python
        self.assertEqual(settings.planner_mode, "langchain")
```

If you want an explicit docs-facing check, add this assertion to `tests/test_agent_backend.py`:

```python
    def test_readme_documents_langchain_planner_default(self):
        readme = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("CLIPFORGE_PLANNER_MODE", readme)
        self.assertIn("default `langchain`", readme)
        self.assertIn("set to `deterministic`", readme)
```

- [ ] **Step 2: Run the docs-focused test and verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_persistence tests.test_agent_backend -v
```

Expected: FAIL because `README.md` does not yet describe the new default mode and deterministic override guidance.

- [ ] **Step 3: Update the README**

Edit `README.md` in the environment-variable section to include:

```md
- `OPENAI_API_KEY`：用于默认的 LangChain initial planner；如果要在本地或测试环境绕过模型调用，可把 `CLIPFORGE_PLANNER_MODE` 设为 `deterministic`。
- `CLIPFORGE_PLANNER_MODE`：可选，planner 运行模式，默认 `langchain`；设为 `deterministic` 可回退到规则版 planner。
- `CLIPFORGE_PLANNER_MODEL`：可选，LangChain planner 使用的模型名，默认 `gpt-4o-mini`。
```

Also update any `openai` wording around planner mode to `langchain`.

- [ ] **Step 4: Run the full regression and verify it passes**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models tests.test_planner_runtime tests.test_planner_graph tests.test_agent_backend tests.test_agent_persistence tests.test_agent_api_p0 tests.test_agent_jobs tests.test_agent_planner_phase1 tests.test_agent_planner_phase2 tests.test_agent_planner_phase3 tests.test_agent_planner_phase4 -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_agent_persistence.py tests/test_agent_backend.py
git commit -m "docs: document langchain planner default"
```

## Self-Review

- Spec coverage:
  - default `langchain` mode: Task 3
  - LangChain-only initial planning: Tasks 1-3
  - deterministic replan delegation: Task 2
  - no fallback / direct failure semantics: Task 4
  - docs update: Task 5
- Placeholder scan:
  - no `TODO` / `TBD`
  - every task lists exact files, tests, commands, and commit steps
- Type consistency:
  - `InitialPlanningResult`, `LangChainPlannerRuntime`, `CLIPFORGE_PLANNER_MODE=langchain`, and deterministic delegate naming are consistent across all tasks

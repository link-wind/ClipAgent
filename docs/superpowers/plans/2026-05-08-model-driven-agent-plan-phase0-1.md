# Model-Driven Agent Plan Phase 0-1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first executable slice of the LangChain/LangGraph-backed model-driven agent plan architecture by adding planner dependencies, persistent plan/observation foundations, a minimal planning graph, and `build_plan_from_brief` wired into `/api/agent/sessions`.

**Architecture:** This phase intentionally stops at Phase 0 + Phase 1 from the spec. We keep the current FastAPI, SQLAlchemy, and Celery execution pipeline intact, but introduce a new planning spine: LangChain handles structured planner calls, LangGraph holds planning state and transitions, and the existing agent session flow begins delegating initial plan generation to the new planner graph. The output remains compatible with the current frontend and execution flow by projecting `AgentPlan` into an `ExecutionPlan`/legacy session shape.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, LangChain, LangGraph, OpenAI, unittest

---

## File Structure

### New files

- `backend/services/planner_models.py`
  - Defines `AgentPlan`, `ExecutionPlan`, `AgentObservation`, planner state payloads, and deterministic planner contracts.
- `backend/services/planner_runtime_deterministic.py`
  - Deterministic runtime for local/dev/test planner behavior.
- `backend/services/planner_runtime_openai.py`
  - LangChain-backed OpenAI runtime with structured output and planner action methods.
- `backend/services/planner_runtime.py`
  - Shared planner runtime selector/factory that chooses deterministic vs OpenAI mode.
- `backend/services/planner_graph.py`
  - Minimal LangGraph state definition, build-plan node, and graph factory.
- `backend/services/planner_projection.py`
  - Converts `AgentPlan` to execution-compatible plan payloads and current `EditPlan` shape when needed.
- `backend/services/planner_orchestrator.py`
  - Thin adapter used by `AgentSessionService` to create initial plan versions and observations through the planner graph.
- `backend/db/repositories/agent_observations.py`
  - Repository for planner observations.
- `tests/test_planner_models.py`
  - Contract tests for planner data models.
- `tests/test_planner_runtime.py`
  - Deterministic/runtime selection tests.
- `tests/test_planner_graph.py`
  - Graph state + build-plan entry tests.
- `tests/test_agent_planner_phase1.py`
  - Integration tests for create-session initial planning behavior.

### Modified files

- `backend/requirements.txt`
  - Add LangChain/LangGraph dependencies.
- `backend/config.py`
  - Add planner runtime configuration.
- `backend/db/models.py`
  - Add observation table and expand plan/session metadata needed for phase 0-1.
- `backend/db/repositories/__init__.py`
  - Export new observation repository.
- `backend/db/repositories/agent_plans.py`
  - Add helpers for immutable version metadata access.
- `backend/models/agent.py`
  - Add planner-facing models that must surface to API/session reads in phase 1.
- `backend/services/agent_read_service.py`
  - Read new plan metadata while remaining backward compatible.
- `backend/services/agent_session_service.py`
  - Replace create-session grounding-first path with planner-graph-driven initial plan creation.
- `tests/test_agent_backend.py`
  - Update session creation expectations for phase 1.
- `tests/test_agent_persistence.py`
  - Cover observation table + expanded plan/session columns.

## Scope Guardrails

- This plan does **not** implement `replan_after_grounding`, `replan_after_user_revision`, or execution-feedback auto-replan.
- This plan does **not** require changing Celery workers or render flow.
- This plan does **not** migrate the frontend to new visual replan history UI.
- This plan does **not** remove current grounding logic; it keeps it as compatibility/fallback where needed.

### Task 1: Add planner dependencies and runtime config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/config.py`
- Test: `tests/test_agent_persistence.py`

- [ ] **Step 1: Write the failing config test for planner settings**

```python
def test_planner_settings_support_default_and_override(self):
    env = {}
    settings = self._load_settings(env)
    self.assertEqual(settings.planner_mode, "deterministic")
    self.assertEqual(settings.planner_model, "gpt-4o-mini")

    env = {
        "CLIPFORGE_PLANNER_MODE": "openai",
        "CLIPFORGE_PLANNER_MODEL": "gpt-4.1",
    }
    settings = self._load_settings(env)
    self.assertEqual(settings.planner_mode, "openai")
    self.assertEqual(settings.planner_model, "gpt-4.1")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_agent_persistence.ConfigTests.test_planner_settings_support_default_and_override -v
```

Expected: FAIL because `Settings` does not expose `planner_mode` or `planner_model`.

- [ ] **Step 3: Add LangChain/LangGraph dependencies**

Update `backend/requirements.txt` by appending:

```text
langchain==0.3.25
langgraph==0.2.60
langchain-openai==0.2.14
```

- [ ] **Step 4: Add planner settings to config**

Update `backend/config.py` so `Settings` includes:

```python
    # Planner runtime mode
    planner_mode: str
    # Planner model name
    planner_model: str
```

and `get_settings()` returns:

```python
        planner_mode=os.getenv("CLIPFORGE_PLANNER_MODE", "deterministic"),
        planner_model=os.getenv("CLIPFORGE_PLANNER_MODEL", "gpt-4o-mini"),
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
python -m unittest tests.test_agent_persistence.ConfigTests.test_planner_settings_support_default_and_override -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/config.py tests/test_agent_persistence.py
git commit -m "feat: add planner runtime settings"
```

### Task 2: Add planner persistence foundations

**Files:**
- Modify: `backend/db/models.py`
- Modify: `backend/db/repositories/__init__.py`
- Modify: `backend/db/repositories/agent_plans.py`
- Create: `backend/db/repositories/agent_observations.py`
- Test: `tests/test_agent_persistence.py`

- [ ] **Step 1: Write the failing persistence test for observation table and expanded plan fields**

Add tests that assert:

```python
self.assertIn("agent_observations", tables)
self.assertEqual(
    set(models.AgentObservationRecord.__table__.columns.keys()),
    {
        "id",
        "session_id",
        "plan_id",
        "observation_type",
        "summary",
        "payload_json",
        "source_message_id",
        "source_job_id",
        "created_at",
    },
)
```

and expand the plan/session column checks to include:

```python
"current_plan_id",
"planner_trace_json",
"parent_plan_id",
"trigger_type",
"planner_mode",
"planner_model",
"execution_plan_json",
"change_summary",
"status",
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_agent_persistence.AgentPersistenceModelTests.test_agent_persistence_models_expose_required_columns -v
```

Expected: FAIL because the new columns/table do not exist.

- [ ] **Step 3: Extend DB models**

Update `backend/db/models.py` with:

```python
    current_plan_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_plans.id"),
        nullable=True,
    )
    planner_trace_json: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
```

inside `AgentSessionRecord`.

Update `AgentPlanRecord` with:

```python
    parent_plan_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_plans.id"),
        nullable=True,
    )
    trigger_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    planner_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    planner_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    execution_plan_json: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
```

Add new model:

```python
class AgentObservationRecord(Base):
    __tablename__ = "agent_observations"
    __table_args__ = (
        Index("idx_agent_observations_session_id_created_at", "session_id", "created_at"),
        Index("idx_agent_observations_plan_id_created_at", "plan_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_sessions.id"), nullable=False)
    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_plans.id"), nullable=True)
    observation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_message_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_messages.id"), nullable=True)
    source_job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_jobs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

- [ ] **Step 4: Add observation repository and exports**

Create `backend/db/repositories/agent_observations.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import AgentObservationRecord


class AgentObservationRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, **values) -> AgentObservationRecord:
        record = AgentObservationRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list_for_session(self, session_id: str) -> list[AgentObservationRecord]:
        stmt = (
            select(AgentObservationRecord)
            .where(AgentObservationRecord.session_id == session_id)
            .order_by(AgentObservationRecord.created_at.asc(), AgentObservationRecord.id.asc())
        )
        return list(self.db.scalars(stmt))
```

Update `backend/db/repositories/__init__.py` to export `AgentObservationRepository`.

- [ ] **Step 5: Add immutable plan metadata helper**

Add to `backend/db/repositories/agent_plans.py`:

```python
    def list_for_session(self, session_id: str) -> list[AgentPlanRecord]:
        stmt = (
            select(AgentPlanRecord)
            .where(AgentPlanRecord.session_id == session_id)
            .order_by(
                AgentPlanRecord.version.asc(),
                AgentPlanRecord.created_at.asc(),
                AgentPlanRecord.id.asc(),
            )
        )
        return list(self.db.scalars(stmt))
```

- [ ] **Step 6: Run persistence tests to verify they pass**

Run:

```bash
python -m unittest tests.test_agent_persistence.AgentPersistenceModelTests -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/db/models.py backend/db/repositories/__init__.py backend/db/repositories/agent_plans.py backend/db/repositories/agent_observations.py tests/test_agent_persistence.py
git commit -m "feat: add planner persistence foundations"
```

### Task 3: Add planner models and deterministic runtime

**Files:**
- Create: `backend/services/planner_models.py`
- Create: `backend/services/planner_runtime_deterministic.py`
- Create: `backend/services/planner_runtime.py`
- Modify: `backend/models/agent.py`
- Test: `tests/test_planner_models.py`
- Test: `tests/test_planner_runtime.py`

- [ ] **Step 1: Write the failing planner model contract test**

Create `tests/test_planner_models.py` with:

```python
import unittest

from backend.services.planner_models import AgentPlan, ExecutionPlan, AgentObservation


class PlannerModelTests(unittest.TestCase):
    def test_agent_plan_defaults_are_stable(self):
        plan = AgentPlan(
            title="Notion AI 产品介绍",
            goal="生成 30 秒产品介绍视频",
            summary="突出真实产品体验",
        )
        self.assertEqual(plan.openIssues, [])
        self.assertEqual(plan.replanHistory, [])
        self.assertEqual(plan.scenes, [])

    def test_execution_plan_scene_supports_grounding_candidate_ids(self):
        plan = ExecutionPlan(
            title="Demo",
            targetDuration=30,
            style="科技感",
            scenes=[
                {
                    "id": 1,
                    "description": "展示首页",
                    "searchQuery": "notion ai homepage",
                    "duration": 6,
                    "groundingCandidateIds": ["fixture:1"],
                }
            ],
        )
        self.assertEqual(plan.scenes[0].groundingCandidateIds, ["fixture:1"])

    def test_observation_payload_round_trips(self):
        observation = AgentObservation(
            id="obs-1",
            sessionId="session-1",
            observationType="user_message",
            payload={"message": "做一个产品视频"},
            createdAt="2026-05-08T00:00:00Z",
        )
        self.assertEqual(observation.payload["message"], "做一个产品视频")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_planner_models -v
```

Expected: FAIL because planner models do not exist.

- [ ] **Step 3: Create planner models**

Create `backend/services/planner_models.py` with:

```python
from typing import Literal

from pydantic import BaseModel, Field


class BriefUnderstanding(BaseModel):
    productName: str = ""
    audience: str = ""
    styleHint: str = ""
    featureHints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class AgentScene(BaseModel):
    id: int
    purpose: str = ""
    description: str
    visualIntent: str = ""
    searchIntent: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    groundingCandidateIds: list[str] = Field(default_factory=list)
    duration: float = 6.0
    fallbackPolicy: str = ""
    status: Literal["draft", "grounded", "blocked", "ready_for_execution"] = "draft"


class AgentPlan(BaseModel):
    title: str
    goal: str
    summary: str
    understanding: BriefUnderstanding = Field(default_factory=BriefUnderstanding)
    constraints: dict = Field(default_factory=dict)
    strategy: dict = Field(default_factory=dict)
    scenes: list[AgentScene] = Field(default_factory=list)
    grounding: dict = Field(default_factory=dict)
    openIssues: list[dict] = Field(default_factory=list)
    replanHistory: list[dict] = Field(default_factory=list)


class ExecutionScene(BaseModel):
    id: int
    description: str
    keywords: list[str] = Field(default_factory=list)
    searchQuery: str
    duration: float
    groundingCandidateIds: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    title: str
    targetDuration: float
    style: str
    scenes: list[ExecutionScene] = Field(default_factory=list)


class AgentObservation(BaseModel):
    id: str
    sessionId: str
    relatedPlanVersion: int | None = None
    observationType: str
    payload: dict = Field(default_factory=dict)
    summary: str = ""
    createdAt: str
```

- [ ] **Step 4: Add deterministic runtime and selector**

Create `backend/services/planner_runtime_deterministic.py`:

```python
from backend.services.planner_models import AgentPlan, ExecutionPlan


class DeterministicPlannerRuntime:
    def build_plan_from_brief(self, brief: str) -> tuple[AgentPlan, ExecutionPlan]:
        title = "智能剪辑短片"
        goal = brief.strip() or "生成产品介绍视频"
        plan = AgentPlan(
            title=title,
            goal=goal,
            summary="根据用户 brief 生成的初版计划",
            scenes=[
                {
                    "id": 1,
                    "purpose": "建立产品识别",
                    "description": "开场展示产品主题",
                    "keywords": ["product", "interface"],
                    "duration": 6,
                },
                {
                    "id": 2,
                    "purpose": "突出核心卖点",
                    "description": "展示重点功能或体验",
                    "keywords": ["feature", "workflow"],
                    "duration": 8,
                },
            ],
        )
        execution = ExecutionPlan(
            title=title,
            targetDuration=30,
            style="快节奏社媒短片",
            scenes=[
                {
                    "id": 1,
                    "description": "开场展示产品主题",
                    "keywords": ["product", "interface"],
                    "searchQuery": "product interface",
                    "duration": 6,
                },
                {
                    "id": 2,
                    "description": "展示重点功能或体验",
                    "keywords": ["feature", "workflow"],
                    "searchQuery": "feature workflow",
                    "duration": 8,
                },
            ],
        )
        return plan, execution
```

Create `backend/services/planner_runtime.py`:

```python
from backend.config import get_settings
from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime


def get_planner_runtime():
    settings = get_settings()
    if settings.planner_mode == "deterministic":
        return DeterministicPlannerRuntime()
    from backend.services.planner_runtime_openai import OpenAIPlannerRuntime

    return OpenAIPlannerRuntime(model_name=settings.planner_model)
```

- [ ] **Step 5: Add runtime selector tests**

Create `tests/test_planner_runtime.py`:

```python
import unittest
from unittest.mock import patch


class PlannerRuntimeTests(unittest.TestCase):
    def test_selector_returns_deterministic_runtime_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            from backend.config import get_settings
            from backend.services.planner_runtime import get_planner_runtime

            get_settings.cache_clear()
            runtime = get_planner_runtime()
            self.assertEqual(runtime.__class__.__name__, "DeterministicPlannerRuntime")
            get_settings.cache_clear()
```

- [ ] **Step 6: Run planner model/runtime tests to verify they pass**

Run:

```bash
python -m unittest tests.test_planner_models tests.test_planner_runtime -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/services/planner_models.py backend/services/planner_runtime_deterministic.py backend/services/planner_runtime.py backend/models/agent.py tests/test_planner_models.py tests/test_planner_runtime.py
git commit -m "feat: add planner models and deterministic runtime"
```

### Task 4: Add LangChain OpenAI runtime and minimal LangGraph graph

**Files:**
- Create: `backend/services/planner_runtime_openai.py`
- Create: `backend/services/planner_graph.py`
- Test: `tests/test_planner_graph.py`
- Test: `tests/test_planner_runtime.py`

- [ ] **Step 1: Write the failing graph test**

Create `tests/test_planner_graph.py`:

```python
import unittest


class PlannerGraphTests(unittest.TestCase):
    def test_build_plan_graph_returns_initial_plan_state(self):
        from backend.services.planner_graph import run_initial_planning

        state = run_initial_planning(
            session_id="session-1",
            brief="给 Notion AI 做一个 30 秒产品视频",
        )

        self.assertEqual(state["status"], "planning_complete")
        self.assertIn("agentPlan", state)
        self.assertIn("executionPlan", state)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_planner_graph -v
```

Expected: FAIL because planner graph does not exist.

- [ ] **Step 3: Add OpenAI runtime shell**

Create `backend/services/planner_runtime_openai.py`:

```python
from langchain_openai import ChatOpenAI

from backend.services.planner_models import AgentPlan, ExecutionPlan


class OpenAIPlannerRuntime:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.llm = ChatOpenAI(model=model_name, temperature=0)

    def build_plan_from_brief(self, brief: str) -> tuple[AgentPlan, ExecutionPlan]:
        raise NotImplementedError("OpenAI planner runtime is enabled in later tasks of the rollout")
```

- [ ] **Step 4: Add minimal LangGraph graph runner**

Create `backend/services/planner_graph.py`:

```python
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.services.planner_runtime import get_planner_runtime


class PlanningState(TypedDict, total=False):
    sessionId: str
    brief: str
    status: str
    agentPlan: dict
    executionPlan: dict


def _build_plan_node(state: PlanningState) -> PlanningState:
    runtime = get_planner_runtime()
    agent_plan, execution_plan = runtime.build_plan_from_brief(state["brief"])
    return {
        **state,
        "status": "planning_complete",
        "agentPlan": agent_plan.model_dump(mode="json"),
        "executionPlan": execution_plan.model_dump(mode="json"),
    }


def build_planning_graph():
    graph = StateGraph(PlanningState)
    graph.add_node("build_plan", _build_plan_node)
    graph.add_edge(START, "build_plan")
    graph.add_edge("build_plan", END)
    return graph.compile()


def run_initial_planning(session_id: str, brief: str) -> PlanningState:
    graph = build_planning_graph()
    return graph.invoke({"sessionId": session_id, "brief": brief})
```

- [ ] **Step 5: Run graph/runtime tests to verify they pass**

Run:

```bash
python -m unittest tests.test_planner_runtime tests.test_planner_graph -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/planner_runtime_openai.py backend/services/planner_graph.py tests/test_planner_graph.py tests/test_planner_runtime.py
git commit -m "feat: add minimal planner graph runtime"
```

### Task 5: Project planner output into session persistence and read models

**Files:**
- Create: `backend/services/planner_projection.py`
- Modify: `backend/models/agent.py`
- Modify: `backend/services/agent_read_service.py`
- Test: `tests/test_planner_models.py`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Write the failing integration expectation for create-session plan readiness**

Add a new test in `tests/test_agent_backend.py`:

```python
def test_create_session_api_returns_model_driven_initial_plan(self):
    from backend.main import app

    client = _make_test_client(app)
    response = client.post(
        "/api/agent/sessions",
        json={"message": "给 Notion AI 做一个 30 秒产品亮点视频"},
    )

    self.assertEqual(response.status_code, 200)
    data = response.json()
    self.assertEqual(data["status"], "plan_ready")
    self.assertIsNotNone(data["plan"])
    self.assertGreater(len(data["plan"]["scenes"]), 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_agent_backend.AgentApiTests.test_create_session_api_returns_model_driven_initial_plan -v
```

Expected: FAIL because current create-session returns grounding-first/no plan.

- [ ] **Step 3: Add planner projection helper**

Create `backend/services/planner_projection.py`:

```python
from backend.models.agent import EditPlan, PlanScene
from backend.services.planner_models import ExecutionPlan


def execution_plan_to_edit_plan(plan: ExecutionPlan) -> EditPlan:
    return EditPlan(
        title=plan.title,
        targetDuration=plan.targetDuration,
        style=plan.style,
        scenes=[
            PlanScene(
                id=scene.id,
                description=scene.description,
                keywords=scene.keywords,
                duration=scene.duration,
                searchQuery=scene.searchQuery,
            )
            for scene in plan.scenes
        ],
    )
```

- [ ] **Step 4: Extend read models for new persisted metadata**

Update `backend/models/agent.py` to allow future planner metadata in `AgentSession` safely:

```python
class AgentSession(BaseModel):
    ...
    plannerTrace: Dict[str, Any] | None = None
```

Update `backend/services/agent_read_service.py` to read:

```python
            plannerTrace=session_record.planner_trace_json or {},
```

- [ ] **Step 5: Run updated tests**

Run:

```bash
python -m unittest tests.test_planner_models tests.test_agent_backend.AgentApiTests.test_create_session_api_returns_model_driven_initial_plan -v
```

Expected: the API test still FAILS until Task 6 wires session creation; planner model tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/services/planner_projection.py backend/models/agent.py backend/services/agent_read_service.py tests/test_planner_models.py tests/test_agent_backend.py
git commit -m "feat: add planner projection and session metadata"
```

### Task 6: Wire `create_session` to the planner graph

**Files:**
- Create: `backend/services/planner_orchestrator.py`
- Modify: `backend/services/agent_session_service.py`
- Modify: `backend/db/repositories/agent_sessions.py`
- Modify: `backend/db/repositories/agent_plans.py`
- Modify: `backend/services/grounding_service.py`
- Test: `tests/test_agent_backend.py`
- Test: `tests/test_agent_persistence.py`
- Test: `tests/test_agent_planner_phase1.py`

- [ ] **Step 1: Write the failing phase-1 integration test for plan + observation persistence**

Create `tests/test_agent_planner_phase1.py`:

```python
import unittest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.base import Base
from backend.db.repositories import AgentObservationRepository, AgentPlanRepository, AgentSessionRepository
from backend.services.agent_session_service import AgentSessionService


class AgentPlannerPhase1Tests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def test_create_session_persists_initial_plan_and_observation(self):
        service = AgentSessionService(session_factory=self.session_factory)

        session = service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")

        self.assertEqual(session.status.value, "plan_ready")
        self.assertIsNotNone(session.plan)

        with self.session_factory() as db:
            session_record = AgentSessionRepository(db).get(session.id)
            plan_record = AgentPlanRepository(db).get_latest_for_session(session.id)
            observations = AgentObservationRepository(db).list_for_session(session.id)

            self.assertIsNotNone(session_record.current_plan_id)
            self.assertEqual(session_record.current_plan_id, plan_record.id)
            self.assertEqual(plan_record.version, 1)
            self.assertEqual(plan_record.trigger_type, "initial_brief")
            self.assertEqual(len(observations), 1)
            self.assertEqual(observations[0].observation_type, "user_message")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_agent_planner_phase1 -v
```

Expected: FAIL because planner orchestration and observation persistence are not wired.

- [ ] **Step 3: Create planner orchestrator**

Create `backend/services/planner_orchestrator.py`:

```python
from datetime import datetime, timezone
from uuid import uuid4

from backend.db.repositories import AgentObservationRepository, AgentPlanRepository
from backend.services.planner_graph import run_initial_planning


class PlannerOrchestrator:
    def persist_initial_plan(self, db, session_record, message_record):
        state = run_initial_planning(session_record.id, message_record.content)
        observation_repo = AgentObservationRepository(db)
        plan_repo = AgentPlanRepository(db)

        observation_repo.create(
            session_id=session_record.id,
            observation_type="user_message",
            summary="初始 brief",
            payload_json={"message": message_record.content},
            source_message_id=message_record.id,
        )

        plan_record = plan_repo.create(
            session_id=session_record.id,
            version=1,
            parent_plan_id=None,
            trigger_type="initial_brief",
            planner_mode="deterministic",
            planner_model="gpt-4o-mini",
            title=state["executionPlan"]["title"],
            target_duration=int(state["executionPlan"]["targetDuration"]),
            style=state["executionPlan"]["style"],
            plan_json=state["agentPlan"],
            execution_plan_json=state["executionPlan"],
            change_summary="根据初始 brief 生成第一版计划",
            status="ready",
        )

        session_record.current_plan_id = plan_record.id
        session_record.planner_trace_json = {
            "lastPlanningState": state["status"],
            "plannedAt": datetime.now(timezone.utc).isoformat(),
        }
        return plan_record
```

- [ ] **Step 4: Wire session creation**

Update `backend/services/agent_session_service.py` `create_session()` so that when `prompt` is present it:

```python
                    message_record = message_repo.create(session_id=session_id, role="user", content=prompt)
                    planner_orchestrator = PlannerOrchestrator()
                    plan_record = planner_orchestrator.persist_initial_plan(
                        db=db,
                        session_record=session_record,
                        message_record=message_record,
                    )
                    plan = EditPlan.model_validate(plan_record.execution_plan_json)
                    self._apply_plan_to_session(session_record, plan)
                    self._append_plan_ready_message(message_repo, session_id)
```

Do not call `grounding_service.build_grounding_summary()` in this phase-1 path.

Update `backend/db/repositories/agent_sessions.py` with a helper:

```python
    def set_current_plan(self, session_id: str, plan_id: str | None) -> AgentSessionRecord | None:
        record = self.get(session_id)
        if record is None:
            return None
        record.current_plan_id = plan_id
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record
```

- [ ] **Step 5: Keep grounding service as compatibility fallback**

Do not remove `grounding_service` behavior. Leave it in place for later phases and non-phase-1 paths, but stop using it inside initial `create_session()` when the prompt is present.

- [ ] **Step 6: Run focused tests**

Run:

```bash
python -m unittest \
  tests.test_planner_models \
  tests.test_planner_runtime \
  tests.test_planner_graph \
  tests.test_agent_planner_phase1 \
  tests.test_agent_backend.AgentApiTests.test_create_session_api_returns_model_driven_initial_plan \
  tests.test_agent_backend.AgentApiTests.test_add_message_updates_existing_session \
  -v
```

Expected: PASS

- [ ] **Step 7: Run broader regression tests**

Run:

```bash
python -m unittest \
  tests.test_agent_backend \
  tests.test_agent_persistence \
  -v
```

Expected: PASS, or clearly identify any now-invalid tests that still assert the old grounding-first create-session behavior and update them in this task before proceeding.

- [ ] **Step 8: Commit**

```bash
git add backend/services/planner_orchestrator.py backend/services/agent_session_service.py backend/db/repositories/agent_sessions.py backend/db/repositories/agent_plans.py backend/services/grounding_service.py tests/test_agent_backend.py tests/test_agent_persistence.py tests/test_agent_planner_phase1.py
git commit -m "feat: wire create session through planner graph"
```

## Self-Review

- Spec coverage:
  - Covers Phase 0 dependency/config work.
  - Covers plan version + observation persistence.
  - Covers LangChain/LangGraph minimal runtime/graph.
  - Covers Phase 1 `build_plan_from_brief` session creation path.
  - Intentionally defers grounding-triggered replan, user revision replan, and execution-feedback replan to later plans.
- Placeholder scan:
  - No TBD/TODO placeholders remain.
  - Each task lists exact files, tests, commands, and target code snippets.
- Type consistency:
  - `AgentPlan`, `ExecutionPlan`, `AgentObservation`, `PlannerOrchestrator`, and `run_initial_planning()` are referenced consistently.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-08-model-driven-agent-plan-phase0-1.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

# Agent Runtime Architecture Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor ClipForge toward an Agent Runtime architecture foundation so future RAG, Skill, and MCP capabilities have clear module boundaries before those capabilities are introduced.

**Architecture:** Keep current user-facing behavior unchanged while creating backend layer boundaries for API routes, application use cases, runtime orchestration, domain contracts, infrastructure adapters, and workers. The first phase should move code through compatibility shims and focused imports rather than a large rewrite, preserving existing endpoints and tests while making the next RAG/Skill/MCP stages straightforward.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy, Celery, Redis, PostgreSQL, LangGraph, LangChain, Next.js, TypeScript, unittest, existing `scripts/check-product-pages.mjs` verification.

---

## File Structure

### New backend structure

- Create `backend/app/__init__.py`
  - Application layer package marker.
- Create `backend/app/agent/__init__.py`
  - Session and read use case package marker.
- Create `backend/app/agent/session_use_cases.py`
  - Exports the current session and read services from stable application-layer names.
- Create `backend/app/execution/__init__.py`
  - Execution use case package marker.
- Create `backend/app/execution/job_use_cases.py`
  - Exports the current execution and task-read services from stable application-layer names.
- Create `backend/app/planning/__init__.py`
  - Planning use case package marker.
- Create `backend/app/planning/orchestrator.py`
  - Exports the current planner orchestrator from the application planning boundary.
- Create `backend/runtime/__init__.py`
  - Runtime package marker. This directory already exists for local config files, so keep runtime data files intact and add Python modules next to them.
- Create `backend/runtime/agent_runtime.py`
  - Thin orchestration facade for session creation, user messages, grounding confirmation, and execution confirmation.
- Create `backend/runtime/context_engine.py`
  - Minimal no-op context engine contract for the future RAG stage.
- Create `backend/runtime/skill_engine.py`
  - Minimal built-in skill engine contract for the future Skill stage.
- Create `backend/runtime/tool_gateway.py`
  - Minimal tool gateway contract for the future MCP stage.
- Create `backend/runtime/trace_recorder.py`
  - Minimal trace recorder contract that can be backed by current observations and events later.
- Create `backend/domain/__init__.py`
  - Domain layer package marker.
- Create `backend/domain/agent/__init__.py`
  - Agent domain package marker.
- Create `backend/domain/agent/contracts.py`
  - Re-exports current API-facing agent models until a later domain/schema split.
- Create `backend/domain/planning/__init__.py`
  - Planning domain package marker.
- Create `backend/domain/planning/contracts.py`
  - Re-exports current planner models until a later domain/schema split.
- Create `backend/infrastructure/__init__.py`
  - Infrastructure package marker.
- Create `backend/infrastructure/config/__init__.py`
  - Configuration infrastructure package marker.
- Create `backend/infrastructure/config/runtime_config_service.py`
  - Re-exports current runtime config service.
- Create `backend/infrastructure/media/__init__.py`
  - Media infrastructure package marker.
- Create `backend/infrastructure/media/render_service.py`
  - Re-exports current render service.
- Create `backend/infrastructure/media/asset_providers/__init__.py`
  - Re-exports current asset provider package.
- Create `backend/workers/__init__.py`
  - Worker package marker.
- Create `backend/workers/celery_app.py`
  - Re-exports current Celery app.
- Create `backend/workers/tasks/__init__.py`
  - Worker task package marker.
- Create `backend/workers/tasks/agent_job.py`
  - Re-exports current agent job task.
- Create `tests/test_agent_runtime_architecture.py`
  - Static and import contract tests for the new architecture boundary.

### Existing files to modify in this phase

- Modify `backend/api/agent.py`
  - Import session, read, execution, and task-read services from the new `backend.app.*` boundary.
- Modify `backend/tasks/celery_app.py`
  - Include both the legacy task module and the new worker task module during the transition.
- Modify `backend/tasks/agent_tasks.py`
  - Keep behavior unchanged. Add no architectural logic here in phase 1.
- Modify `README.md`
  - Add a short architecture note explaining the new layer boundaries and where RAG/Skill/MCP will land.

### Explicit non-goals

- Do not add a vector database in this phase.
- Do not add MCP clients or servers in this phase.
- Do not add a full skill registry in this phase.
- Do not change API response shapes in this phase.
- Do not change Celery queue names or task names in this phase.
- Do not move database tables or Alembic migrations in this phase.
- Do not redesign frontend screens in this phase.

---

## Target Architecture Map

```text
backend/api/
  FastAPI routes and request/response translation

backend/app/
  Application use cases for agent sessions, planning, execution, knowledge, skills, and tools

backend/runtime/
  Agent orchestration layer: context engine, skill engine, planner runtime, tool gateway, trace recorder

backend/domain/
  Stable business contracts and policies independent of FastAPI, Celery, and external providers

backend/infrastructure/
  Adapters for database, LLM, vector stores, MCP clients, media providers, FFmpeg, and runtime config

backend/workers/
  Celery app and task entrypoints for long-running execution
```

## Migration Principle

The first phase uses compatibility modules. New imports should point to the target architecture, while old modules remain in place so existing tests, task names, and runtime behavior keep working. Deleting legacy modules is a later cleanup phase after all imports have moved and verification is stable.

---

### Task 1: Add Architecture Boundary Contract Tests

**Files:**
- Create: `tests/test_agent_runtime_architecture.py`

- [ ] **Step 1: Create failing tests for target packages**

Create `tests/test_agent_runtime_architecture.py` with:

```python
from __future__ import annotations

import importlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AgentRuntimeArchitectureTests(unittest.TestCase):
    def test_target_architecture_packages_exist(self) -> None:
        expected_paths = [
            "backend/app/__init__.py",
            "backend/app/agent/__init__.py",
            "backend/app/execution/__init__.py",
            "backend/app/planning/__init__.py",
            "backend/runtime/__init__.py",
            "backend/runtime/agent_runtime.py",
            "backend/runtime/context_engine.py",
            "backend/runtime/skill_engine.py",
            "backend/runtime/tool_gateway.py",
            "backend/runtime/trace_recorder.py",
            "backend/domain/__init__.py",
            "backend/domain/agent/__init__.py",
            "backend/domain/planning/__init__.py",
            "backend/infrastructure/__init__.py",
            "backend/infrastructure/config/__init__.py",
            "backend/infrastructure/media/__init__.py",
            "backend/workers/__init__.py",
            "backend/workers/tasks/__init__.py",
        ]

        for relative_path in expected_paths:
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)
```

- [ ] **Step 2: Add failing import boundary tests**

Append to `tests/test_agent_runtime_architecture.py`:

```python
    def test_application_boundary_reexports_existing_use_cases(self) -> None:
        session_use_cases = importlib.import_module("backend.app.agent.session_use_cases")
        job_use_cases = importlib.import_module("backend.app.execution.job_use_cases")
        planning_orchestrator = importlib.import_module("backend.app.planning.orchestrator")

        self.assertTrue(hasattr(session_use_cases, "AgentSessionService"))
        self.assertTrue(hasattr(session_use_cases, "AgentReadService"))
        self.assertTrue(hasattr(job_use_cases, "AgentExecutionService"))
        self.assertTrue(hasattr(job_use_cases, "AgentTaskReadService"))
        self.assertTrue(hasattr(planning_orchestrator, "PlannerOrchestrator"))

    def test_runtime_contracts_import_without_side_effects(self) -> None:
        context_engine = importlib.import_module("backend.runtime.context_engine")
        skill_engine = importlib.import_module("backend.runtime.skill_engine")
        tool_gateway = importlib.import_module("backend.runtime.tool_gateway")
        trace_recorder = importlib.import_module("backend.runtime.trace_recorder")
        agent_runtime = importlib.import_module("backend.runtime.agent_runtime")

        self.assertTrue(hasattr(context_engine, "ContextEngine"))
        self.assertTrue(hasattr(skill_engine, "SkillEngine"))
        self.assertTrue(hasattr(tool_gateway, "ToolGateway"))
        self.assertTrue(hasattr(trace_recorder, "TraceRecorder"))
        self.assertTrue(hasattr(agent_runtime, "AgentRuntime"))
```

- [ ] **Step 3: Add failing worker and infrastructure boundary tests**

Append to `tests/test_agent_runtime_architecture.py`:

```python
    def test_infrastructure_and_worker_boundaries_reexport_existing_adapters(self) -> None:
        runtime_config = importlib.import_module("backend.infrastructure.config.runtime_config_service")
        render_service = importlib.import_module("backend.infrastructure.media.render_service")
        celery_app = importlib.import_module("backend.workers.celery_app")
        agent_job = importlib.import_module("backend.workers.tasks.agent_job")

        self.assertTrue(hasattr(runtime_config, "runtime_config_service"))
        self.assertTrue(hasattr(render_service, "render_video"))
        self.assertTrue(hasattr(celery_app, "celery_app"))
        self.assertTrue(hasattr(agent_job, "run_agent_job"))
```

- [ ] **Step 4: Run the new tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_runtime_architecture -v
```

Expected: `FAIL` because the new architecture packages and modules do not exist yet.

- [ ] **Step 5: Commit the architecture contract test**

Run:

```bash
git add tests/test_agent_runtime_architecture.py
git commit -m "test: lock agent runtime architecture boundary"
```

---

### Task 2: Create Application Layer Compatibility Modules

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/agent/__init__.py`
- Create: `backend/app/agent/session_use_cases.py`
- Create: `backend/app/execution/__init__.py`
- Create: `backend/app/execution/job_use_cases.py`
- Create: `backend/app/planning/__init__.py`
- Create: `backend/app/planning/orchestrator.py`

- [ ] **Step 1: Create application package markers**

Create these empty package marker files:

```text
backend/app/__init__.py
backend/app/agent/__init__.py
backend/app/execution/__init__.py
backend/app/planning/__init__.py
```

- [ ] **Step 2: Create session use case compatibility module**

Create `backend/app/agent/session_use_cases.py` with:

```python
from backend.services.agent_read_service import AgentReadService
from backend.services.agent_session_service import AgentSessionService


__all__ = [
    "AgentReadService",
    "AgentSessionService",
]
```

- [ ] **Step 3: Create execution use case compatibility module**

Create `backend/app/execution/job_use_cases.py` with:

```python
from backend.services.agent_execution_service import AgentExecutionService
from backend.services.agent_task_read_service import AgentTaskReadService


__all__ = [
    "AgentExecutionService",
    "AgentTaskReadService",
]
```

- [ ] **Step 4: Create planning orchestrator compatibility module**

Create `backend/app/planning/orchestrator.py` with:

```python
from backend.services.planner_orchestrator import PlannerOrchestrator


__all__ = ["PlannerOrchestrator"]
```

- [ ] **Step 5: Run focused application boundary tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture.AgentRuntimeArchitectureTests.test_application_boundary_reexports_existing_use_cases -v
```

Expected: `OK`.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app tests/test_agent_runtime_architecture.py
git commit -m "refactor: add application layer compatibility modules"
```

---

### Task 3: Create Runtime Contracts For RAG, Skill, MCP, And Trace

**Files:**
- Create: `backend/runtime/__init__.py`
- Create: `backend/runtime/context_engine.py`
- Create: `backend/runtime/skill_engine.py`
- Create: `backend/runtime/tool_gateway.py`
- Create: `backend/runtime/trace_recorder.py`

- [ ] **Step 1: Create runtime package marker**

Create `backend/runtime/__init__.py` with:

```python
"""Agent runtime package for orchestration, context, skills, tools, and trace."""
```

- [ ] **Step 2: Create context engine contract**

Create `backend/runtime/context_engine.py` with:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextRequest:
    session_id: str
    message: str
    plan_version: int | None = None
    scope: str = "planning"


@dataclass(frozen=True)
class ContextBundle:
    documents: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0


class ContextEngine:
    def build_context(self, request: ContextRequest) -> ContextBundle:
        return ContextBundle()
```

- [ ] **Step 3: Create skill engine contract**

Create `backend/runtime/skill_engine.py` with:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillSelectionRequest:
    session_id: str
    user_message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillSelection:
    skill_id: str
    version: str
    reason: str = ""


class SkillEngine:
    def select_skill(self, request: SkillSelectionRequest) -> SkillSelection:
        return SkillSelection(
            skill_id="builtin.product_intro_video",
            version="0.1.0",
            reason="Default ClipForge video generation skill",
        )
```

- [ ] **Step 4: Create tool gateway contract**

Create `backend/runtime/tool_gateway.py` with:

```python
from dataclasses import dataclass, field
from typing import Any, Literal


ToolCallStatus = Literal["succeeded", "failed", "skipped"]


@dataclass(frozen=True)
class ToolCallRequest:
    session_id: str
    tool_id: str
    arguments: dict[str, Any] = field(default_factory=dict)
    permission_scope: str = "session"


@dataclass(frozen=True)
class ToolCallResult:
    status: ToolCallStatus
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class ToolGateway:
    def call_tool(self, request: ToolCallRequest) -> ToolCallResult:
        return ToolCallResult(
            status="skipped",
            error=f"Tool is not registered: {request.tool_id}",
        )
```

- [ ] **Step 5: Create trace recorder contract**

Create `backend/runtime/trace_recorder.py` with:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TraceEvent:
    session_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


class TraceRecorder:
    def record(self, event: TraceEvent) -> None:
        return None
```

- [ ] **Step 6: Run focused runtime boundary tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture.AgentRuntimeArchitectureTests.test_runtime_contracts_import_without_side_effects -v
```

Expected: `OK`.

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/runtime tests/test_agent_runtime_architecture.py
git commit -m "refactor: add agent runtime contracts"
```

---

### Task 4: Add AgentRuntime Facade Without Changing Behavior

**Files:**
- Create: `backend/runtime/agent_runtime.py`
- Modify: `tests/test_agent_runtime_architecture.py`

- [ ] **Step 1: Add a behavior test for AgentRuntime constructor shape**

Append this test to `AgentRuntimeArchitectureTests`:

```python
    def test_agent_runtime_accepts_existing_services(self) -> None:
        from backend.runtime.agent_runtime import AgentRuntime
        from backend.runtime.context_engine import ContextEngine
        from backend.runtime.skill_engine import SkillEngine
        from backend.runtime.tool_gateway import ToolGateway
        from backend.runtime.trace_recorder import TraceRecorder

        runtime = AgentRuntime(
            session_service=object(),
            execution_service=object(),
            context_engine=ContextEngine(),
            skill_engine=SkillEngine(),
            tool_gateway=ToolGateway(),
            trace_recorder=TraceRecorder(),
        )

        self.assertIsNotNone(runtime)
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture.AgentRuntimeArchitectureTests.test_agent_runtime_accepts_existing_services -v
```

Expected: `FAIL` because `AgentRuntime` does not yet exist.

- [ ] **Step 3: Create AgentRuntime facade**

Create `backend/runtime/agent_runtime.py` with:

```python
from dataclasses import dataclass
from typing import Any

from backend.runtime.context_engine import ContextEngine
from backend.runtime.skill_engine import SkillEngine
from backend.runtime.tool_gateway import ToolGateway
from backend.runtime.trace_recorder import TraceRecorder


@dataclass
class AgentRuntime:
    session_service: Any
    execution_service: Any
    context_engine: ContextEngine
    skill_engine: SkillEngine
    tool_gateway: ToolGateway
    trace_recorder: TraceRecorder

    def create_session(self, message: str | None = None):
        return self.session_service.create_session(message)

    def submit_message(self, session_id: str, message: str):
        return self.session_service.add_user_message(session_id, message)

    def confirm_grounding(self, session_id: str, candidate_ids: list[str]):
        return self.session_service.confirm_grounding_candidates(session_id, candidate_ids)

    def confirm_plan(self, session_id: str):
        return self.execution_service.confirm_session(session_id)
```

- [ ] **Step 4: Run runtime tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_runtime_architecture -v
```

Expected: `OK` for all tests in `tests.test_agent_runtime_architecture`.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/runtime/agent_runtime.py tests/test_agent_runtime_architecture.py
git commit -m "refactor: add agent runtime facade"
```

---

### Task 5: Create Infrastructure And Worker Compatibility Boundaries

**Files:**
- Create: `backend/infrastructure/__init__.py`
- Create: `backend/infrastructure/config/__init__.py`
- Create: `backend/infrastructure/config/runtime_config_service.py`
- Create: `backend/infrastructure/media/__init__.py`
- Create: `backend/infrastructure/media/render_service.py`
- Create: `backend/infrastructure/media/asset_providers/__init__.py`
- Create: `backend/workers/__init__.py`
- Create: `backend/workers/celery_app.py`
- Create: `backend/workers/tasks/__init__.py`
- Create: `backend/workers/tasks/agent_job.py`

- [ ] **Step 1: Create infrastructure package markers**

Create:

```text
backend/infrastructure/__init__.py
backend/infrastructure/config/__init__.py
backend/infrastructure/media/__init__.py
backend/infrastructure/media/asset_providers/__init__.py
```

- [ ] **Step 2: Re-export runtime config service**

Create `backend/infrastructure/config/runtime_config_service.py` with:

```python
from backend.services.runtime_config_service import (
    DEFAULT_ASSET_PROVIDER_ORDER,
    DEFAULT_DATABASE_URL,
    DEFAULT_FIXTURE_LIBRARY_PATH,
    DEFAULT_REDIS_URL,
    FIELD_DEFINITIONS,
    KNOWN_ASSET_PROVIDERS,
    RuntimeConfigService,
    RuntimeField,
    runtime_config_service,
)


__all__ = [
    "DEFAULT_ASSET_PROVIDER_ORDER",
    "DEFAULT_DATABASE_URL",
    "DEFAULT_FIXTURE_LIBRARY_PATH",
    "DEFAULT_REDIS_URL",
    "FIELD_DEFINITIONS",
    "KNOWN_ASSET_PROVIDERS",
    "RuntimeConfigService",
    "RuntimeField",
    "runtime_config_service",
]
```

- [ ] **Step 3: Re-export render service**

Create `backend/infrastructure/media/render_service.py` with:

```python
from backend.services.render_service import (
    OUTPUT_FPS,
    VERTICAL_HEIGHT,
    VERTICAL_WIDTH,
    build_render_commands,
    build_render_inputs,
    check_ffmpeg,
    render_shortform_video,
    render_video,
)


__all__ = [
    "OUTPUT_FPS",
    "VERTICAL_HEIGHT",
    "VERTICAL_WIDTH",
    "build_render_commands",
    "build_render_inputs",
    "check_ffmpeg",
    "render_shortform_video",
    "render_video",
]
```

- [ ] **Step 4: Re-export current asset provider package entrypoints**

Create `backend/infrastructure/media/asset_providers/__init__.py` with:

```python
from backend.services.asset_providers.types import AssetCandidate, AssetDownload


__all__ = [
    "AssetCandidate",
    "AssetDownload",
]
```

- [ ] **Step 5: Create worker compatibility modules**

Create `backend/workers/__init__.py` with:

```python
"""Worker entrypoints for ClipForge background execution."""
```

Create `backend/workers/celery_app.py` with:

```python
from backend.tasks.celery_app import celery_app


__all__ = ["celery_app"]
```

Create `backend/workers/tasks/__init__.py` with:

```python
"""Celery task modules exposed through the target worker package."""
```

Create `backend/workers/tasks/agent_job.py` with:

```python
from backend.tasks.agent_tasks import dispatch_agent_job, run_agent_job


__all__ = [
    "dispatch_agent_job",
    "run_agent_job",
]
```

- [ ] **Step 6: Run focused infrastructure and worker boundary tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture.AgentRuntimeArchitectureTests.test_infrastructure_and_worker_boundaries_reexport_existing_adapters -v
```

Expected: `OK`.

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/infrastructure backend/workers tests/test_agent_runtime_architecture.py
git commit -m "refactor: add infrastructure and worker boundaries"
```

---

### Task 6: Move API Imports To The Application Boundary

**Files:**
- Modify: `backend/api/agent.py`
- Test: `tests/test_agent_backend.py`
- Test: `tests/test_agent_runtime_architecture.py`

- [ ] **Step 1: Update API imports**

In `backend/api/agent.py`, replace:

```python
from backend.services.agent_execution_service import AgentExecutionService
from backend.services.agent_read_service import AgentReadService
from backend.services.agent_session_service import AgentSessionService
from backend.services.agent_task_read_service import AgentTaskReadService
```

with:

```python
from backend.app.agent.session_use_cases import AgentReadService, AgentSessionService
from backend.app.execution.job_use_cases import AgentExecutionService, AgentTaskReadService
```

- [ ] **Step 2: Add source contract test for API import direction**

Append this test to `AgentRuntimeArchitectureTests`:

```python
    def test_agent_api_imports_use_application_boundary(self) -> None:
        source = (ROOT / "backend" / "api" / "agent.py").read_text(encoding="utf-8")

        self.assertIn("from backend.app.agent.session_use_cases import AgentReadService, AgentSessionService", source)
        self.assertIn("from backend.app.execution.job_use_cases import AgentExecutionService, AgentTaskReadService", source)
        self.assertNotIn("from backend.services.agent_execution_service import", source)
        self.assertNotIn("from backend.services.agent_session_service import", source)
```

- [ ] **Step 3: Run API and architecture tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture \
  tests.test_agent_backend.AgentApiTests -v
```

Expected: `OK`.

- [ ] **Step 4: Commit**

Run:

```bash
git add backend/api/agent.py tests/test_agent_runtime_architecture.py
git commit -m "refactor: route agent api through application boundary"
```

---

### Task 7: Document The Target Architecture In README

**Files:**
- Modify: `README.md`
- Test: `tests/test_agent_runtime_architecture.py`

- [ ] **Step 1: Add README contract test**

Append this test to `AgentRuntimeArchitectureTests`:

```python
    def test_readme_documents_agent_runtime_architecture(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Agent Runtime 架构", readme)
        self.assertIn("Context Engine", readme)
        self.assertIn("Skill Engine", readme)
        self.assertIn("Tool Gateway", readme)
        self.assertIn("RAG", readme)
        self.assertIn("MCP", readme)
```

- [ ] **Step 2: Run the README contract test and verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture.AgentRuntimeArchitectureTests.test_readme_documents_agent_runtime_architecture -v
```

Expected: `FAIL` because README does not yet document the target architecture.

- [ ] **Step 3: Add architecture section to README**

Add this section after the existing technology stack section in `README.md`:

```markdown
## Agent Runtime 架构方向

ClipForge 的下一阶段架构目标是从“视频生成服务集合”演进为“面向视频生成的 Agent Runtime”。现有 API、规划、任务执行、素材搜索和渲染能力会逐步收敛到清晰分层：

- `backend/api/`：FastAPI 路由，只负责 HTTP 请求、响应和错误翻译。
- `backend/app/`：应用用例层，负责会话、规划、执行、知识库、Skill 和工具调用的业务编排。
- `backend/runtime/`：Agent Runtime 层，承载 Context Engine、Skill Engine、Tool Gateway、Trace Recorder 和 Planner Runtime。
- `backend/domain/`：稳定领域模型、状态和策略。
- `backend/infrastructure/`：数据库、LLM、Vector Store、MCP、素材 Provider、FFmpeg 和运行时配置等外部适配。
- `backend/workers/`：Celery 后台任务入口。

后续 RAG 会接入 `Context Engine` 和知识库用例；Skill 会接入 `Skill Engine` 和可注册 Skill 包；MCP 会通过 `Tool Gateway` 统一调用、鉴权、审计和错误归一化。这样可以避免把检索、技能选择和工具调用继续堆进 planner 或 worker。
```

- [ ] **Step 4: Run README contract test**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture.AgentRuntimeArchitectureTests.test_readme_documents_agent_runtime_architecture -v
```

Expected: `OK`.

- [ ] **Step 5: Commit**

Run:

```bash
git add README.md tests/test_agent_runtime_architecture.py
git commit -m "docs: document agent runtime architecture direction"
```

---

### Task 8: Full Verification And Handoff

**Files:**
- Verify all changed files from Tasks 1-7.

- [ ] **Step 1: Run backend unit tests most likely to catch import regressions**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture \
  tests.test_agent_backend \
  tests.test_agent_jobs \
  tests.test_agent_persistence -v
```

Expected: `OK`.

- [ ] **Step 2: Run planner tests to catch runtime import drift**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m pytest \
  tests/test_planner_graph.py \
  tests/test_planner_runtime.py \
  tests/test_agent_planner_phase1.py \
  tests/test_agent_planner_phase2.py \
  tests/test_agent_planner_phase3.py \
  tests/test_agent_planner_phase4.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run frontend build**

Run:

```bash
npm run build
```

Expected: Next.js production build succeeds.

- [ ] **Step 4: Run product page check**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: product page checks pass.

- [ ] **Step 5: Inspect changed files**

Run:

```bash
git status --short
git diff --stat
```

Expected: changed files are limited to architecture packages, import rewiring, tests, and README documentation from this plan.

- [ ] **Step 6: Commit verification note if any test fixture updates were needed**

If no additional fixture updates were needed, skip this step. If test fixture updates were required by actual import behavior, commit only those focused files:

```bash
git add <focused-files>
git commit -m "test: update architecture boundary verification"
```

---

## Later Phases Not Covered By This Plan

### Phase 2: RAG Foundation

- Add `backend/app/knowledge/`.
- Add `backend/domain/knowledge/`.
- Add `backend/infrastructure/vector/`.
- Add knowledge source, document, chunk, and context usage persistence.
- Extend `ContextEngine` from no-op to retrieval-backed context assembly.

### Phase 3: Skill Foundation

- Add `backend/skills/builtin/product_intro_video/`.
- Add `backend/skills/builtin/asset_search_repair/`.
- Add a real skill registry and selection policy.
- Persist skill runs and skill outputs.

### Phase 4: MCP Foundation

- Add `backend/infrastructure/mcp/`.
- Add MCP server registry and client adapter.
- Extend `ToolGateway` from skipped calls to permissioned MCP calls.
- Persist tool calls, tool results, latency, and errors.

## Self-Review

- Spec coverage: This plan covers the requested next-stage architecture planning and only writes documentation for future implementation.
- Scope check: The plan is limited to the first architecture foundation phase and explicitly defers RAG, Skill, and MCP implementation to later phases.
- Placeholder scan: The plan defines concrete files, tests, commands, expected outcomes, and commit points without unresolved sections.
- Type consistency: Runtime contract class names are stable across tests and implementation steps: `ContextEngine`, `SkillEngine`, `ToolGateway`, `TraceRecorder`, and `AgentRuntime`.

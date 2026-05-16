# Agent Runtime 架构基础实施计划

> **给 agentic workers：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步执行本计划。每一步使用 checkbox（`- [ ]`）追踪状态。

**目标：** 将 ClipForge 重构到 Agent Runtime 架构基础形态，让后续 RAG、Skill、MCP 能力在引入前就拥有清晰的模块边界。

**架构：** 本阶段保持现有用户行为不变，只建立后端分层边界：API 路由、应用用例、Agent Runtime、领域契约、基础设施适配器和 Worker。第一阶段通过兼容模块和聚焦的 import 迁移完成，不做大规模重写，确保现有接口、任务名和测试稳定，同时为下一阶段接入 RAG/Skill/MCP 打好位置。

**技术栈：** FastAPI、Pydantic v2、SQLAlchemy、Celery、Redis、PostgreSQL、LangGraph、LangChain、Next.js、TypeScript、unittest、现有 `scripts/check-product-pages.mjs` 验证脚本。

---

## 文件结构

### 新增后端结构

- 创建 `backend/app/__init__.py`
  - 应用层包标记。
- 创建 `backend/app/agent/__init__.py`
  - 会话与读取用例包标记。
- 创建 `backend/app/agent/session_use_cases.py`
  - 从稳定应用层名称导出现有 session/read services。
- 创建 `backend/app/execution/__init__.py`
  - 执行用例包标记。
- 创建 `backend/app/execution/job_use_cases.py`
  - 从稳定应用层名称导出现有 execution/task-read services。
- 创建 `backend/app/planning/__init__.py`
  - 规划用例包标记。
- 创建 `backend/app/planning/orchestrator.py`
  - 从应用规划边界导出现有 planner orchestrator。
- 创建 `backend/runtime/__init__.py`
  - Runtime 包标记。该目录当前已有本地配置文件，保留 runtime 数据文件，在旁边增加 Python 模块。
- 创建 `backend/runtime/agent_runtime.py`
  - 会话创建、用户消息、grounding 确认和执行确认的薄编排 facade。
- 创建 `backend/runtime/context_engine.py`
  - 面向未来 RAG 阶段的最小 no-op context engine 契约。
- 创建 `backend/runtime/skill_engine.py`
  - 面向未来 Skill 阶段的最小 built-in skill engine 契约。
- 创建 `backend/runtime/tool_gateway.py`
  - 面向未来 MCP 阶段的最小 tool gateway 契约。
- 创建 `backend/runtime/trace_recorder.py`
  - 最小 trace recorder 契约，后续可接入当前 observations 和 events。
- 创建 `backend/domain/__init__.py`
  - 领域层包标记。
- 创建 `backend/domain/agent/__init__.py`
  - Agent 领域包标记。
- 创建 `backend/domain/agent/contracts.py`
  - 在后续拆分 domain/schema 前，先重新导出现有 API-facing agent models。
- 创建 `backend/domain/planning/__init__.py`
  - Planning 领域包标记。
- 创建 `backend/domain/planning/contracts.py`
  - 在后续拆分 domain/schema 前，先重新导出现有 planner models。
- 创建 `backend/infrastructure/__init__.py`
  - 基础设施层包标记。
- 创建 `backend/infrastructure/config/__init__.py`
  - 配置基础设施包标记。
- 创建 `backend/infrastructure/config/runtime_config_service.py`
  - 重新导出现有 runtime config service。
- 创建 `backend/infrastructure/media/__init__.py`
  - 媒体基础设施包标记。
- 创建 `backend/infrastructure/media/render_service.py`
  - 重新导出现有 render service。
- 创建 `backend/infrastructure/media/asset_providers/__init__.py`
  - 重新导出现有 asset provider 包。
- 创建 `backend/workers/__init__.py`
  - Worker 包标记。
- 创建 `backend/workers/celery_app.py`
  - 重新导出现有 Celery app。
- 创建 `backend/workers/tasks/__init__.py`
  - Worker task 包标记。
- 创建 `backend/workers/tasks/agent_job.py`
  - 重新导出现有 agent job task。
- 创建 `tests/test_agent_runtime_architecture.py`
  - 新架构边界的静态和 import 契约测试。

### 本阶段修改的现有文件

- 修改 `backend/api/agent.py`
  - 从新的 `backend.app.*` 边界导入 session、read、execution、task-read services。
- 修改 `backend/tasks/celery_app.py`
  - 过渡期同时 include legacy task module 和新的 worker task module。
- 修改 `backend/tasks/agent_tasks.py`
  - 保持行为不变。本阶段不在这里增加架构逻辑。
- 修改 `README.md`
  - 增加一小节架构说明，解释新层级边界，以及 RAG/Skill/MCP 后续落点。

### 明确不做

- 本阶段不增加 vector database。
- 本阶段不增加 MCP client 或 MCP server。
- 本阶段不增加完整 skill registry。
- 本阶段不改变 API response shape。
- 本阶段不改变 Celery queue name 或 task name。
- 本阶段不迁移数据库表或 Alembic migration。
- 本阶段不重设计前端页面。

---

## 目标架构图

```text
backend/api/
  FastAPI routes 和 request/response translation

backend/app/
  agent sessions、planning、execution、knowledge、skills、tools 的应用用例

backend/runtime/
  Agent orchestration layer: context engine, skill engine, planner runtime, tool gateway, trace recorder

backend/domain/
  与 FastAPI、Celery、外部 provider 无关的稳定业务契约和策略

backend/infrastructure/
  database、LLM、vector store、MCP client、media provider、FFmpeg、runtime config 等适配器

backend/workers/
  长耗时执行的 Celery app 和 task entrypoints
```

## 迁移原则

第一阶段使用兼容模块。新增 import 应该指向目标架构，但旧模块保留在原位置，确保现有测试、Celery task name 和运行时行为继续稳定。删除 legacy modules 是后续清理阶段的工作，必须等所有 import 都迁移完成并通过验证后再做。

---

### Task 1: 增加架构边界契约测试

**Files:**
- Create: `tests/test_agent_runtime_architecture.py`

- [ ] **Step 1: 为目标 package 写失败测试**

创建 `tests/test_agent_runtime_architecture.py`：

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

- [ ] **Step 2: 增加 application boundary import 测试**

继续追加到 `tests/test_agent_runtime_architecture.py`：

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

- [ ] **Step 3: 增加 worker 和 infrastructure boundary 测试**

继续追加到 `tests/test_agent_runtime_architecture.py`：

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

- [ ] **Step 4: 运行新测试并确认失败**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_runtime_architecture -v
```

Expected: `FAIL`，因为新架构 package 和 module 还不存在。

- [ ] **Step 5: 提交架构契约测试**

Run:

```bash
git add tests/test_agent_runtime_architecture.py
git commit -m "test: lock agent runtime architecture boundary"
```

---

### Task 2: 创建 Application Layer 兼容模块

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/agent/__init__.py`
- Create: `backend/app/agent/session_use_cases.py`
- Create: `backend/app/execution/__init__.py`
- Create: `backend/app/execution/job_use_cases.py`
- Create: `backend/app/planning/__init__.py`
- Create: `backend/app/planning/orchestrator.py`

- [ ] **Step 1: 创建 application package marker**

创建这些空 package marker 文件：

```text
backend/app/__init__.py
backend/app/agent/__init__.py
backend/app/execution/__init__.py
backend/app/planning/__init__.py
```

- [ ] **Step 2: 创建 session use case 兼容模块**

创建 `backend/app/agent/session_use_cases.py`：

```python
from backend.services.agent_read_service import AgentReadService
from backend.services.agent_session_service import AgentSessionService


__all__ = [
    "AgentReadService",
    "AgentSessionService",
]
```

- [ ] **Step 3: 创建 execution use case 兼容模块**

创建 `backend/app/execution/job_use_cases.py`：

```python
from backend.services.agent_execution_service import AgentExecutionService
from backend.services.agent_task_read_service import AgentTaskReadService


__all__ = [
    "AgentExecutionService",
    "AgentTaskReadService",
]
```

- [ ] **Step 4: 创建 planning orchestrator 兼容模块**

创建 `backend/app/planning/orchestrator.py`：

```python
from backend.services.planner_orchestrator import PlannerOrchestrator


__all__ = ["PlannerOrchestrator"]
```

- [ ] **Step 5: 运行 application boundary 聚焦测试**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture.AgentRuntimeArchitectureTests.test_application_boundary_reexports_existing_use_cases -v
```

Expected: `OK`。

- [ ] **Step 6: 提交**

Run:

```bash
git add backend/app tests/test_agent_runtime_architecture.py
git commit -m "refactor: add application layer compatibility modules"
```

---

### Task 3: 创建 RAG、Skill、MCP、Trace 的 Runtime 契约

**Files:**
- Create: `backend/runtime/__init__.py`
- Create: `backend/runtime/context_engine.py`
- Create: `backend/runtime/skill_engine.py`
- Create: `backend/runtime/tool_gateway.py`
- Create: `backend/runtime/trace_recorder.py`

- [ ] **Step 1: 创建 runtime package marker**

创建 `backend/runtime/__init__.py`：

```python
"""Agent runtime package for orchestration, context, skills, tools, and trace."""
```

- [ ] **Step 2: 创建 context engine 契约**

创建 `backend/runtime/context_engine.py`：

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

- [ ] **Step 3: 创建 skill engine 契约**

创建 `backend/runtime/skill_engine.py`：

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

- [ ] **Step 4: 创建 tool gateway 契约**

创建 `backend/runtime/tool_gateway.py`：

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

- [ ] **Step 5: 创建 trace recorder 契约**

创建 `backend/runtime/trace_recorder.py`：

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

- [ ] **Step 6: 运行 runtime boundary 聚焦测试**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture.AgentRuntimeArchitectureTests.test_runtime_contracts_import_without_side_effects -v
```

Expected: `OK`。

- [ ] **Step 7: 提交**

Run:

```bash
git add backend/runtime tests/test_agent_runtime_architecture.py
git commit -m "refactor: add agent runtime contracts"
```

---

### Task 4: 增加 AgentRuntime Facade 且不改变行为

**Files:**
- Create: `backend/runtime/agent_runtime.py`
- Modify: `tests/test_agent_runtime_architecture.py`

- [ ] **Step 1: 增加 AgentRuntime 构造形状测试**

追加到 `AgentRuntimeArchitectureTests`：

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

- [ ] **Step 2: 运行新测试并确认失败**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture.AgentRuntimeArchitectureTests.test_agent_runtime_accepts_existing_services -v
```

Expected: `FAIL`，因为 `AgentRuntime` 还不存在。

- [ ] **Step 3: 创建 AgentRuntime facade**

创建 `backend/runtime/agent_runtime.py`：

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

- [ ] **Step 4: 运行 runtime 测试**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_runtime_architecture -v
```

Expected: `OK`。

- [ ] **Step 5: 提交**

Run:

```bash
git add backend/runtime/agent_runtime.py tests/test_agent_runtime_architecture.py
git commit -m "refactor: add agent runtime facade"
```

---

### Task 5: 创建 Infrastructure 和 Worker 兼容边界

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

- [ ] **Step 1: 创建 infrastructure package marker**

创建：

```text
backend/infrastructure/__init__.py
backend/infrastructure/config/__init__.py
backend/infrastructure/media/__init__.py
backend/infrastructure/media/asset_providers/__init__.py
```

- [ ] **Step 2: 重新导出 runtime config service**

创建 `backend/infrastructure/config/runtime_config_service.py`：

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

- [ ] **Step 3: 重新导出 render service**

创建 `backend/infrastructure/media/render_service.py`：

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

- [ ] **Step 4: 重新导出现有 asset provider package entrypoints**

创建 `backend/infrastructure/media/asset_providers/__init__.py`：

```python
from backend.services.asset_providers.types import AssetCandidate, AssetDownload


__all__ = [
    "AssetCandidate",
    "AssetDownload",
]
```

- [ ] **Step 5: 创建 worker 兼容模块**

创建 `backend/workers/__init__.py`：

```python
"""Worker entrypoints for ClipForge background execution."""
```

创建 `backend/workers/celery_app.py`：

```python
from backend.tasks.celery_app import celery_app


__all__ = ["celery_app"]
```

创建 `backend/workers/tasks/__init__.py`：

```python
"""Celery task modules exposed through the target worker package."""
```

创建 `backend/workers/tasks/agent_job.py`：

```python
from backend.tasks.agent_tasks import dispatch_agent_job, run_agent_job


__all__ = [
    "dispatch_agent_job",
    "run_agent_job",
]
```

- [ ] **Step 6: 运行 infrastructure 和 worker boundary 聚焦测试**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture.AgentRuntimeArchitectureTests.test_infrastructure_and_worker_boundaries_reexport_existing_adapters -v
```

Expected: `OK`。

- [ ] **Step 7: 提交**

Run:

```bash
git add backend/infrastructure backend/workers tests/test_agent_runtime_architecture.py
git commit -m "refactor: add infrastructure and worker boundaries"
```

---

### Task 6: 将 API Import 迁到 Application Boundary

**Files:**
- Modify: `backend/api/agent.py`
- Test: `tests/test_agent_backend.py`
- Test: `tests/test_agent_runtime_architecture.py`

- [ ] **Step 1: 更新 API imports**

在 `backend/api/agent.py` 中，把：

```python
from backend.services.agent_execution_service import AgentExecutionService
from backend.services.agent_read_service import AgentReadService
from backend.services.agent_session_service import AgentSessionService
from backend.services.agent_task_read_service import AgentTaskReadService
```

替换成：

```python
from backend.app.agent.session_use_cases import AgentReadService, AgentSessionService
from backend.app.execution.job_use_cases import AgentExecutionService, AgentTaskReadService
```

- [ ] **Step 2: 增加 API import direction 源码契约测试**

追加这个测试到 `AgentRuntimeArchitectureTests`：

```python
    def test_agent_api_imports_use_application_boundary(self) -> None:
        source = (ROOT / "backend" / "api" / "agent.py").read_text(encoding="utf-8")

        self.assertIn("from backend.app.agent.session_use_cases import AgentReadService, AgentSessionService", source)
        self.assertIn("from backend.app.execution.job_use_cases import AgentExecutionService, AgentTaskReadService", source)
        self.assertNotIn("from backend.services.agent_execution_service import", source)
        self.assertNotIn("from backend.services.agent_session_service import", source)
```

- [ ] **Step 3: 运行 API 和架构测试**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture \
  tests.test_agent_backend.AgentApiTests -v
```

Expected: `OK`。

- [ ] **Step 4: 提交**

Run:

```bash
git add backend/api/agent.py tests/test_agent_runtime_architecture.py
git commit -m "refactor: route agent api through application boundary"
```

---

### Task 7: 在 README 记录目标架构

**Files:**
- Modify: `README.md`
- Test: `tests/test_agent_runtime_architecture.py`

- [ ] **Step 1: 增加 README 契约测试**

追加这个测试到 `AgentRuntimeArchitectureTests`：

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

- [ ] **Step 2: 运行 README 契约测试并确认失败**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture.AgentRuntimeArchitectureTests.test_readme_documents_agent_runtime_architecture -v
```

Expected: `FAIL`，因为 README 还没有记录目标架构。

- [ ] **Step 3: 给 README 增加架构章节**

在 `README.md` 的技术栈章节后增加：

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

- [ ] **Step 4: 运行 README 契约测试**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture.AgentRuntimeArchitectureTests.test_readme_documents_agent_runtime_architecture -v
```

Expected: `OK`。

- [ ] **Step 5: 提交**

Run:

```bash
git add README.md tests/test_agent_runtime_architecture.py
git commit -m "docs: document agent runtime architecture direction"
```

---

### Task 8: 完整验证和交接

**Files:**
- 验证 Task 1-7 中所有变更文件。

- [ ] **Step 1: 运行最容易捕获 import regression 的后端单元测试**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_runtime_architecture \
  tests.test_agent_backend \
  tests.test_agent_jobs \
  tests.test_agent_persistence -v
```

Expected: `OK`。

- [ ] **Step 2: 运行 planner tests 捕获 runtime import drift**

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

Expected: 选中的测试全部通过。

- [ ] **Step 3: 运行前端 build**

Run:

```bash
npm run build
```

Expected: Next.js production build 成功。

- [ ] **Step 4: 运行 product page check**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: product page checks 通过。

- [ ] **Step 5: 检查变更文件**

Run:

```bash
git status --short
git diff --stat
```

Expected: 变更文件仅限本计划内的架构 package、import rewiring、测试和 README 文档。

- [ ] **Step 6: 必要时提交验证补充**

如果不需要额外 fixture 更新，跳过本步骤。如果实际 import 行为需要测试 fixture 更新，只提交聚焦文件：

```bash
git add <focused-files>
git commit -m "test: update architecture boundary verification"
```

---

## 本计划不覆盖的后续阶段

### Phase 2: RAG Foundation

- 增加 `backend/app/knowledge/`。
- 增加 `backend/domain/knowledge/`。
- 增加 `backend/infrastructure/vector/`。
- 增加 knowledge source、document、chunk、context usage 持久化。
- 将 `ContextEngine` 从 no-op 扩展为 retrieval-backed context assembly。

### Phase 3: Skill Foundation

- 增加 `backend/skills/builtin/product_intro_video/`。
- 增加 `backend/skills/builtin/asset_search_repair/`。
- 增加真实 skill registry 和 selection policy。
- 持久化 skill runs 和 skill outputs。

### Phase 4: MCP Foundation

- 增加 `backend/infrastructure/mcp/`。
- 增加 MCP server registry 和 client adapter。
- 将 `ToolGateway` 从 skipped calls 扩展为 permissioned MCP calls。
- 持久化 tool calls、tool results、latency 和 errors。

## 自检

- Spec coverage：本计划覆盖“下一阶段架构规划，并且只写文档”的需求。
- Scope check：计划聚焦第一阶段架构基础，RAG、Skill、MCP 的真实实现明确延后到后续阶段。
- Placeholder scan：计划包含具体文件、测试、命令、预期结果和提交点，没有未解析占位段落。
- Type consistency：Runtime 契约类名在测试和实现步骤中保持一致：`ContextEngine`、`SkillEngine`、`ToolGateway`、`TraceRecorder`、`AgentRuntime`。

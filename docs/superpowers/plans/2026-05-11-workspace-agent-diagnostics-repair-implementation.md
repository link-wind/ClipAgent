# Workspace Agent Diagnostics And Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stable agent diagnostic read model, expose it on failed sessions/tasks, and let `/workspace` turn a diagnosis into a user-controlled repair prompt.

**Architecture:** Introduce `AgentDiagnostic` as a small API model and build it in a focused `AgentDiagnosticService` from existing failure events, job/session errors, and structured worker payloads. Wire that read model into `AgentReadService` and `AgentTaskReadService`, then update frontend types and the existing `/workspace` and task-detail failure panels without adding automatic retry.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy, unittest, Next.js, TypeScript, Tailwind CSS

---

## File Structure

### Create

- `backend/services/agent_diagnostic_service.py`
  - Owns all diagnostic normalization, category mapping, phase mapping, and repair prompt generation.

### Modify

- `backend/models/agent.py`
  - Adds `AgentDiagnostic` and `AgentDiagnosticSeverity`.
  - Adds optional `diagnostic` fields to `AgentSession` and `AgentTaskDetail`.
- `backend/services/agent_read_service.py`
  - Uses `AgentDiagnosticService` to attach diagnostics to failed sessions.
- `backend/services/agent_task_read_service.py`
  - Uses `AgentDiagnosticService` to attach diagnostics to failed task details.
- `src/lib/agentApi.ts`
  - Adds frontend `AgentDiagnostic` types and `AgentSession.diagnostic`.
- `src/lib/taskApi.ts`
  - Adds `AgentTaskDetail.diagnostic`.
- `src/components/workspace/BriefWorkspacePage.tsx`
  - Shows the diagnosis panel and fills the composer with `diagnostic.repairPrompt`.
  - Shows the execution-feedback requeue note when the event timeline includes `job_requeued_after_replan`.
- `src/components/tasks/TaskManagerPage.tsx`
  - Shows minimal diagnostic title/message in task detail.
  - Keeps retry disabled.
- `tests/test_agent_backend.py`
  - Adds frontend source contract tests for diagnosis UI and repair prompt behavior.
- `tests/test_agent_jobs.py`
  - Adds diagnostic service behavior tests.
- `tests/test_agent_persistence.py`
  - Adds session/task read-service diagnostic integration tests.

## Task 1: Add Backend Diagnostic Models

**Files:**
- Modify: `backend/models/agent.py`
- Modify: `tests/test_agent_persistence.py`

- [ ] **Step 1: Write the failing model contract test**

Add this assertion block to `SessionServiceBehaviorTests.test_agent_session_schema_includes_events_and_active_job_id` in `tests/test_agent_persistence.py`:

```python
        from backend.models.agent import AgentDiagnostic

        self.assertIn("diagnostic", AgentSession.model_fields)
        self.assertIsNone(AgentSession.model_fields["diagnostic"].default)
        self.assertIn("phase", AgentDiagnostic.model_fields)
        self.assertIn("category", AgentDiagnostic.model_fields)
        self.assertIn("repairPrompt", AgentDiagnostic.model_fields)
```

Add this new test to `SessionServiceBehaviorTests`:

```python
    def test_agent_diagnostic_schema_defaults(self):
        from backend.models.agent import AgentDiagnostic

        diagnostic = AgentDiagnostic(
            phase="search_assets",
            category="no_inventory",
            title="素材搜索没有找到可用结果",
            message="YouTube 没有返回可下载候选素材。",
        )

        self.assertEqual(diagnostic.phase, "search_assets")
        self.assertEqual(diagnostic.category, "no_inventory")
        self.assertEqual(diagnostic.primaryProvider, None)
        self.assertEqual(diagnostic.failedSceneIds, [])
        self.assertEqual(diagnostic.providerDiagnostics, [])
        self.assertEqual(diagnostic.sceneDiagnostics, [])
        self.assertEqual(diagnostic.retryStrategyHint, None)
        self.assertEqual(diagnostic.repairPrompt, "")
        self.assertEqual(diagnostic.severity, "error")
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_agent_session_schema_includes_events_and_active_job_id \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_agent_diagnostic_schema_defaults -v
```

Expected: FAIL because `AgentDiagnostic` and `diagnostic` fields do not exist.

- [ ] **Step 3: Add the Pydantic models and response fields**

In `backend/models/agent.py`, add these type aliases after `GroundingStatus`:

```python
AgentDiagnosticSeverity = Literal["info", "warning", "error"]
AgentDiagnosticPhase = Literal["planning", "search_assets", "prepare_assets", "render_video", "unknown"]
AgentDiagnosticCategory = Literal[
    "no_inventory",
    "provider_blocked",
    "download_failed",
    "render_failed",
    "planning_failed",
    "unknown",
]
```

Add this model after `AgentEvent`:

```python
class AgentDiagnostic(BaseModel):
    phase: AgentDiagnosticPhase
    category: AgentDiagnosticCategory
    title: str
    message: str
    primaryProvider: Optional[str] = None
    failedSceneIds: List[int] = Field(default_factory=list)
    providerDiagnostics: List[Dict[str, Any]] = Field(default_factory=list)
    sceneDiagnostics: List[Dict[str, Any]] = Field(default_factory=list)
    retryStrategyHint: Optional[str] = None
    repairPrompt: str = ""
    severity: AgentDiagnosticSeverity = "error"
```

Add the optional field to `AgentSession`:

```python
    diagnostic: Optional[AgentDiagnostic] = None
```

Add the optional field to `AgentTaskDetail`:

```python
    diagnostic: Optional[AgentDiagnostic] = None
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_agent_session_schema_includes_events_and_active_job_id \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_agent_diagnostic_schema_defaults -v
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add backend/models/agent.py tests/test_agent_persistence.py
git commit -m "feat: add agent diagnostic response model"
```

## Task 2: Build The Diagnostic Normalization Service

**Files:**
- Create: `backend/services/agent_diagnostic_service.py`
- Modify: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write failing diagnostic service tests**

Add these tests to `AgentExecutionWorkerTests` in `tests/test_agent_jobs.py`:

```python
    def test_agent_diagnostic_service_builds_search_no_inventory_diagnostic(self):
        from types import SimpleNamespace

        from backend.services.agent_diagnostic_service import AgentDiagnosticService

        event_rows = [
            SimpleNamespace(
                event_type="job_failed",
                step="failed",
                message="没有下载到可用素材",
                payload_json={
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
                    "retryableStep": "searching",
                },
            )
        ]
        job_record = SimpleNamespace(error_message="没有下载到可用素材", current_step="处理失败：没有下载到可用素材")
        session_record = SimpleNamespace(error_message="没有下载到可用素材", error_retryable_step="searching")

        diagnostic = AgentDiagnosticService().build_diagnostic(
            session_record=session_record,
            job_record=job_record,
            event_rows=event_rows,
        )

        self.assertIsNotNone(diagnostic)
        self.assertEqual(diagnostic.phase, "search_assets")
        self.assertEqual(diagnostic.category, "no_inventory")
        self.assertEqual(diagnostic.title, "素材搜索没有找到可用结果")
        self.assertEqual(diagnostic.primaryProvider, "youtube")
        self.assertEqual(diagnostic.failedSceneIds, [1])
        self.assertEqual(diagnostic.retryStrategyHint, "inventory_broaden")
        self.assertIn("场景 1", diagnostic.message)
        self.assertIn("YouTube", diagnostic.message)
        self.assertIn("请根据这次失败调整方案", diagnostic.repairPrompt)
        self.assertIn("场景 1", diagnostic.repairPrompt)

    def test_agent_diagnostic_service_falls_back_from_plain_job_error(self):
        from types import SimpleNamespace

        from backend.services.agent_diagnostic_service import AgentDiagnosticService

        diagnostic = AgentDiagnosticService().build_diagnostic(
            session_record=None,
            job_record=SimpleNamespace(error_message="mocked missing render dependency", current_step="处理失败：mocked missing render dependency"),
            event_rows=[],
        )

        self.assertIsNotNone(diagnostic)
        self.assertEqual(diagnostic.phase, "unknown")
        self.assertEqual(diagnostic.category, "unknown")
        self.assertEqual(diagnostic.title, "任务执行失败")
        self.assertEqual(diagnostic.message, "mocked missing render dependency")
        self.assertEqual(diagnostic.repairPrompt, "请根据这次失败调整方案：mocked missing render dependency。请保持原始目标不变，改写为更容易执行的方案。")
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_jobs.AgentExecutionWorkerTests.test_agent_diagnostic_service_builds_search_no_inventory_diagnostic \
  tests.test_agent_jobs.AgentExecutionWorkerTests.test_agent_diagnostic_service_falls_back_from_plain_job_error -v
```

Expected: FAIL because `backend.services.agent_diagnostic_service` does not exist.

- [ ] **Step 3: Create the diagnostic service**

Create `backend/services/agent_diagnostic_service.py` with this implementation:

```python
from typing import Any

from backend.models.agent import AgentDiagnostic


STEP_TO_PHASE = {
    "planning": "planning",
    "finalize_plan": "planning",
    "searching": "search_assets",
    "search_assets": "search_assets",
    "downloading": "prepare_assets",
    "prepare_assets": "prepare_assets",
    "rendering": "render_video",
    "render_video": "render_video",
}

SUPPORTED_CATEGORIES = {
    "no_inventory",
    "provider_blocked",
    "download_failed",
    "render_failed",
    "planning_failed",
    "unknown",
}

PROVIDER_LABELS = {
    "pexels": "Pexels",
    "youtube": "YouTube",
}


class AgentDiagnosticService:
    def build_diagnostic(self, *, session_record=None, job_record=None, event_rows=None) -> AgentDiagnostic | None:
        payload = self._latest_failure_payload(event_rows or [])
        message = self._resolve_message(payload, session_record, job_record)
        if not message:
            return None

        phase = self._resolve_phase(payload, session_record, job_record)
        category = self._resolve_category(payload, phase, message)
        failed_scene_ids = self._normalize_scene_ids(payload.get("failedSceneIds"))
        primary_provider = self._normalize_optional_string(payload.get("primaryProvider"))
        provider_diagnostics = self._normalize_record_list(payload.get("providerDiagnostics"))
        scene_diagnostics = self._normalize_record_list(payload.get("sceneDiagnostics"))
        retry_strategy_hint = self._normalize_optional_string(payload.get("retryStrategyHint"))

        return AgentDiagnostic(
            phase=phase,
            category=category,
            title=self._build_title(category, phase),
            message=self._build_message(
                raw_message=message,
                primary_provider=primary_provider,
                failed_scene_ids=failed_scene_ids,
            ),
            primaryProvider=primary_provider,
            failedSceneIds=failed_scene_ids,
            providerDiagnostics=provider_diagnostics,
            sceneDiagnostics=scene_diagnostics,
            retryStrategyHint=retry_strategy_hint,
            repairPrompt=self._build_repair_prompt(
                message=message,
                phase=phase,
                category=category,
                primary_provider=primary_provider,
                failed_scene_ids=failed_scene_ids,
            ),
            severity="error",
        )

    def _latest_failure_payload(self, event_rows) -> dict[str, Any]:
        for row in reversed(list(event_rows)):
            if getattr(row, "event_type", "") != "job_failed":
                continue
            payload = getattr(row, "payload_json", None) or {}
            if isinstance(payload, dict):
                return payload
        return {}

    def _resolve_message(self, payload: dict[str, Any], session_record, job_record) -> str:
        for value in (
            payload.get("failureReason"),
            payload.get("message"),
            getattr(job_record, "error_message", None),
            getattr(session_record, "error_message", None),
        ):
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _resolve_phase(self, payload: dict[str, Any], session_record, job_record) -> str:
        for value in (
            payload.get("retryableStep"),
            getattr(session_record, "error_retryable_step", None),
            getattr(job_record, "current_step", None),
        ):
            phase = self._phase_from_value(value)
            if phase != "unknown":
                return phase
        return "unknown"

    def _phase_from_value(self, value) -> str:
        if not isinstance(value, str):
            return "unknown"
        if value in STEP_TO_PHASE:
            return STEP_TO_PHASE[value]
        if "素材" in value or "搜索" in value:
            return "search_assets"
        if "渲染" in value or "合成" in value:
            return "render_video"
        return "unknown"

    def _resolve_category(self, payload: dict[str, Any], phase: str, message: str) -> str:
        category = payload.get("failureCategory")
        if isinstance(category, str) and category in SUPPORTED_CATEGORIES:
            return category

        lowered = message.lower()
        if any(token in lowered for token in ("403", "blocked", "rate limit", "unauthorized", "forbidden")):
            return "provider_blocked"
        if phase == "render_video":
            return "render_failed"
        if phase == "planning":
            return "planning_failed"
        return "unknown"

    def _build_title(self, category: str, phase: str) -> str:
        if category == "no_inventory":
            return "素材搜索没有找到可用结果"
        if category == "provider_blocked":
            return "外部素材源暂时不可用"
        if category == "download_failed":
            return "素材下载失败"
        if category == "render_failed":
            return "视频渲染失败"
        if category == "planning_failed":
            return "方案规划失败"
        if phase == "search_assets":
            return "素材搜索失败"
        return "任务执行失败"

    def _build_message(self, *, raw_message: str, primary_provider: str | None, failed_scene_ids: list[int]) -> str:
        parts: list[str] = []
        if primary_provider:
            parts.append(self._provider_label(primary_provider))
        if failed_scene_ids:
            parts.append(self._scene_label(failed_scene_ids))
        if parts:
            return f"{' / '.join(parts)}：{raw_message}"
        return raw_message

    def _build_repair_prompt(
        self,
        *,
        message: str,
        phase: str,
        category: str,
        primary_provider: str | None,
        failed_scene_ids: list[int],
    ) -> str:
        context_parts: list[str] = []
        if failed_scene_ids:
            context_parts.append(self._scene_label(failed_scene_ids))
        if primary_provider:
            context_parts.append(f"{self._provider_label(primary_provider)} 素材源")
        context = " / ".join(context_parts)
        prefix = f"{context}：{message}" if context else message

        if phase == "search_assets" or category in {"no_inventory", "provider_blocked"}:
            return f"请根据这次失败调整方案：{prefix}。请放宽检索关键词，优先选择更通用、容易找到真实素材的画面方向，并保持总时长不变。"
        if phase == "render_video":
            return f"请根据这次失败调整方案：{prefix}。请简化镜头结构，减少对特殊素材或复杂渲染的依赖，并保持总时长不变。"
        return f"请根据这次失败调整方案：{prefix}。请保持原始目标不变，改写为更容易执行的方案。"

    def _normalize_scene_ids(self, value) -> list[int]:
        if not isinstance(value, list):
            return []
        scene_ids: list[int] = []
        for item in value:
            if isinstance(item, int) and item not in scene_ids:
                scene_ids.append(item)
        return scene_ids

    def _normalize_record_list(self, value) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _normalize_optional_string(self, value) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _provider_label(self, provider: str) -> str:
        return PROVIDER_LABELS.get(provider.lower(), provider)

    def _scene_label(self, scene_ids: list[int]) -> str:
        return "、".join(f"场景 {scene_id}" for scene_id in scene_ids)
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_jobs.AgentExecutionWorkerTests.test_agent_diagnostic_service_builds_search_no_inventory_diagnostic \
  tests.test_agent_jobs.AgentExecutionWorkerTests.test_agent_diagnostic_service_falls_back_from_plain_job_error -v
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add backend/services/agent_diagnostic_service.py tests/test_agent_jobs.py
git commit -m "feat: normalize agent failure diagnostics"
```

## Task 3: Attach Diagnostics To Session And Task Responses

**Files:**
- Modify: `backend/services/agent_read_service.py`
- Modify: `backend/services/agent_task_read_service.py`
- Modify: `tests/test_agent_persistence.py`

- [ ] **Step 1: Write failing read-service integration tests**

Add this test to `SessionServiceBehaviorTests` in `tests/test_agent_persistence.py`:

```python
    def test_read_session_includes_diagnostic_for_failed_session(self):
        from backend.db.repositories import AgentEventRepository, AgentJobRepository, AgentSessionRepository
        from backend.services.agent_read_service import AgentReadService

        with self.SessionLocal() as db:
            session_repo = AgentSessionRepository(db)
            job_repo = AgentJobRepository(db)
            event_repo = AgentEventRepository(db)
            session_record = session_repo.create(
                status="failed",
                current_step="处理失败：没有下载到可用素材",
                progress=35,
                error_message="没有下载到可用素材",
                error_retryable_step="searching",
            )
            job_record = job_repo.create(
                session_id=session_record.id,
                job_type="generate_video",
                status="failed",
                progress=35,
                current_step="处理失败：没有下载到可用素材",
                error_message="没有下载到可用素材",
            )
            session_record.active_job_id = job_record.id
            event_repo.create(
                session_id=session_record.id,
                job_id=job_record.id,
                event_type="job_failed",
                step="failed",
                message="没有下载到可用素材",
                payload_json={
                    "failedSceneIds": [1],
                    "failureReason": "没有下载到可用素材",
                    "failureCategory": "no_inventory",
                    "primaryProvider": "youtube",
                    "retryableStep": "searching",
                },
            )
            session_id = session_record.id
            db.commit()

        session = AgentReadService(session_factory=self.SessionLocal).read_session(session_id)

        self.assertIsNotNone(session.diagnostic)
        self.assertEqual(session.diagnostic.phase, "search_assets")
        self.assertEqual(session.diagnostic.category, "no_inventory")
        self.assertEqual(session.diagnostic.primaryProvider, "youtube")
        self.assertEqual(session.diagnostic.failedSceneIds, [1])
```

Add this test to `SessionServiceBehaviorTests`:

```python
    def test_read_task_includes_diagnostic_for_failed_job(self):
        from backend.db.repositories import AgentEventRepository, AgentJobRepository, AgentSessionRepository
        from backend.services.agent_task_read_service import AgentTaskReadService

        with self.SessionLocal() as db:
            session_repo = AgentSessionRepository(db)
            job_repo = AgentJobRepository(db)
            event_repo = AgentEventRepository(db)
            session_record = session_repo.create(title="诊断测试", status="failed")
            job_record = job_repo.create(
                session_id=session_record.id,
                job_type="generate_video",
                status="failed",
                progress=35,
                current_step="处理失败：没有下载到可用素材",
                error_message="没有下载到可用素材",
            )
            event_repo.create(
                session_id=session_record.id,
                job_id=job_record.id,
                event_type="job_failed",
                step="failed",
                message="没有下载到可用素材",
                payload_json={
                    "failureReason": "没有下载到可用素材",
                    "failureCategory": "no_inventory",
                    "primaryProvider": "youtube",
                    "retryableStep": "searching",
                },
            )
            job_id = job_record.id
            db.commit()

        task = AgentTaskReadService(session_factory=self.SessionLocal).read_task(job_id)

        self.assertIsNotNone(task.diagnostic)
        self.assertEqual(task.diagnostic.phase, "search_assets")
        self.assertEqual(task.diagnostic.title, "素材搜索没有找到可用结果")
        self.assertIn("请根据这次失败调整方案", task.diagnostic.repairPrompt)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_read_session_includes_diagnostic_for_failed_session \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_read_task_includes_diagnostic_for_failed_job -v
```

Expected: FAIL because read services do not attach diagnostics yet.

- [ ] **Step 3: Attach diagnostics in `AgentReadService`**

In `backend/services/agent_read_service.py`, add the import:

```python
from backend.services.agent_diagnostic_service import AgentDiagnosticService
```

Also add `AgentJobRepository` to the existing repository import block:

```python
from backend.db.repositories import (
    AgentArtifactRepository,
    AgentEventRepository,
    AgentJobRepository,
    AgentMessageRepository,
    AgentPlanRepository,
    AgentSessionRepository,
)
```

In `AgentReadService.__init__`, add:

```python
        self.diagnostic_service = AgentDiagnosticService()
```

In `read_session(...)`, load the active job before `build_session_response(...)`:

```python
            artifact_rows = self.load_artifacts(db, session_id)
            event_rows = AgentEventRepository(db).list_for_session(session_id)
            active_job_record = None
            if getattr(session_record, "active_job_id", None):
                active_job_record = AgentJobRepository(db).get(session_record.active_job_id)

            return self.build_session_response(
                session_record=session_record,
                message_rows=message_repo.list_for_session(session_id),
                plan_row=self.load_current_plan(db, session_record),
                artifact_rows=artifact_rows,
                event_rows=event_rows,
                job_record=active_job_record,
            )
```

Update `build_session_response(...)` signature:

```python
    def build_session_response(self, session_record, message_rows, plan_row, artifact_rows, event_rows, job_record=None) -> AgentSession:
```

Add this field when constructing `AgentSession`:

```python
            diagnostic=self.diagnostic_service.build_diagnostic(
                session_record=session_record,
                job_record=job_record,
                event_rows=event_rows,
            ),
```

- [ ] **Step 4: Attach diagnostics in `AgentTaskReadService`**

In `backend/services/agent_task_read_service.py`, add:

```python
from backend.services.agent_diagnostic_service import AgentDiagnosticService
```

In `AgentTaskReadService.__init__`, add:

```python
        self.diagnostic_service = AgentDiagnosticService()
```

Add this field when constructing `AgentTaskDetail`:

```python
                diagnostic=self.diagnostic_service.build_diagnostic(
                    session_record=session,
                    job_record=job,
                    event_rows=events,
                ),
```

- [ ] **Step 5: Run focused integration tests and compatibility test**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_persistence.SessionServiceContractTests.test_agent_read_service_exposes_read_methods \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_read_session_includes_diagnostic_for_failed_session \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_read_task_includes_diagnostic_for_failed_job -v
```

Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add backend/services/agent_read_service.py backend/services/agent_task_read_service.py tests/test_agent_persistence.py
git commit -m "feat: expose diagnostics on agent reads"
```

## Task 4: Add Frontend Types And Workspace Repair Panel

**Files:**
- Modify: `src/lib/agentApi.ts`
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
- Modify: `tests/test_agent_backend.py`

- [ ] **Step 1: Write failing frontend contract test**

Add this test to `FrontendClientContractTests` in `tests/test_agent_backend.py`:

```python
    def test_workspace_failure_diagnostic_panel_and_repair_prompt_action(self):
        api_source = (ROOT / "src" / "lib" / "agentApi.ts").read_text(encoding="utf-8")
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("export interface AgentDiagnostic", api_source)
        self.assertIn("diagnostic: AgentDiagnostic | null", api_source)
        self.assertIn("const diagnostic = session?.diagnostic ?? null;", workspace_source)
        self.assertIn("function applyDiagnosticRepairPrompt()", workspace_source)
        self.assertIn("setMessage(diagnostic.repairPrompt);", workspace_source)
        self.assertIn("textareaRef.current?.focus();", workspace_source)
        self.assertIn("用建议修复方案继续修改", workspace_source)
        self.assertIn("diagnostic.primaryProvider", workspace_source)
        self.assertIn("diagnostic.failedSceneIds", workspace_source)
        self.assertIn("const isSessionActivelyExecuting = Boolean(", workspace_source)
        self.assertIn("const showFailurePanel = Boolean(", workspace_source)
        self.assertIn("{showFailurePanel ? (", workspace_source)
```

Add this test to `FrontendClientContractTests`:

```python
    def test_workspace_surfaces_execution_feedback_requeue_note(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("hasExecutionFeedbackRequeue", workspace_source)
        self.assertIn("job_requeued_after_replan", workspace_source)
        self.assertIn("已根据上一次失败自动调整方案并重新入队", workspace_source)
```

- [ ] **Step 2: Run frontend contract tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_failure_diagnostic_panel_and_repair_prompt_action \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_surfaces_execution_feedback_requeue_note -v
```

Expected: FAIL because frontend types and UI strings do not exist.

- [ ] **Step 3: Add frontend diagnostic types**

In `src/lib/agentApi.ts`, add after `AgentStep`:

```ts
export type AgentDiagnosticSeverity = 'info' | 'warning' | 'error'

export interface AgentDiagnostic {
  phase: 'planning' | 'search_assets' | 'prepare_assets' | 'render_video' | 'unknown'
  category: 'no_inventory' | 'provider_blocked' | 'download_failed' | 'render_failed' | 'planning_failed' | 'unknown'
  title: string
  message: string
  primaryProvider: string | null
  failedSceneIds: number[]
  providerDiagnostics: Record<string, unknown>[]
  sceneDiagnostics: Record<string, unknown>[]
  retryStrategyHint: string | null
  repairPrompt: string
  severity: AgentDiagnosticSeverity
}
```

In `AgentSession`, add:

```ts
  diagnostic: AgentDiagnostic | null
```

- [ ] **Step 4: Add workspace helpers**

In `src/components/workspace/BriefWorkspacePage.tsx`, after `getStepStatusText(...)`, add:

```tsx
function formatDiagnosticPhase(phase: string) {
  return (
    {
      planning: '方案规划',
      search_assets: '搜索素材',
      prepare_assets: '准备素材',
      render_video: '渲染视频',
      unknown: '未知阶段',
    }[phase] ?? phase
  );
}

function formatSceneIds(sceneIds: number[]) {
  return sceneIds.length ? sceneIds.map((sceneId) => `场景 ${sceneId}`).join('、') : '未指定';
}
```

Inside `BriefWorkspacePage`, after `const failedStep = findFailedStep(session);`, add:

```tsx
  const diagnostic = session?.diagnostic ?? null;
  const isSessionActivelyExecuting = Boolean(
    session?.status === 'queued' ||
      session?.status === 'searching' ||
      session?.status === 'downloading' ||
      session?.status === 'rendering'
  );
  const showFailurePanel = Boolean((session?.status === 'failed' || failedStep) && !isSessionActivelyExecuting);
  const hasExecutionFeedbackRequeue = Boolean(
    session?.events?.some((event) => event.eventType === 'job_requeued_after_replan')
  );
```

In the restored-session jump target, replace the failure target condition:

```tsx
      (showFailurePanel ? failureSectionRef.current : null) ||
```

Update the dependency list for that effect so it uses `showFailurePanel` instead of `failedStep` and `session?.error`:

```tsx
  }, [hasAppliedRestoreJump, restoredSessionId, resultUrl, session?.id, showExecutionHandoff, showFailurePanel]);
```

Add this function near `focusComposer`:

```tsx
  function applyDiagnosticRepairPrompt() {
    if (!diagnostic?.repairPrompt) {
      return;
    }
    setMessage(diagnostic.repairPrompt);
    textareaRef.current?.focus();
  }
```

- [ ] **Step 5: Render the requeue note**

Inside the execution handoff section, after the Job ID block, add:

```tsx
                {hasExecutionFeedbackRequeue ? (
                  <div className="rounded-lg border border-[rgba(168,198,108,0.38)] bg-[#f6faef] px-3 py-2 text-sm font-semibold text-accentink">
                    已根据上一次失败自动调整方案并重新入队
                  </div>
                ) : null}
```

- [ ] **Step 6: Render the diagnostic panel and repair action**

Change the failure section condition from `{session?.error || failedStep ? (` to `{showFailurePanel ? (`. Then replace the two plain failure paragraphs inside the failure section with this block, keeping the existing `<span>` and `<h2>`:

```tsx
                {diagnostic ? (
                  <div className="mt-3 grid gap-3">
                    <div className="rounded-lg border border-[#f5c2c7] bg-white/75 p-3">
                      <strong className="block text-sm text-[#641421]">{diagnostic.title}</strong>
                      <p className="mt-2 leading-6">{diagnostic.message}</p>
                      <div className="mt-3 grid gap-2 text-xs leading-5 sm:grid-cols-3">
                        <span>
                          <strong>阶段：</strong>
                          {formatDiagnosticPhase(diagnostic.phase)}
                        </span>
                        <span>
                          <strong>素材源：</strong>
                          {diagnostic.primaryProvider || '未指定'}
                        </span>
                        <span>
                          <strong>场景：</strong>
                          {formatSceneIds(diagnostic.failedSceneIds)}
                        </span>
                      </div>
                    </div>
                    {diagnostic.repairPrompt ? (
                      <button
                        type="button"
                        onClick={applyDiagnosticRepairPrompt}
                        className="inline-flex min-h-10 w-fit items-center justify-center rounded-lg bg-[#8b1f2d] px-4 text-sm font-semibold text-white transition hover:bg-[#721827]"
                      >
                        用建议修复方案继续修改
                      </button>
                    ) : null}
                  </div>
                ) : (
                  <>
                    <p className="mt-2 leading-6">
                      {failedStep?.error?.message || session?.error?.message || '任务执行失败，请查看任务详情。'}
                    </p>
                    <p className="mt-2 leading-6">
                      {failedStep?.error?.retryable || session?.error?.retryableStep
                        ? '该问题可能可以重试，请先在任务页查看事件时间线。'
                        : '请在任务页查看事件时间线和外部素材下载日志。'}
                    </p>
                  </>
                )}
```

- [ ] **Step 7: Run focused frontend contract tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_failure_diagnostic_panel_and_repair_prompt_action \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_surfaces_execution_feedback_requeue_note -v
```

Expected: OK.

- [ ] **Step 8: Commit**

```bash
git add src/lib/agentApi.ts src/components/workspace/BriefWorkspacePage.tsx tests/test_agent_backend.py
git commit -m "feat: show workspace failure diagnostics"
```

## Task 5: Add Task Detail Diagnostic Parity

**Files:**
- Modify: `src/lib/taskApi.ts`
- Modify: `src/components/tasks/TaskManagerPage.tsx`
- Modify: `tests/test_agent_backend.py`

- [ ] **Step 1: Write failing task detail contract test**

Add this test to `FrontendClientContractTests` in `tests/test_agent_backend.py`:

```python
    def test_task_detail_renders_minimal_diagnostic_without_retry_action(self):
        task_api_source = (ROOT / "src" / "lib" / "taskApi.ts").read_text(encoding="utf-8")
        task_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(encoding="utf-8")

        self.assertIn("AgentDiagnostic", task_api_source)
        self.assertIn("diagnostic: AgentDiagnostic | null", task_api_source)
        self.assertIn("activeTask.diagnostic", task_source)
        self.assertIn("诊断摘要", task_source)
        self.assertIn("activeTask.diagnostic.title", task_source)
        self.assertIn("activeTask.diagnostic.message", task_source)
        self.assertIn("任务级重新执行暂未开放", task_source)
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_task_detail_renders_minimal_diagnostic_without_retry_action -v
```

Expected: FAIL because task detail does not type or render diagnostics.

- [ ] **Step 3: Update task API types**

In `src/lib/taskApi.ts`, change the import to:

```ts
import type { AgentDiagnostic, AgentErrorInfo, AgentEvent, AgentStep, AgentStepId, ClipInfo } from './agentApi'
```

Add this field to `AgentTaskDetail`:

```ts
  diagnostic: AgentDiagnostic | null
```

- [ ] **Step 4: Render minimal task detail diagnostic**

In `src/components/tasks/TaskManagerPage.tsx`, inside the status summary section after the existing `错误信息` block, add:

```tsx
                  {activeTask.diagnostic ? (
                    <div className="mt-4 rounded-lg border border-rose-200 bg-white/85 p-4">
                      <span className="block text-xs font-semibold text-secondary">诊断摘要</span>
                      <strong className="mt-2 block text-sm font-semibold text-ink">
                        {activeTask.diagnostic.title}
                      </strong>
                      <p className="mt-2 text-sm leading-6 text-ink">{activeTask.diagnostic.message}</p>
                    </div>
                  ) : null}
```

- [ ] **Step 5: Run the focused test and verify it passes**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_task_detail_renders_minimal_diagnostic_without_retry_action -v
```

Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add src/lib/taskApi.ts src/components/tasks/TaskManagerPage.tsx tests/test_agent_backend.py
git commit -m "feat: show task failure diagnostics"
```

## Task 6: Final Verification

**Files:**
- Verify only

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_jobs.AgentExecutionWorkerTests.test_agent_diagnostic_service_builds_search_no_inventory_diagnostic \
  tests.test_agent_jobs.AgentExecutionWorkerTests.test_agent_diagnostic_service_falls_back_from_plain_job_error \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_read_session_includes_diagnostic_for_failed_session \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_read_task_includes_diagnostic_for_failed_job -v
```

Expected: OK.

- [ ] **Step 2: Run focused frontend contract tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_failure_diagnostic_panel_and_repair_prompt_action \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_surfaces_execution_feedback_requeue_note \
  tests.test_agent_backend.FrontendClientContractTests.test_task_detail_renders_minimal_diagnostic_without_retry_action -v
```

Expected: OK.

- [ ] **Step 3: Run broader backend regression tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend \
  tests.test_agent_jobs \
  tests.test_agent_persistence -v
```

Expected: OK.

- [ ] **Step 4: Run frontend build**

Run:

```bash
npm run build
```

Expected: `Compiled successfully` and `/workspace` route generated.

- [ ] **Step 5: Inspect final diff**

Run:

```bash
git status --short
git diff --stat master...HEAD
```

Expected: only files listed in this plan changed.

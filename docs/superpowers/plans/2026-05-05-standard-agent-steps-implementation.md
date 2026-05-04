# Standard Agent Steps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fixed standard `steps[]` contract so the backend returns real per-step status, progress, results, and errors for the frontend product workflow.

**Architecture:** Extend the existing FastAPI/Pydantic read models with `AgentStep` snapshots while preserving legacy fields such as `status`, `progress`, and `currentStep`. Add a dedicated backend `AgentStepSnapshotService` that aggregates session, plan, job, events, and artifacts into the fixed 8-step product flow. Update the Next.js frontend types and product pages to consume `steps[]` instead of hardcoded step/result content.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy repositories, Python `unittest`, Next.js 14, React 18, TypeScript, CSS Modules, Zustand.

---

## File Structure

- Modify `backend/models/agent.py`
  - Add `AgentStepId`, `AgentStepStatus`, `AgentStepError`, and `AgentStep`.
  - Add `steps` to `AgentSession` and `AgentTaskDetail`.
  - Add `currentStepId` to `AgentTaskSummary`.
- Create `backend/services/agent_step_snapshot_service.py`
  - Owns standard step metadata, status aggregation, result payload construction, and retryable-step mapping.
- Modify `backend/services/agent_read_service.py`
  - Uses `AgentStepSnapshotService` to add session `steps[]`.
- Modify `backend/services/agent_task_read_service.py`
  - Uses `AgentStepSnapshotService` to add task detail `steps[]` and summary `currentStepId`.
- Modify `tests/test_agent_api_p0.py`
  - Adds API contract tests for step models, session steps, task detail steps, and failure mapping.
- Modify `src/lib/agentApi.ts`
  - Adds frontend step types and `steps` to `AgentSession`.
- Modify `src/lib/taskApi.ts`
  - Adds `currentStepId` to task summaries and `steps` to task details.
- Modify `src/components/workspace/BriefWorkspacePage.tsx`
  - Renders the first four backend steps instead of local static step definitions.
- Modify `src/components/workspace/BriefWorkspacePage.module.css`
  - Adjusts styles only as needed for backend-driven result rendering.
- Modify `src/components/tasks/TaskManagerPage.tsx`
  - Renders task detail modal steps before events.
- Modify `src/components/tasks/TaskManagerPage.module.css`
  - Adds task detail step snapshot styles.
- Modify `scripts/check-product-pages.mjs`
  - Extends structural checks to assert backend-driven step labels remain visible.

---

### Task 1: Add Standard Step Models To Backend Contract

**Files:**
- Modify: `backend/models/agent.py`
- Test: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Add a failing model contract test**

Append this test to `AgentApiP0ContractTests` in `tests/test_agent_api_p0.py`:

```python
    def test_agent_step_response_models_can_be_instantiated(self):
        from backend.models.agent import AgentStep, AgentStepError

        step = AgentStep(
            id="understand_request",
            title="理解原始需求",
            description="读取用户原始 prompt，提炼主题、受众、用途和初步意图。",
            status="failed",
            progress=30,
            summary="已读取原始需求",
            result={"originalPrompt": "做一个 30 秒产品宣传片"},
            error=AgentStepError(
                message="规划失败",
                retryable=True,
                retryableStep="finalize_plan",
            ),
            startedAt="2026-05-05T10:00:00",
            finishedAt="2026-05-05T10:01:00",
        )

        self.assertEqual(step.id, "understand_request")
        self.assertEqual(step.error.retryableStep, "finalize_plan")
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_agent_step_response_models_can_be_instantiated
```

Expected: fail with `ImportError` because `AgentStep` and `AgentStepError` do not exist.

- [ ] **Step 3: Add backend step models**

In `backend/models/agent.py`, update imports:

```python
from typing import Any, Dict, List, Literal, Optional
```

Add these models after `AgentError`:

```python
AgentStepId = Literal[
    "understand_request",
    "extract_requirements",
    "generate_options",
    "finalize_plan",
    "create_task",
    "search_assets",
    "prepare_assets",
    "render_video",
]

AgentStepStatus = Literal["pending", "running", "succeeded", "failed", "skipped"]


class AgentStepError(BaseModel):
    message: str
    retryable: bool = False
    retryableStep: Optional[AgentStepId] = None


class AgentStep(BaseModel):
    id: AgentStepId
    title: str
    description: str
    status: AgentStepStatus = "pending"
    progress: float = 0.0
    summary: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[AgentStepError] = None
    startedAt: Optional[str] = None
    finishedAt: Optional[str] = None
```

Update `AgentSession`, `AgentTaskSummary`, and `AgentTaskDetail`:

```python
class AgentSession(BaseModel):
    id: str
    status: AgentStatus = AgentStatus.IDLE
    messages: List[AgentMessage] = Field(default_factory=list)
    plan: Optional[EditPlan] = None
    clips: List[ClipInfo] = Field(default_factory=list)
    events: List[AgentEvent] = Field(default_factory=list)
    steps: List[AgentStep] = Field(default_factory=list)
    videoUrl: Optional[str] = None
    activeJobId: Optional[str] = None
    error: Optional[AgentError] = None
    progress: float = 0.0
    currentStep: str = ""


class AgentTaskSummary(BaseModel):
    id: str
    sessionId: str
    title: str
    status: str
    progress: float = 0.0
    currentStep: str = ""
    currentStepId: Optional[AgentStepId] = None
    createdAt: str
    updatedAt: str


class AgentTaskDetail(AgentTaskSummary):
    events: List[AgentEvent] = Field(default_factory=list)
    clips: List[ClipInfo] = Field(default_factory=list)
    steps: List[AgentStep] = Field(default_factory=list)
    error: Optional[AgentError] = None
    videoUrl: Optional[str] = None
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_agent_step_response_models_can_be_instantiated
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/models/agent.py tests/test_agent_api_p0.py
git commit -m "feat: add standard agent step models"
```

---

### Task 2: Add Session Step Snapshot Service

**Files:**
- Create: `backend/services/agent_step_snapshot_service.py`
- Modify: `backend/services/agent_read_service.py`
- Test: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Add a failing API test for session steps**

Append this test to `AgentApiP0ContractTests` in `tests/test_agent_api_p0.py`:

```python
    def test_agent_session_response_includes_standard_steps_from_prompt_and_plan(self):
        async def _run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/agent/sessions",
                    json={"message": "做一个 30 秒 AI 笔记产品宣传片"},
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()

                self.assertEqual(
                    [step["id"] for step in payload["steps"]],
                    [
                        "understand_request",
                        "extract_requirements",
                        "generate_options",
                        "finalize_plan",
                        "create_task",
                        "search_assets",
                        "prepare_assets",
                        "render_video",
                    ],
                )
                understand_step = payload["steps"][0]
                self.assertEqual(understand_step["status"], "succeeded")
                self.assertEqual(understand_step["result"]["originalPrompt"], "做一个 30 秒 AI 笔记产品宣传片")

                finalize_step = payload["steps"][3]
                self.assertEqual(finalize_step["status"], "succeeded")
                self.assertEqual(finalize_step["result"]["title"], payload["plan"]["title"])
                self.assertEqual(len(finalize_step["result"]["scenes"]), len(payload["plan"]["scenes"]))

                self.assertEqual(payload["steps"][4]["status"], "pending")

        import asyncio

        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module,
            "read_service",
            self.read_service,
        ):
            asyncio.run(_run())
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_agent_session_response_includes_standard_steps_from_prompt_and_plan
```

Expected: fail because `payload["steps"]` is missing or empty.

- [ ] **Step 3: Create the snapshot service**

Create `backend/services/agent_step_snapshot_service.py`:

```python
from dataclasses import dataclass
from typing import Iterable

from backend.models.agent import AgentStep, AgentStepError, AgentStepId, ClipInfo, EditPlan


@dataclass(frozen=True)
class StepMeta:
    id: AgentStepId
    title: str
    description: str


STANDARD_STEPS: tuple[StepMeta, ...] = (
    StepMeta("understand_request", "理解原始需求", "读取用户原始 prompt，提炼主题、受众、用途和初步意图。"),
    StepMeta("extract_requirements", "提炼目标与限制", "提炼时长、格式、风格、素材限制、输出目标等约束。"),
    StepMeta("generate_options", "生成方案方向", "生成多个可选方向，供用户选择主方向。"),
    StepMeta("finalize_plan", "生成最终执行方案", "根据用户选择生成最终方案、镜头拆分和可确认计划。"),
    StepMeta("create_task", "创建执行任务", "用户确认方案后创建后端 job，并返回队列信息。"),
    StepMeta("search_assets", "搜索素材", "根据最终方案搜索候选素材并记录搜索结果。"),
    StepMeta("prepare_assets", "准备素材", "下载、裁剪、整理素材，形成渲染输入。"),
    StepMeta("render_video", "渲染视频", "调用渲染流程，生成视频产物或失败原因。"),
)

EVENT_STEP_TO_AGENT_STEP: dict[str, AgentStepId] = {
    "planning": "finalize_plan",
    "queued": "create_task",
    "searching": "search_assets",
    "downloading": "prepare_assets",
    "rendering": "render_video",
    "done": "render_video",
    "failed": "render_video",
}

RETRYABLE_STEP_TO_AGENT_STEP: dict[str, AgentStepId] = {
    "planning": "finalize_plan",
    "queued": "create_task",
    "searching": "search_assets",
    "downloading": "prepare_assets",
    "rendering": "render_video",
}


class AgentStepSnapshotService:
    def build_session_steps(self, session_record, message_rows, plan_row, event_rows) -> list[AgentStep]:
        plan = EditPlan.model_validate(plan_row.plan_json) if plan_row is not None else None
        first_user_message = next((row for row in message_rows if row.role == "user"), None)
        steps = self._empty_steps()

        if first_user_message is not None:
            steps["understand_request"] = self._succeeded(
                "understand_request",
                summary="已理解原始需求",
                result={
                    "originalPrompt": first_user_message.content,
                    "topic": session_record.title or plan.title if plan else "智能剪辑短片",
                    "audience": "待进一步确认",
                    "useCase": "短视频生成",
                    "intentSummary": first_user_message.content,
                },
                started_at=first_user_message.created_at.isoformat(),
                finished_at=first_user_message.created_at.isoformat(),
            )

        if plan is not None:
            plan_time = plan_row.created_at.isoformat()
            steps["extract_requirements"] = self._succeeded(
                "extract_requirements",
                summary="已提炼目标时长、风格和镜头结构",
                result={
                    "targetDuration": plan.targetDuration,
                    "aspectRatio": "16:9",
                    "style": plan.style,
                    "tone": plan.style,
                    "constraints": [f"{len(plan.scenes)} 个场景", f"{plan.targetDuration} 秒"],
                },
                started_at=plan_time,
                finished_at=plan_time,
            )
            steps["generate_options"] = self._succeeded(
                "generate_options",
                summary="已生成方案方向",
                result={
                    "options": [
                        {
                            "id": "A",
                            "name": "稳健叙事",
                            "summary": "以清晰问题和结果转化组织视频结构。",
                            "tags": ["稳健", "清晰", "低风险"],
                            "recommended": True,
                        }
                    ],
                    "selectedOptionId": "A",
                },
                started_at=plan_time,
                finished_at=plan_time,
            )
            steps["finalize_plan"] = self._succeeded(
                "finalize_plan",
                summary="最终执行方案已生成，等待确认",
                result={
                    "title": plan.title,
                    "style": plan.style,
                    "targetDuration": plan.targetDuration,
                    "selectedOptionId": "A",
                    "scenes": [scene.model_dump(mode="json") for scene in plan.scenes],
                },
                started_at=plan_time,
                finished_at=plan_time,
            )

        self._apply_session_failure(steps, session_record)
        return list(steps.values())

    def build_task_steps(self, session_record, job_record, plan_row, artifact_rows, event_rows) -> list[AgentStep]:
        plan = EditPlan.model_validate(plan_row.plan_json) if plan_row is not None else None
        steps = self._empty_steps()

        if session_record is not None:
            # Task details include the full product flow. Session planning data can be reconstructed from the plan.
            prompt_summary = session_record.title or (plan.title if plan else "视频任务")
            steps["understand_request"] = self._succeeded(
                "understand_request",
                summary="已关联原始会话需求",
                result={
                    "originalPrompt": prompt_summary,
                    "topic": prompt_summary,
                    "audience": "待进一步确认",
                    "useCase": "短视频生成",
                    "intentSummary": prompt_summary,
                },
                started_at=session_record.created_at.isoformat(),
                finished_at=session_record.created_at.isoformat(),
            )

        if plan is not None:
            plan_time = plan_row.created_at.isoformat()
            steps["extract_requirements"] = self._succeeded(
                "extract_requirements",
                summary="已提炼计划要求",
                result={
                    "targetDuration": plan.targetDuration,
                    "aspectRatio": "16:9",
                    "style": plan.style,
                    "tone": plan.style,
                    "constraints": [f"{len(plan.scenes)} 个场景", f"{plan.targetDuration} 秒"],
                },
                started_at=plan_time,
                finished_at=plan_time,
            )
            steps["generate_options"] = self._succeeded(
                "generate_options",
                summary="已确定执行方向",
                result={
                    "options": [
                        {
                            "id": "A",
                            "name": "稳健叙事",
                            "summary": "以清晰问题和结果转化组织视频结构。",
                            "tags": ["稳健", "清晰", "低风险"],
                            "recommended": True,
                        }
                    ],
                    "selectedOptionId": "A",
                },
                started_at=plan_time,
                finished_at=plan_time,
            )
            steps["finalize_plan"] = self._succeeded(
                "finalize_plan",
                summary="最终执行方案已确认",
                result={
                    "title": plan.title,
                    "style": plan.style,
                    "targetDuration": plan.targetDuration,
                    "selectedOptionId": "A",
                    "scenes": [scene.model_dump(mode="json") for scene in plan.scenes],
                },
                started_at=plan_time,
                finished_at=plan_time,
            )

        if job_record is not None:
            queued_at = job_record.created_at.isoformat()
            steps["create_task"] = self._succeeded(
                "create_task",
                summary="执行任务已创建",
                result={
                    "jobId": job_record.id,
                    "sessionId": job_record.session_id or "",
                    "queuedAt": queued_at,
                    "queueName": job_record.job_type,
                },
                started_at=queued_at,
                finished_at=queued_at,
            )

        clip_rows = [row for row in artifact_rows if row.artifact_type == "clip"]
        video_rows = [row for row in artifact_rows if row.artifact_type == "video"]
        events_by_type = {row.event_type: row for row in event_rows}

        if "job_started" in events_by_type or job_record.status in {"running", "succeeded", "failed"}:
            status = "succeeded" if clip_rows or video_rows else "running"
            steps["search_assets"] = self._step(
                "search_assets",
                status=status,
                progress=100 if status == "succeeded" else 50,
                summary="素材搜索已开始" if status == "running" else "素材搜索已完成",
                result={
                    "queries": [scene.searchQuery for scene in plan.scenes] if plan else [],
                    "candidateCount": len(clip_rows),
                    "selectedCount": len(clip_rows),
                },
                started_at=self._first_event_time(event_rows, {"job_started"}),
                finished_at=self._first_event_time(event_rows, {"clips_ready"}) if clip_rows else None,
            )

        if clip_rows:
            steps["prepare_assets"] = self._succeeded(
                "prepare_assets",
                summary=f"已准备 {len(clip_rows)} 段素材",
                result={"clips": [self._clip_result(row) for row in clip_rows]},
                started_at=self._first_event_time(event_rows, {"job_started"}),
                finished_at=self._first_event_time(event_rows, {"clips_ready"}),
            )
        elif job_record.status == "running" and job_record.progress >= 60:
            steps["prepare_assets"] = self._step(
                "prepare_assets",
                status="running",
                progress=min(job_record.progress, 75),
                summary="正在准备素材",
                result={"clips": []},
            )

        video_url = self._resolve_video_url(video_rows, event_rows)
        if video_url:
            steps["render_video"] = self._succeeded(
                "render_video",
                summary="视频已经生成",
                result={
                    "videoUrl": video_url,
                    "format": "mp4",
                    "duration": plan.targetDuration if plan else 0,
                    "artifactId": video_rows[-1].id if video_rows else None,
                },
                started_at=self._first_event_time(event_rows, {"render_started"}),
                finished_at=self._first_event_time(event_rows, {"job_succeeded"}),
            )
        elif job_record.status == "running" and job_record.progress >= 80:
            steps["render_video"] = self._step(
                "render_video",
                status="running",
                progress=job_record.progress,
                summary="正在渲染视频",
                result=None,
                started_at=self._first_event_time(event_rows, {"render_started"}),
            )

        self._apply_job_failure(steps, job_record, event_rows)
        return list(steps.values())

    def resolve_current_step_id(self, status: str, current_step: str = "") -> AgentStepId | None:
        if status in {"queued", "pending"}:
            return "create_task"
        if status in {"running", "active"}:
            if "渲染" in current_step or "合成" in current_step:
                return "render_video"
            if "下载" in current_step or "素材" in current_step:
                return "prepare_assets"
            return "search_assets"
        if status in {"succeeded", "completed", "done"}:
            return "render_video"
        if status in {"failed", "error"}:
            return "render_video"
        return None

    def _empty_steps(self) -> dict[AgentStepId, AgentStep]:
        return {meta.id: self._step(meta.id, status="pending", progress=0, summary="", result=None) for meta in STANDARD_STEPS}

    def _step(
        self,
        step_id: AgentStepId,
        status: str,
        progress: float,
        summary: str,
        result: dict | None,
        started_at: str | None = None,
        finished_at: str | None = None,
        error: AgentStepError | None = None,
    ) -> AgentStep:
        meta = next(meta for meta in STANDARD_STEPS if meta.id == step_id)
        return AgentStep(
            id=meta.id,
            title=meta.title,
            description=meta.description,
            status=status,
            progress=max(0, min(100, progress)),
            summary=summary,
            result=result,
            error=error,
            startedAt=started_at,
            finishedAt=finished_at,
        )

    def _succeeded(self, step_id: AgentStepId, summary: str, result: dict, started_at: str | None, finished_at: str | None) -> AgentStep:
        return self._step(step_id, "succeeded", 100, summary, result, started_at, finished_at)

    def _apply_session_failure(self, steps: dict[AgentStepId, AgentStep], session_record) -> None:
        if session_record.status != "failed" or not session_record.error_message:
            return
        retryable_step = RETRYABLE_STEP_TO_AGENT_STEP.get(session_record.error_retryable_step or "", "finalize_plan")
        self._mark_failed(steps, retryable_step, session_record.error_message, retryable_step)

    def _apply_job_failure(self, steps: dict[AgentStepId, AgentStep], job_record, event_rows) -> None:
        if job_record.status != "failed" or not job_record.error_message:
            return
        retryable_step = self._resolve_retryable_step(event_rows) or self.resolve_current_step_id(job_record.status, job_record.current_step or "") or "render_video"
        self._mark_failed(steps, retryable_step, job_record.error_message, retryable_step)

    def _mark_failed(self, steps: dict[AgentStepId, AgentStep], step_id: AgentStepId, message: str, retryable_step: AgentStepId) -> None:
        current = steps[step_id]
        steps[step_id] = self._step(
            step_id,
            "failed",
            current.progress,
            message,
            current.result,
            current.startedAt,
            current.finishedAt,
            AgentStepError(message=message, retryable=True, retryableStep=retryable_step),
        )

    def _first_event_time(self, event_rows: Iterable, event_types: set[str]) -> str | None:
        for row in event_rows:
            if row.event_type in event_types:
                return row.created_at.isoformat()
        return None

    def _clip_result(self, row) -> dict:
        metadata = row.metadata_json or {}
        return {
            "sceneId": int(row.scene_id) if row.scene_id is not None and str(row.scene_id).isdigit() else 0,
            "sourceUrl": row.source_url or "",
            "publicUrl": row.public_url or "",
            "caption": metadata.get("caption", "") or "",
            "trimStart": float(metadata.get("trimStart", 0.0) or 0.0),
            "trimDuration": float(metadata.get("trimDuration", row.duration or 0.0) or 0.0),
        }

    def _resolve_video_url(self, video_rows, event_rows) -> str | None:
        for row in reversed(video_rows):
            if row.public_url:
                return row.public_url
        for row in reversed(event_rows):
            payload = row.payload_json or {}
            if payload.get("videoUrl"):
                return str(payload["videoUrl"])
        return None

    def _resolve_retryable_step(self, event_rows) -> AgentStepId | None:
        for row in reversed(event_rows):
            payload = row.payload_json or {}
            retryable_step = payload.get("retryableStep")
            if retryable_step:
                return RETRYABLE_STEP_TO_AGENT_STEP.get(str(retryable_step))
        return None
```

- [ ] **Step 4: Wire session read service**

In `backend/services/agent_read_service.py`, add import:

```python
from backend.services.agent_step_snapshot_service import AgentStepSnapshotService
```

In `AgentReadService.__init__`, add:

```python
        self.step_snapshot_service = AgentStepSnapshotService()
```

In `build_session_response`, add `steps` before `videoUrl`:

```python
            steps=self.step_snapshot_service.build_session_steps(
                session_record=session_record,
                message_rows=message_rows,
                plan_row=plan_row,
                event_rows=event_rows,
            ),
```

- [ ] **Step 5: Run the focused test and verify it passes**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_agent_session_response_includes_standard_steps_from_prompt_and_plan
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add backend/services/agent_step_snapshot_service.py backend/services/agent_read_service.py tests/test_agent_api_p0.py
git commit -m "feat: add session step snapshots"
```

---

### Task 3: Add Task Step Snapshots And Current Step IDs

**Files:**
- Modify: `backend/services/agent_task_read_service.py`
- Modify: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Add a failing task detail API test**

Append this test to `AgentApiP0ContractTests` in `tests/test_agent_api_p0.py`:

```python
    def test_agent_task_detail_response_includes_standard_steps_and_current_step_id(self):
        async def _run():
            session = self.session_service.create_session("做一个产品宣传片")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                event_repo = AgentEventRepository(db)
                artifact_repo = AgentArtifactRepository(db)
                job_record = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="running",
                    progress=80,
                    current_step="正在合成视频",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="job_started",
                    step="searching",
                    progress=35,
                    message="任务开始执行",
                    payload_json={"jobId": job_record.id},
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="clips_ready",
                    step="downloading",
                    progress=60,
                    message="素材已准备完成，共 1 段",
                    payload_json={"clipCount": 1},
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="render_started",
                    step="rendering",
                    progress=80,
                    message="开始合成视频",
                    payload_json={},
                )
                artifact_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    artifact_type="clip",
                    scene_id="1",
                    source_url="https://example.com/source.mp4",
                    local_path="/tmp/clip.mp4",
                    public_url="https://cdn.example.com/clip.mp4",
                    duration=6.0,
                    metadata_json={"caption": "clip", "trimStart": 1.0, "trimDuration": 5.0},
                )
                job_id = job_record.id
                db.commit()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                tasks_response = await client.get("/api/agent/tasks")
                self.assertEqual(tasks_response.status_code, 200)
                task_summary = tasks_response.json()[0]
                self.assertEqual(task_summary["currentStepId"], "render_video")

                detail_response = await client.get(f"/api/agent/tasks/{job_id}")
                self.assertEqual(detail_response.status_code, 200)
                detail = detail_response.json()

                self.assertEqual(len(detail["steps"]), 8)
                self.assertEqual(detail["steps"][4]["id"], "create_task")
                self.assertEqual(detail["steps"][4]["status"], "succeeded")
                self.assertEqual(detail["steps"][6]["id"], "prepare_assets")
                self.assertEqual(detail["steps"][6]["status"], "succeeded")
                self.assertEqual(detail["steps"][6]["result"]["clips"][0]["publicUrl"], "https://cdn.example.com/clip.mp4")
                self.assertEqual(detail["steps"][7]["id"], "render_video")
                self.assertEqual(detail["steps"][7]["status"], "running")

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module, "task_read_service", task_read_service
        ):
            asyncio.run(_run())
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_agent_task_detail_response_includes_standard_steps_and_current_step_id
```

Expected: fail because `currentStepId` or `steps` is missing.

- [ ] **Step 3: Wire task read service**

In `backend/services/agent_task_read_service.py`, add imports:

```python
    AgentPlanRepository,
```

and:

```python
from backend.services.agent_step_snapshot_service import AgentStepSnapshotService
```

In `AgentTaskReadService.__init__`, add:

```python
        self.step_snapshot_service = AgentStepSnapshotService()
```

In `read_task`, load the plan:

```python
            plan = AgentPlanRepository(db).get(job.plan_id) if job.plan_id else None
```

Add `steps` when constructing `AgentTaskDetail`:

```python
                steps=self.step_snapshot_service.build_task_steps(
                    session_record=session,
                    job_record=job,
                    plan_row=plan,
                    artifact_rows=artifacts,
                    event_rows=events,
                ),
```

In `_build_task_summary`, add:

```python
            currentStepId=self.step_snapshot_service.resolve_current_step_id(
                job.status,
                job.current_step or "",
            ),
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_agent_task_detail_response_includes_standard_steps_and_current_step_id
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/services/agent_task_read_service.py tests/test_agent_api_p0.py
git commit -m "feat: add task step snapshots"
```

---

### Task 4: Add Failure Mapping For Standard Steps

**Files:**
- Modify: `backend/services/agent_step_snapshot_service.py`
- Modify: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Add a failing failure-mapping test**

Append this test to `AgentApiP0ContractTests` in `tests/test_agent_api_p0.py`:

```python
    def test_agent_task_failed_retryable_step_maps_to_standard_step_error(self):
        async def _run():
            session = self.session_service.create_session("做一个失败可恢复的短片")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                event_repo = AgentEventRepository(db)
                job_record = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="failed",
                    progress=60,
                    current_step="处理失败：下载素材失败",
                    error_message="下载素材失败",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="job_failed",
                    step="failed",
                    progress=60,
                    message="下载素材失败",
                    payload_json={"retryableStep": "downloading"},
                )
                job_id = job_record.id
                db.commit()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get(f"/api/agent/tasks/{job_id}")
                self.assertEqual(response.status_code, 200)
                payload = response.json()

                failed_steps = [step for step in payload["steps"] if step["status"] == "failed"]
                self.assertEqual(len(failed_steps), 1)
                self.assertEqual(failed_steps[0]["id"], "prepare_assets")
                self.assertEqual(failed_steps[0]["error"]["message"], "下载素材失败")
                self.assertTrue(failed_steps[0]["error"]["retryable"])
                self.assertEqual(failed_steps[0]["error"]["retryableStep"], "prepare_assets")
                self.assertEqual(payload["steps"][7]["status"], "pending")

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module, "task_read_service", task_read_service
        ):
            asyncio.run(_run())
```

- [ ] **Step 2: Run the focused test and verify it fails if mapping is incomplete**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_agent_task_failed_retryable_step_maps_to_standard_step_error
```

Expected: fail until `"downloading"` maps to `"prepare_assets"` and later steps remain pending.

- [ ] **Step 3: Ensure failure mapping uses standard step IDs**

Ensure `RETRYABLE_STEP_TO_AGENT_STEP` in `backend/services/agent_step_snapshot_service.py` contains:

```python
RETRYABLE_STEP_TO_AGENT_STEP: dict[str, AgentStepId] = {
    "planning": "finalize_plan",
    "queued": "create_task",
    "searching": "search_assets",
    "downloading": "prepare_assets",
    "rendering": "render_video",
}
```

Ensure `_apply_job_failure` uses `_resolve_retryable_step(event_rows)` before falling back to current-step text:

```python
        retryable_step = self._resolve_retryable_step(event_rows) or self.resolve_current_step_id(job_record.status, job_record.current_step or "") or "render_video"
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_agent_task_failed_retryable_step_maps_to_standard_step_error
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/services/agent_step_snapshot_service.py tests/test_agent_api_p0.py
git commit -m "fix: map failed jobs to standard steps"
```

---

### Task 5: Sync Frontend API Types

**Files:**
- Modify: `src/lib/agentApi.ts`
- Modify: `src/lib/taskApi.ts`

- [ ] **Step 1: Update `src/lib/agentApi.ts` types**

Add these types after `AgentErrorInfo`:

```ts
export type AgentStepId =
  | 'understand_request'
  | 'extract_requirements'
  | 'generate_options'
  | 'finalize_plan'
  | 'create_task'
  | 'search_assets'
  | 'prepare_assets'
  | 'render_video'

export type AgentStepStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped'

export interface AgentStepError {
  message: string
  retryable: boolean
  retryableStep?: AgentStepId | null
}

export interface AgentStep {
  id: AgentStepId
  title: string
  description: string
  status: AgentStepStatus
  progress: number
  summary: string
  result: Record<string, unknown> | null
  error: AgentStepError | null
  startedAt: string | null
  finishedAt: string | null
}
```

Add `steps` to `AgentSession` after `events`:

```ts
  steps: AgentStep[]
```

- [ ] **Step 2: Update `src/lib/taskApi.ts` types**

Change the import:

```ts
import type { AgentErrorInfo, AgentEvent, AgentStep, AgentStepId, ClipInfo } from './agentApi'
```

Add `currentStepId` to `AgentTaskSummary`:

```ts
  currentStepId: AgentStepId | null
```

Add `steps` to `AgentTaskDetail`:

```ts
  steps: AgentStep[]
```

- [ ] **Step 3: Run TypeScript build and verify frontend types compile**

Run:

```bash
npm run build
```

Expected: pass, because no frontend consumers require the new fields yet.

- [ ] **Step 4: Commit**

```bash
git add src/lib/agentApi.ts src/lib/taskApi.ts
git commit -m "feat: sync agent step frontend types"
```

---

### Task 6: Render Backend Steps In Workspace Page

**Files:**
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
- Modify: `src/components/workspace/BriefWorkspacePage.module.css`
- Modify: `scripts/check-product-pages.mjs`

- [ ] **Step 1: Replace local static step definitions**

In `src/components/workspace/BriefWorkspacePage.tsx`, remove:

```ts
const STEP_DEFINITIONS = [
  {
    id: 'understand',
    title: '步骤 1：理解原始需求',
    progress: 100,
    buildResult: (session: AgentSession | null) => [
      { label: '原始诉求', value: session?.messages.find((item) => item.role === 'user')?.content || '等待输入' },
      { label: '推断目标', value: session?.plan ? `${session.plan.title} 的宣传表达` : '待分析' },
      { label: '基调判断', value: session?.plan?.style || '专业可信' },
    ],
  },
  {
    id: 'constraints',
    title: '步骤 2：提炼目标与限制条件',
    progress: 100,
    buildResult: (session: AgentSession | null) => [
      { label: '建议时长', value: session?.plan ? `${session.plan.targetDuration} 秒` : '待分析' },
      { label: '执行结构', value: session?.plan ? `${session.plan.scenes.length} 个段落` : '待分析' },
      { label: '当前状态', value: session?.currentStep || '等待需求进入系统' },
    ],
  },
  {
    id: 'directions',
    title: '步骤 3：生成多个方案方向',
    progress: 100,
  },
  {
    id: 'final',
    title: '步骤 4：输出最终执行方案',
    progress: 100,
  },
] as const;
```

Add these constants near `DIRECTION_OPTIONS`:

```ts
const WORKSPACE_STEP_IDS = ['understand_request', 'extract_requirements', 'generate_options', 'finalize_plan'] as const;

const FALLBACK_WORKSPACE_STEPS = [
  {
    id: 'understand_request',
    title: '理解原始需求',
    description: '读取用户原始 prompt，提炼主题、受众、用途和初步意图。',
    status: 'pending',
    progress: 0,
    summary: '',
    result: null,
    error: null,
    startedAt: null,
    finishedAt: null,
  },
  {
    id: 'extract_requirements',
    title: '提炼目标与限制',
    description: '提炼时长、格式、风格、素材限制、输出目标等约束。',
    status: 'pending',
    progress: 0,
    summary: '',
    result: null,
    error: null,
    startedAt: null,
    finishedAt: null,
  },
  {
    id: 'generate_options',
    title: '生成方案方向',
    description: '生成多个可选方向，供用户选择主方向。',
    status: 'pending',
    progress: 0,
    summary: '',
    result: null,
    error: null,
    startedAt: null,
    finishedAt: null,
  },
  {
    id: 'finalize_plan',
    title: '生成最终执行方案',
    description: '根据用户选择生成最终方案、镜头拆分和可确认计划。',
    status: 'pending',
    progress: 0,
    summary: '',
    result: null,
    error: null,
    startedAt: null,
    finishedAt: null,
  },
] as const;
```

The fallback steps are labels only. They must not contain fake business results.

- [ ] **Step 2: Add result helpers**

Add these helper functions before the component:

```ts
function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asString(value: unknown, fallback = '') {
  return typeof value === 'string' ? value : fallback;
}

function asNumber(value: unknown, fallback = 0) {
  return typeof value === 'number' ? value : fallback;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}
```

- [ ] **Step 3: Derive workspace steps from session**

Inside `BriefWorkspacePage`, add:

```ts
  const workspaceSteps = useMemo(() => {
    if (!session?.steps?.length) {
      return FALLBACK_WORKSPACE_STEPS;
    }
    return WORKSPACE_STEP_IDS.map((stepId) => session.steps.find((step) => step.id === stepId)).filter(Boolean);
  }, [session?.steps]);
```

- [ ] **Step 4: Render `generate_options` from backend result**

Inside the step loop, for `step.id === 'generate_options'`, read:

```ts
const result = asRecord(step.result);
const options = asArray(result.options).map((option) => asRecord(option));
const selectedOptionId = asString(result.selectedOptionId, selectedDirection);
```

Render option cards from `options` when present. If `options.length === 0`, render:

```tsx
<div className={styles.pendingPlan}>
  <p>等待后端返回方案方向。</p>
</div>
```

Keep `selectedDirection` for UI selection, but initialize the displayed selected state from `selectedOptionId`.

- [ ] **Step 5: Render `finalize_plan` from backend result**

Inside the step loop, for `step.id === 'finalize_plan'`, read:

```ts
const result = asRecord(step.result);
const scenes = asArray(result.scenes).map((scene) => asRecord(scene));
```

Render final summary from:

```ts
[
  { label: '标题', value: asString(result.title, '待确认') },
  { label: '时长节奏', value: `${asNumber(result.targetDuration, 0)} 秒` },
  { label: '风格方向', value: asString(result.style, '待确认') },
  { label: '输出目标', value: session?.status === 'done' ? '已输出结果' : '确认后生成任务' },
]
```

Render scenes from `scenes`; if empty, show:

```tsx
<div className={styles.pendingPlan}>
  <p>待后端返回最终方案后，这里会展示结构化段落拆分。</p>
</div>
```

- [ ] **Step 6: Render generic result cards for the first two steps**

For non-option and non-final steps, render `step.summary` and simple key/value rows from `step.result`.

Use:

```tsx
{Object.entries(asRecord(step.result)).length > 0 ? (
  <div className={styles.analysisGrid}>
    {Object.entries(asRecord(step.result)).map(([label, value]) => (
      <div key={label} className={styles.analysisItem}>
        <span>{label}</span>
        <strong>{Array.isArray(value) ? value.join(' / ') : String(value)}</strong>
      </div>
    ))}
  </div>
) : (
  <div className={styles.pendingPlan}>
    <p>{step.summary || '等待后端返回步骤结果。'}</p>
  </div>
)}
```

- [ ] **Step 7: Extend page structural check**

In `scripts/check-product-pages.mjs`, add:

```js
  assertIncludes(workspaceHtml, '理解原始需求', 'workspace 页面缺少标准步骤：理解原始需求');
  assertIncludes(workspaceHtml, '提炼目标与限制', 'workspace 页面缺少标准步骤：提炼目标与限制');
```

- [ ] **Step 8: Run build and page check**

Run:

```bash
npm run build
node scripts/check-product-pages.mjs
```

Expected: both pass.

- [ ] **Step 9: Commit**

```bash
git add src/components/workspace/BriefWorkspacePage.tsx src/components/workspace/BriefWorkspacePage.module.css scripts/check-product-pages.mjs
git commit -m "feat: render workspace standard steps"
```

---

### Task 7: Render Standard Steps In Task Detail Modal

**Files:**
- Modify: `src/components/tasks/TaskManagerPage.tsx`
- Modify: `src/components/tasks/TaskManagerPage.module.css`
- Modify: `scripts/check-product-pages.mjs`

- [ ] **Step 1: Add step helpers to task page**

In `src/components/tasks/TaskManagerPage.tsx`, add:

```ts
function getStepStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: '等待中',
    running: '进行中',
    succeeded: '已完成',
    failed: '失败',
    skipped: '已跳过',
  };
  return labels[status] ?? status;
}
```

- [ ] **Step 2: Use currentStepId in search text**

Update `getTaskSearchText`:

```ts
function getTaskSearchText(task: AgentTaskSummary) {
  return `${task.title} ${task.status} ${task.currentStep} ${task.currentStepId ?? ''} ${task.sessionId} ${task.id}`.toLowerCase();
}
```

- [ ] **Step 3: Render steps before events in modal**

In the modal body, insert this section before the existing `事件时间线` section:

```tsx
              <section className={styles.modalSection}>
                <h3>标准步骤</h3>
                <ol className={styles.stepList}>
                  {activeTask.steps.map((step) => (
                    <li key={step.id} className={`${styles.stepItem} ${styles[`step_${step.status}`] ?? ''}`}>
                      <div className={styles.stepItemHead}>
                        <div>
                          <strong>{step.title}</strong>
                          <span>{step.description}</span>
                        </div>
                        <em>{getStepStatusLabel(step.status)}</em>
                      </div>
                      <div className={styles.progressTrack} aria-hidden="true">
                        <span style={{ width: formatProgress(step.progress) }} />
                      </div>
                      {step.summary ? <p>{step.summary}</p> : null}
                      {step.error ? <p className={styles.stepError}>{step.error.message}</p> : null}
                    </li>
                  ))}
                </ol>
              </section>
```

- [ ] **Step 4: Add task step styles**

In `src/components/tasks/TaskManagerPage.module.css`, add:

```css
.stepList {
  margin-top: 10px;
  display: grid;
  gap: 10px;
  list-style: none;
}

.stepItem {
  padding: 12px;
  border: 1px solid rgba(79, 85, 99, 0.12);
  border-radius: 8px;
  background: #ffffff;
  display: grid;
  gap: 8px;
}

.stepItemHead {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.stepItemHead strong {
  display: block;
  font-size: 13px;
}

.stepItemHead span {
  display: block;
  margin-top: 3px;
  color: var(--text-secondary);
  font-size: 12px;
}

.stepItemHead em {
  flex: 0 0 auto;
  font-style: normal;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.step_failed {
  border-color: rgba(153, 27, 27, 0.24);
  background: #fff7f7;
}

.stepError {
  color: #991b1b;
}
```

- [ ] **Step 5: Extend page structural check**

In `scripts/check-product-pages.mjs`, add:

```js
  assertIncludes(tasksHtml, '当前阶段', 'tasks 页面缺少当前阶段列');
```

Do not assert modal-only text in this script because the modal content is not server-rendered until a task is selected.

- [ ] **Step 6: Run build and page check**

Run:

```bash
npm run build
node scripts/check-product-pages.mjs
```

Expected: both pass.

- [ ] **Step 7: Commit**

```bash
git add src/components/tasks/TaskManagerPage.tsx src/components/tasks/TaskManagerPage.module.css scripts/check-product-pages.mjs
git commit -m "feat: show task standard steps"
```

---

### Task 8: Full Regression Verification

**Files:**
- No production files expected.

- [ ] **Step 1: Run backend focused regression**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_api_p0 tests.test_agent_persistence tests.test_agent_jobs
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend build**

Run:

```bash
npm run build
```

Expected: Next.js build passes.

- [ ] **Step 3: Run product page structural check**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected:

```text
product page checks passed
```

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short --branch
```

Expected: clean working tree on the implementation branch after all task commits.

- [ ] **Step 5: Final commit if verification required any small fix**

If verification required a fix, commit it:

```bash
git add backend/models/agent.py backend/services/agent_read_service.py backend/services/agent_step_snapshot_service.py backend/services/agent_task_read_service.py tests/test_agent_api_p0.py src/lib/agentApi.ts src/lib/taskApi.ts src/components/workspace/BriefWorkspacePage.tsx src/components/workspace/BriefWorkspacePage.module.css src/components/tasks/TaskManagerPage.tsx src/components/tasks/TaskManagerPage.module.css scripts/check-product-pages.mjs
git commit -m "fix: stabilize standard agent steps"
```

If no files changed, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage: backend models, snapshot service, API responses, frontend types, workspace rendering, task modal rendering, errors, and verification are all covered.
- Scope: this plan only implements read-model step snapshots and frontend consumption. It does not rewrite the execution engine.
- Backward compatibility: legacy `status`, `progress`, `currentStep`, `events`, `clips`, and `videoUrl` remain in place.
- Risk: `AgentStepSnapshotService` uses conservative inference from existing records. It can be refined later without changing the frontend contract.

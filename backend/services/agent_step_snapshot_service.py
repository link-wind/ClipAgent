from dataclasses import dataclass
from typing import Any, Optional

from backend.models.agent import AgentStep, AgentStepError, AgentStepId, EditPlan


@dataclass(frozen=True)
class StepMeta:
    id: AgentStepId
    title: str
    description: str


STANDARD_STEPS = [
    StepMeta(
        id="understand_request",
        title="理解原始需求",
        description="读取用户原始 prompt，提炼主题、受众、用途和初步意图。",
    ),
    StepMeta(
        id="extract_requirements",
        title="提炼目标与限制",
        description="提炼时长、格式、风格、素材限制、输出目标等约束。",
    ),
    StepMeta(
        id="generate_options",
        title="生成方案方向",
        description="生成多个可选方向，供用户选择主方向。",
    ),
    StepMeta(
        id="finalize_plan",
        title="生成最终执行方案",
        description="根据用户选择生成最终方案、镜头拆分和可确认计划。",
    ),
    StepMeta(
        id="create_task",
        title="创建执行任务",
        description="用户确认方案后创建后端 job，并返回队列信息。",
    ),
    StepMeta(
        id="search_assets",
        title="搜索素材",
        description="根据最终方案搜索候选素材并记录搜索结果。",
    ),
    StepMeta(
        id="prepare_assets",
        title="准备素材",
        description="下载、裁剪、整理素材，形成渲染输入。",
    ),
    StepMeta(
        id="render_video",
        title="渲染视频",
        description="调用渲染流程，生成视频产物或失败原因。",
    ),
]

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
        first_prompt = self._extract_first_prompt(message_rows)
        plan = self._extract_plan(plan_row)
        event_state = self._build_event_state(session_record, event_rows)

        steps_by_id = {meta.id: self._build_pending_step(meta) for meta in STANDARD_STEPS}

        if first_prompt is not None:
            steps_by_id["understand_request"] = self._build_understand_request_step(first_prompt)

        if plan is not None:
            requirements_result = self._build_requirements_result(first_prompt, plan)
            steps_by_id["extract_requirements"] = self._build_succeeded_step(
                self._meta("extract_requirements"),
                requirements_result,
                summary="已提炼需求",
            )
            steps_by_id["generate_options"] = self._build_succeeded_step(
                self._meta("generate_options"),
                self._build_generate_options_result(plan),
                summary="已生成方案",
            )
            steps_by_id["finalize_plan"] = self._build_succeeded_step(
                self._meta("finalize_plan"),
                self._build_finalize_plan_result(plan),
                summary="已确认计划",
            )

        self._apply_execution_state(steps_by_id, session_record, event_rows, event_state)

        return [steps_by_id[meta.id] for meta in STANDARD_STEPS]

    def build_task_steps(self, session_record, job_record, plan_row, artifact_rows, event_rows) -> list[AgentStep]:
        steps = self.build_session_steps(session_record, [], plan_row, event_rows)
        current_step_id = self.resolve_current_step_id(job_record.status, job_record.current_step or "")
        self._apply_task_artifacts(steps, artifact_rows, current_step_id)
        return steps

    def resolve_current_step_id(self, job_status: str, current_step: str) -> Optional[AgentStepId]:
        if job_status == "queued" or "入队" in current_step:
            return "create_task"
        if job_status == "rendering" or "合成视频" in current_step:
            return "render_video"
        if job_status == "downloading" or "准备渲染" in current_step:
            return "prepare_assets"
        if job_status == "searching" or "搜索素材" in current_step or job_status == "running":
            return "search_assets"
        if job_status == "succeeded" or "完成" in current_step:
            return "render_video"
        if job_status == "failed" or "失败" in current_step:
            return "render_video"
        return None

    def _build_understand_request_step(self, prompt: str) -> AgentStep:
        return self._build_succeeded_step(
            self._meta("understand_request"),
            {"originalPrompt": prompt},
            summary="已读取原始需求",
        )

    def _build_requirements_result(self, prompt: Optional[str], plan: EditPlan) -> dict[str, Any]:
        return {
            "originalPrompt": prompt or "",
            "title": plan.title,
            "targetDuration": plan.targetDuration,
            "style": plan.style,
            "sceneCount": len(plan.scenes),
        }

    def _build_generate_options_result(self, plan: EditPlan) -> dict[str, Any]:
        return {
            "title": plan.title,
            "options": [
                {
                    "sceneId": scene.id,
                    "description": scene.description,
                    "keywords": scene.keywords,
                    "searchQuery": scene.searchQuery,
                    "duration": scene.duration,
                }
                for scene in plan.scenes
            ],
        }

    def _build_finalize_plan_result(self, plan: EditPlan) -> dict[str, Any]:
        return {
            "title": plan.title,
            "targetDuration": plan.targetDuration,
            "style": plan.style,
            "scenes": [scene.model_dump(mode="json") for scene in plan.scenes],
        }

    def _build_pending_step(self, meta: StepMeta) -> AgentStep:
        return AgentStep(
            id=meta.id,
            title=meta.title,
            description=meta.description,
            status="pending",
            progress=0.0,
            summary="",
        )

    def _build_succeeded_step(
        self,
        meta: StepMeta,
        result: dict[str, Any],
        summary: str,
    ) -> AgentStep:
        return AgentStep(
            id=meta.id,
            title=meta.title,
            description=meta.description,
            status="succeeded",
            progress=100.0,
            summary=summary,
            result=result,
        )

    def _build_failed_step(self, meta: StepMeta, message: str, retryable_step: Optional[AgentStepId]) -> AgentStep:
        return AgentStep(
            id=meta.id,
            title=meta.title,
            description=meta.description,
            status="failed",
            progress=100.0,
            summary="执行失败",
            error=AgentStepError(message=message, retryable=True, retryableStep=retryable_step),
        )

    def _extract_first_prompt(self, message_rows) -> Optional[str]:
        for row in message_rows:
            if row.role == "user":
                return row.content
        return None

    def _extract_plan(self, plan_row) -> Optional[EditPlan]:
        if plan_row is None:
            return None
        return EditPlan.model_validate(plan_row.plan_json)

    def _build_event_state(self, session_record, event_rows) -> dict[str, Any]:
        latest_event_step = ""
        latest_failure_payload: dict[str, Any] = {}
        latest_job_id = ""
        latest_video_url = ""

        for row in event_rows:
            step = getattr(row, "step", None)
            if step:
                latest_event_step = step
            payload = getattr(row, "payload_json", None) or {}
            if step == "failed" and isinstance(payload, dict):
                latest_failure_payload = payload
            if step == "queued" and isinstance(payload, dict) and payload.get("jobId"):
                latest_job_id = payload["jobId"]
            if step == "done" and isinstance(payload, dict) and payload.get("videoUrl"):
                latest_video_url = payload["videoUrl"]

        retryable_step = ""
        if session_record is not None and getattr(session_record, "error_retryable_step", None):
            retryable_step = session_record.error_retryable_step or ""
        if not retryable_step and latest_failure_payload.get("retryableStep"):
            retryable_step = latest_failure_payload["retryableStep"]
        return {
            "latest_event_step": latest_event_step,
            "latest_failure_payload": latest_failure_payload,
            "latest_job_id": latest_job_id,
            "latest_video_url": latest_video_url,
            "retryable_step": retryable_step,
        }

    def _apply_execution_state(
        self,
        steps_by_id: dict[AgentStepId, AgentStep],
        session_record,
        event_rows,
        event_state: dict[str, Any],
    ) -> None:
        session_status = getattr(session_record, "status", "") if session_record is not None else ""
        latest_event_step = event_state["latest_event_step"]
        retryable_step = self._normalize_retryable_step(event_state["retryable_step"])

        if session_status in {"queued", "searching", "downloading", "rendering", "done"} or latest_event_step == "queued":
            self._mark_step_succeeded(
                steps_by_id,
                "create_task",
                self._build_create_task_result(session_record, event_state),
            )

        if session_status == "searching":
            self._mark_step_running(steps_by_id, "search_assets")
        elif session_status == "downloading":
            self._mark_step_succeeded(
                steps_by_id,
                "search_assets",
                self._build_search_assets_result(event_rows),
            )
            self._mark_step_running(steps_by_id, "prepare_assets")
        elif session_status == "rendering":
            self._mark_step_succeeded(
                steps_by_id,
                "search_assets",
                self._build_search_assets_result(event_rows),
            )
            self._mark_step_succeeded(
                steps_by_id,
                "prepare_assets",
                self._build_prepare_assets_result(event_rows),
            )
            self._mark_step_running(steps_by_id, "render_video")
        elif session_status == "done":
            self._mark_step_succeeded(
                steps_by_id,
                "search_assets",
                self._build_search_assets_result(event_rows),
            )
            self._mark_step_succeeded(
                steps_by_id,
                "prepare_assets",
                self._build_prepare_assets_result(event_rows),
            )
            self._mark_step_succeeded(
                steps_by_id,
                "render_video",
                self._build_render_result(session_record, event_rows, event_state),
            )
        elif session_status == "failed":
            failed_step_id = retryable_step or self._normalize_retryable_step(
                event_state["latest_failure_payload"].get("retryableStep")
            )
            if failed_step_id is None:
                failed_step_id = "render_video"
            self._apply_failed_execution_state(
                steps_by_id,
                failed_step_id,
                session_record,
                event_rows,
                event_state,
            )

    def _apply_failed_execution_state(
        self,
        steps_by_id: dict[AgentStepId, AgentStep],
        failed_step_id: AgentStepId,
        session_record,
        event_rows,
        event_state: dict[str, Any],
    ) -> None:
        if failed_step_id == "finalize_plan":
            self._mark_step_failed(
                steps_by_id,
                "finalize_plan",
                message=getattr(session_record, "error_message", None)
                or event_state["latest_failure_payload"].get("message")
                or "执行失败",
                retryable_step="finalize_plan",
            )
            return

        execution_order: list[AgentStepId] = [
            "create_task",
            "search_assets",
            "prepare_assets",
            "render_video",
        ]
        failed_index = execution_order.index(failed_step_id)
        for index, step_id in enumerate(execution_order):
            if index < failed_index:
                self._mark_step_succeeded(steps_by_id, step_id, self._build_execution_result(step_id, session_record, event_rows, event_state))
            elif index == failed_index:
                self._mark_step_failed(
                    steps_by_id,
                    step_id,
                    message=getattr(session_record, "error_message", None)
                    or event_state["latest_failure_payload"].get("message")
                    or "执行失败",
                    retryable_step=failed_step_id,
                )

    def _normalize_retryable_step(self, retryable_step: str | None) -> Optional[AgentStepId]:
        if retryable_step in {"create_task", "search_assets", "prepare_assets", "render_video"}:
            return retryable_step
        if retryable_step:
            return RETRYABLE_STEP_TO_AGENT_STEP.get(retryable_step)
        return None

    def _build_create_task_result(self, session_record, event_state: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        job_id = ""
        if session_record is not None and getattr(session_record, "active_job_id", None):
            job_id = session_record.active_job_id
        elif event_state["latest_job_id"]:
            job_id = event_state["latest_job_id"]
        if job_id:
            result["jobId"] = job_id
        if session_record is not None and getattr(session_record, "status", None):
            result["status"] = session_record.status
        return result

    def _build_search_assets_result(self, event_rows) -> dict[str, Any]:
        payload = self._latest_event_payload(event_rows, "searching")
        return dict(payload)

    def _build_prepare_assets_result(self, event_rows) -> dict[str, Any]:
        payload = self._latest_event_payload(event_rows, "downloading")
        return dict(payload)

    def _build_render_result(self, session_record, event_rows, event_state: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        video_url = event_state["latest_video_url"]
        if not video_url and session_record is not None and getattr(session_record, "video_url", None):
            video_url = session_record.video_url
        if not video_url:
            payload = self._latest_event_payload(event_rows, "done")
            video_url = payload.get("videoUrl", "")
        if video_url:
            result["videoUrl"] = video_url
        return result

    def _apply_task_artifacts(self, steps_by_id: list[AgentStep], artifact_rows, current_step_id: Optional[AgentStepId]) -> None:
        if current_step_id is None:
            return

        if current_step_id not in {"search_assets", "prepare_assets", "render_video"}:
            return

        if current_step_id in {"prepare_assets", "render_video"}:
            self._set_step_succeeded(steps_by_id, "create_task")

        if current_step_id == "prepare_assets":
            self._set_step_succeeded(steps_by_id, "search_assets")

        if current_step_id == "render_video":
            self._set_step_succeeded(steps_by_id, "search_assets")
            self._set_step_succeeded(steps_by_id, "prepare_assets", self._build_task_clips_result(artifact_rows))
            self._set_step_running(steps_by_id, "render_video")

    def _set_step_succeeded(self, steps: list[AgentStep], step_id: AgentStepId, result: Optional[dict[str, Any]] = None) -> None:
        for index, step in enumerate(steps):
            if step.id == step_id:
                steps[index] = self._build_succeeded_step(self._meta(step_id), result or {}, summary="已完成")
                return

    def _set_step_running(self, steps: list[AgentStep], step_id: AgentStepId) -> None:
        for index, step in enumerate(steps):
            if step.id == step_id:
                meta = self._meta(step_id)
                steps[index] = AgentStep(
                    id=meta.id,
                    title=meta.title,
                    description=meta.description,
                    status="running",
                    progress=50.0,
                    summary="执行中",
                )
                return

    def _build_task_clips_result(self, artifact_rows) -> dict[str, Any]:
        clips: list[dict[str, Any]] = []
        for row in artifact_rows:
            if getattr(row, "artifact_type", None) != "clip":
                continue
            metadata = getattr(row, "metadata_json", None) or {}
            clips.append(
                {
                    "sceneId": int(row.scene_id) if row.scene_id is not None and str(row.scene_id).isdigit() else 0,
                    "sourceUrl": row.source_url or "",
                    "localPath": row.local_path or "",
                    "publicUrl": row.public_url or "",
                    "caption": metadata.get("caption", "") or "",
                    "startTime": 0.0,
                    "duration": row.duration or 0.0,
                    "sourceDuration": float(metadata.get("sourceDuration", 0.0) or 0.0),
                    "trimStart": float(metadata.get("trimStart", 0.0) or 0.0),
                    "trimDuration": float(metadata.get("trimDuration", row.duration or 0.0) or 0.0),
                }
            )
        return {"clips": clips}

    def _build_execution_result(
        self,
        step_id: AgentStepId,
        session_record,
        event_rows,
        event_state: dict[str, Any],
    ) -> dict[str, Any]:
        if step_id == "create_task":
            return self._build_create_task_result(session_record, event_state)
        if step_id == "search_assets":
            return self._build_search_assets_result(event_rows)
        if step_id == "prepare_assets":
            return self._build_prepare_assets_result(event_rows)
        if step_id == "render_video":
            return self._build_render_result(session_record, event_rows, event_state)
        return {}

    def _latest_event_payload(self, event_rows, target_step: str) -> dict[str, Any]:
        for row in reversed(event_rows):
            if getattr(row, "step", None) != target_step:
                continue
            payload = getattr(row, "payload_json", None)
            if isinstance(payload, dict):
                return payload
            return {}
        return {}

    def _mark_step_succeeded(self, steps_by_id: dict[AgentStepId, AgentStep], step_id: AgentStepId, result: dict[str, Any]) -> None:
        steps_by_id[step_id] = self._build_succeeded_step(self._meta(step_id), result, summary="已完成")

    def _mark_step_running(self, steps_by_id: dict[AgentStepId, AgentStep], step_id: AgentStepId) -> None:
        meta = self._meta(step_id)
        steps_by_id[step_id] = AgentStep(
            id=meta.id,
            title=meta.title,
            description=meta.description,
            status="running",
            progress=50.0,
            summary="执行中",
        )

    def _mark_step_failed(
        self,
        steps_by_id: dict[AgentStepId, AgentStep],
        step_id: AgentStepId,
        message: str,
        retryable_step: AgentStepId,
    ) -> None:
        steps_by_id[step_id] = self._build_failed_step(self._meta(step_id), message=message, retryable_step=retryable_step)

    def _meta(self, step_id: AgentStepId) -> StepMeta:
        for meta in STANDARD_STEPS:
            if meta.id == step_id:
                return meta
        raise KeyError(step_id)

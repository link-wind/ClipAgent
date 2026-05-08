from dataclasses import dataclass
from typing import Any, Optional

from backend.models.agent import AgentStep, AgentStepError, AgentStepId, EditPlan
from backend.services.planner_projection import execution_plan_to_edit_plan


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
        grounding = self._extract_grounding(session_record)
        event_state = self._build_event_state(session_record, event_rows)

        steps_by_id = {meta.id: self._build_pending_step(meta) for meta in STANDARD_STEPS}

        if first_prompt is not None:
            steps_by_id["understand_request"] = self._build_understand_request_step(first_prompt)

        if grounding is not None:
            steps_by_id["extract_requirements"] = self._build_succeeded_step(
                self._meta("extract_requirements"),
                self._build_grounding_requirements_result(first_prompt, grounding),
                summary="已提炼需求",
            )
            steps_by_id["generate_options"] = self._build_succeeded_step(
                self._meta("generate_options"),
                self._build_grounding_generate_options_result(grounding),
                summary="已生成候选方向",
            )

        if plan is not None:
            requirements_result = self._build_requirements_result(first_prompt, plan, grounding)
            steps_by_id["extract_requirements"] = self._build_succeeded_step(
                self._meta("extract_requirements"),
                requirements_result,
                summary="已提炼需求",
            )
            steps_by_id["generate_options"] = self._build_succeeded_step(
                self._meta("generate_options"),
                self._build_generate_options_result(plan, grounding),
                summary="已生成方案",
            )
            steps_by_id["finalize_plan"] = self._build_succeeded_step(
                self._meta("finalize_plan"),
                self._build_finalize_plan_result(plan, grounding),
                summary="已确认计划",
            )

        self._apply_execution_state(steps_by_id, session_record, event_rows, event_state)

        return [steps_by_id[meta.id] for meta in STANDARD_STEPS]

    def build_task_steps(self, session_record, job_record, plan_row, artifact_rows, event_rows) -> list[AgentStep]:
        steps_by_id = {meta.id: self._build_pending_step(meta) for meta in STANDARD_STEPS}
        plan = self._extract_plan(plan_row)
        grounding = self._extract_grounding(session_record)
        first_prompt = None
        if plan is not None:
            requirements_result = self._build_requirements_result(first_prompt, plan, grounding)
            steps_by_id["extract_requirements"] = self._build_succeeded_step(
                self._meta("extract_requirements"),
                requirements_result,
                summary="已提炼需求",
            )
            steps_by_id["generate_options"] = self._build_succeeded_step(
                self._meta("generate_options"),
                self._build_generate_options_result(plan, grounding),
                summary="已生成方案",
            )
            steps_by_id["finalize_plan"] = self._build_succeeded_step(
                self._meta("finalize_plan"),
                self._build_finalize_plan_result(plan, grounding),
                summary="已确认计划",
            )
        task_state = self._build_task_state(job_record, artifact_rows, event_rows)
        self._apply_task_state(steps_by_id, task_state)
        return [steps_by_id[meta.id] for meta in STANDARD_STEPS]

    def resolve_current_step_id(self, job_status: str, current_step: str) -> Optional[AgentStepId]:
        if job_status == "queued" or "入队" in current_step:
            return "create_task"
        if job_status in {"succeeded", "failed"}:
            return "render_video"
        if job_status == "rendering" or "合成视频" in current_step:
            return "render_video"
        if job_status == "downloading" or "准备渲染" in current_step:
            return "prepare_assets"
        if job_status == "searching" or "搜索素材" in current_step or job_status == "running":
            return "search_assets"
        return None

    def _build_understand_request_step(self, prompt: str) -> AgentStep:
        return self._build_succeeded_step(
            self._meta("understand_request"),
            {"originalPrompt": prompt},
            summary="已读取原始需求",
        )

    def _build_requirements_result(
        self,
        prompt: Optional[str],
        plan: EditPlan,
        grounding: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return {
            "originalPrompt": prompt or "",
            "title": plan.title,
            "targetDuration": plan.targetDuration,
            "style": plan.style,
            "sceneCount": len(plan.scenes),
            "productName": (grounding or {}).get("productName", ""),
            "audience": (grounding or {}).get("audience", ""),
            "featureHints": (grounding or {}).get("featureHints", []) or [],
        }

    def _build_generate_options_result(
        self,
        plan: EditPlan,
        grounding: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        result = {
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
        if grounding is not None:
            result["status"] = grounding.get("status", "confirmed")
            result["selectedCandidateIds"] = grounding.get("selectedCandidateIds", []) or []
            result["candidates"] = grounding.get("candidates", []) or []
        return result

    def _build_finalize_plan_result(
        self,
        plan: EditPlan,
        grounding: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        result = {
            "title": plan.title,
            "targetDuration": plan.targetDuration,
            "style": plan.style,
            "scenes": [scene.model_dump(mode="json") for scene in plan.scenes],
        }
        if grounding is not None:
            result["selectedCandidateIds"] = grounding.get("selectedCandidateIds", []) or []
        return result

    def _extract_grounding(self, session_record) -> Optional[dict[str, Any]]:
        if session_record is None:
            return None
        grounding_summary = getattr(session_record, "grounding_summary_json", None) or {}
        grounding_status = getattr(session_record, "grounding_status", None)
        selected_candidate_ids = getattr(session_record, "selected_candidate_ids_json", None) or []
        if not grounding_summary and not grounding_status and not selected_candidate_ids:
            return None
        return {
            **grounding_summary,
            "status": grounding_status or grounding_summary.get("status", "pending_search"),
            "selectedCandidateIds": selected_candidate_ids or grounding_summary.get("selectedCandidateIds", []) or [],
        }

    def _build_grounding_requirements_result(
        self,
        prompt: Optional[str],
        grounding: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "originalPrompt": prompt or "",
            "productName": grounding.get("productName", ""),
            "audience": grounding.get("audience", ""),
            "style": grounding.get("styleHint", "") or "",
            "featureHints": grounding.get("featureHints", []) or [],
            "searchQueries": grounding.get("searchQueries", []) or [],
            "candidateCount": len(grounding.get("candidates", []) or []),
        }

    def _build_grounding_generate_options_result(self, grounding: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": grounding.get("status", "pending_search"),
            "productName": grounding.get("productName", ""),
            "selectedCandidateIds": grounding.get("selectedCandidateIds", []) or [],
            "candidates": grounding.get("candidates", []) or [],
            "options": grounding.get("candidates", []) or [],
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
        execution_plan_json = getattr(plan_row, "execution_plan_json", None) or {}
        if execution_plan_json.get("scenes"):
            return execution_plan_to_edit_plan(execution_plan_json)
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
        return self.normalize_retryable_step(retryable_step)

    def normalize_retryable_step(self, retryable_step: str | None) -> Optional[AgentStepId]:
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

    def _build_task_state(self, job_record, artifact_rows, event_rows) -> dict[str, Any]:
        status = getattr(job_record, "status", "")
        current_step_id = self.resolve_current_step_id(status, getattr(job_record, "current_step", "") or "")
        latest_job_event = self._latest_job_event(event_rows)
        video_url = self._resolve_task_video_url(job_record, artifact_rows, event_rows)
        retryable_step = self._resolve_task_retryable_step(job_record, latest_job_event)
        return {
            "status": status,
            "progress": getattr(job_record, "progress", 0.0) or 0.0,
            "current_step_id": current_step_id,
            "current_step": getattr(job_record, "current_step", "") or "",
            "latest_job_event": latest_job_event,
            "video_url": video_url,
            "retryable_step": retryable_step,
            "artifact_rows": artifact_rows,
            "job_record": job_record,
        }

    def _apply_task_state(self, steps_by_id: list[AgentStep], task_state: dict[str, Any]) -> None:
        status = task_state["status"]
        current_step_id = task_state["current_step_id"]
        artifact_rows = task_state["artifact_rows"]
        video_url = task_state["video_url"]
        retryable_step = task_state["retryable_step"]

        self._mark_step_succeeded(steps_by_id, "create_task", self._build_create_task_result_from_task_state(task_state))

        if status == "queued":
            return

        if status == "searching":
            self._mark_step_running(steps_by_id, "search_assets")
            return

        if status == "running" and current_step_id == "search_assets":
            self._mark_step_running(steps_by_id, "search_assets")
            return

        if status == "downloading":
            self._mark_step_succeeded(steps_by_id, "search_assets", self._build_search_assets_result_from_task_state(task_state))
            self._mark_step_running(steps_by_id, "prepare_assets")
            return

        if status == "running" and current_step_id == "prepare_assets":
            self._mark_step_succeeded(steps_by_id, "search_assets", self._build_search_assets_result_from_task_state(task_state))
            self._mark_step_running(steps_by_id, "prepare_assets")
            return

        if status == "rendering":
            self._mark_step_succeeded(steps_by_id, "search_assets", self._build_search_assets_result_from_task_state(task_state))
            self._mark_step_succeeded(
                steps_by_id,
                "prepare_assets",
                self._build_prepare_assets_result_from_task_state(task_state),
            )
            self._mark_step_running(steps_by_id, "render_video")
            return

        if status == "running" and current_step_id == "render_video":
            self._mark_step_succeeded(steps_by_id, "search_assets", self._build_search_assets_result_from_task_state(task_state))
            self._mark_step_succeeded(
                steps_by_id,
                "prepare_assets",
                self._build_prepare_assets_result_from_task_state(task_state),
            )
            self._mark_step_running(steps_by_id, "render_video")
            return

        if status == "succeeded":
            self._mark_step_succeeded(steps_by_id, "search_assets", self._build_search_assets_result_from_task_state(task_state))
            self._mark_step_succeeded(
                steps_by_id,
                "prepare_assets",
                self._build_prepare_assets_result_from_task_state(task_state),
            )
            self._mark_step_succeeded(
                steps_by_id,
                "render_video",
                self._build_task_render_result(video_url, artifact_rows, task_state["latest_job_event"]),
            )
            return

        if status == "failed":
            self._apply_failed_task_state(
                steps_by_id,
                retryable_step or "render_video",
                task_state,
            )

    def _apply_failed_task_state(
        self,
        steps_by_id: list[AgentStep],
        failed_step_id: AgentStepId,
        task_state: dict[str, Any],
    ) -> None:
        failed_step = failed_step_id if failed_step_id in {"create_task", "search_assets", "prepare_assets", "render_video"} else "render_video"
        execution_order: list[AgentStepId] = ["create_task", "search_assets", "prepare_assets", "render_video"]
        if failed_step == "render_video":
            self._mark_step_succeeded(steps_by_id, "search_assets", self._build_task_step_result("search_assets", task_state))
            self._mark_step_succeeded(
                steps_by_id,
                "prepare_assets",
                self._build_task_step_result("prepare_assets", task_state),
            )
        failed_index = execution_order.index(failed_step)
        for index, step_id in enumerate(execution_order):
            if index < failed_index:
                self._mark_step_succeeded(
                    steps_by_id,
                    step_id,
                    self._build_task_step_result(step_id, task_state),
                )
            elif index == failed_index:
                self._mark_step_failed(
                    steps_by_id,
                    step_id,
                    message=self._resolve_task_failure_message(task_state),
                    retryable_step=failed_step,
                )

    def _set_step_succeeded(self, steps: list[AgentStep], step_id: AgentStepId, result: Optional[dict[str, Any]] = None) -> None:
        for index, step in enumerate(steps):
            if step.id == step_id:
                steps[index] = self._build_succeeded_step(self._meta(step_id), result or {}, summary="已完成")
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

    def _build_create_task_result_from_task_state(self, task_state: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": task_state["status"],
            "progress": task_state["progress"],
        }
        if task_state["current_step"]:
            result["currentStep"] = task_state["current_step"]
        return result

    def _build_search_assets_result_from_task_state(self, task_state: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": task_state["status"],
            "progress": task_state["progress"],
        }
        return result

    def _build_prepare_assets_result_from_task_state(self, task_state: dict[str, Any]) -> dict[str, Any]:
        return self._build_task_clips_result(task_state["artifact_rows"])

    def _build_task_render_result(self, video_url: str, artifact_rows, latest_job_event) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if video_url:
            result["videoUrl"] = video_url
        clips = self._build_task_clips_result(artifact_rows)["clips"]
        if clips:
            result["clips"] = clips
        if latest_job_event:
            result["eventType"] = getattr(latest_job_event, "event_type", "")
        return result

    def _build_task_step_result(self, step_id: AgentStepId, task_state: dict[str, Any]) -> dict[str, Any]:
        if step_id == "create_task":
            return self._build_create_task_result_from_task_state(task_state)
        if step_id == "search_assets":
            return self._build_search_assets_result_from_task_state(task_state)
        if step_id == "prepare_assets":
            return self._build_prepare_assets_result_from_task_state(task_state)
        if step_id == "render_video":
            if task_state["status"] == "failed":
                return {}
            return self._build_task_render_result(task_state["video_url"], task_state["artifact_rows"], task_state["latest_job_event"])
        return {}

    def _latest_job_event(self, event_rows):
        for row in reversed(event_rows):
            if getattr(row, "job_id", None):
                return row
        return None

    def _resolve_task_video_url(self, job_record, artifact_rows, event_rows) -> str:
        for row in reversed(artifact_rows):
            if row.artifact_type == "video" and row.public_url:
                return row.public_url
        for row in reversed(event_rows):
            payload = row.payload_json or {}
            if payload.get("videoUrl"):
                return str(payload["videoUrl"])
        return getattr(job_record, "video_url", "") or ""

    def _resolve_task_retryable_step(self, job_record, latest_job_event) -> Optional[AgentStepId]:
        if getattr(job_record, "error_message", None):
            payload = getattr(latest_job_event, "payload_json", None) or {}
            retryable_step = payload.get("retryableStep") if isinstance(payload, dict) else None
            if retryable_step in {"create_task", "search_assets", "prepare_assets", "render_video"}:
                return retryable_step
            if retryable_step:
                return self._normalize_retryable_step(str(retryable_step))
            return self._normalize_retryable_step(getattr(job_record, "current_step", "") or "")
        return None

    def _resolve_task_failure_message(self, task_state: dict[str, Any]) -> str:
        job_record = task_state.get("job_record")
        if job_record is not None and getattr(job_record, "error_message", None):
            return job_record.error_message
        latest_job_event = task_state["latest_job_event"]
        if latest_job_event is not None:
            message = getattr(latest_job_event, "message", None)
            if message:
                return message
        return "执行失败"

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

from dataclasses import dataclass
from typing import Any, Optional

from backend.models.agent import AgentStep, AgentStepError, AgentStepId, AgentStepStatus, EditPlan


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

        if session_record is not None and getattr(session_record, "error_message", None):
            retryable_step = getattr(session_record, "error_retryable_step", None)
            mapped_step = RETRYABLE_STEP_TO_AGENT_STEP.get(retryable_step or "")
            if mapped_step in steps_by_id:
                steps_by_id[mapped_step] = self._build_failed_step(
                    self._meta(mapped_step),
                    message=session_record.error_message,
                    retryable_step=mapped_step,
                )

        latest_event_step = self._latest_event_step(event_rows)
        if latest_event_step in EVENT_STEP_TO_AGENT_STEP:
            mapped_step = EVENT_STEP_TO_AGENT_STEP[latest_event_step]
            if (
                session_record is not None
                and getattr(session_record, "status", None) == "failed"
                and mapped_step in steps_by_id
                and steps_by_id[mapped_step].status == "pending"
            ):
                steps_by_id[mapped_step] = self._build_failed_step(
                    self._meta(mapped_step),
                    message=session_record.error_message or "执行失败",
                    retryable_step=RETRYABLE_STEP_TO_AGENT_STEP.get(latest_event_step),
                )

        return [steps_by_id[meta.id] for meta in STANDARD_STEPS]

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

    def _latest_event_step(self, event_rows) -> str:
        for row in reversed(event_rows):
            if getattr(row, "step", None):
                return row.step
        return ""

    def _meta(self, step_id: AgentStepId) -> StepMeta:
        for meta in STANDARD_STEPS:
            if meta.id == step_id:
                return meta
        raise KeyError(step_id)

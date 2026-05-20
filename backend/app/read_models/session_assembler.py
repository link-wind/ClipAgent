from backend.app.execution.diagnostic_service import AgentDiagnosticService
from backend.app.planning.projection import execution_plan_to_edit_plan
from backend.app.read_models.step_assembler import StepReadModelAssembler
from backend.models.agent import (
    AgentError,
    AgentEvent,
    AgentGroundingCandidate,
    AgentGroundingSummary,
    AgentMessage,
    AgentSession,
    AgentStatus,
    AgentTaskDetail,
    ClipInfo,
    EditPlan,
)


class SessionReadModelAssembler:
    def __init__(
        self,
        step_assembler: StepReadModelAssembler | None = None,
        diagnostic_service: AgentDiagnosticService | None = None,
    ) -> None:
        self.step_assembler = step_assembler or StepReadModelAssembler()
        self.diagnostic_service = diagnostic_service or AgentDiagnosticService()

    def build_session(
        self,
        *,
        session_record,
        message_rows,
        plan_row,
        artifact_rows,
        event_rows,
        job_record=None,
        persisted_step_rows=None,
    ) -> AgentSession:
        plan = self._build_edit_plan(plan_row)
        clip_rows = [row for row in artifact_rows if row.artifact_type == "clip"]
        steps = self.step_assembler.build_session_steps(
            session_record=session_record,
            message_rows=message_rows,
            plan_row=plan_row,
            event_rows=event_rows,
            persisted_step_rows=persisted_step_rows or [],
        )
        return AgentSession(
            id=session_record.id,
            status=AgentStatus(session_record.status),
            messages=[
                AgentMessage(
                    id=row.id,
                    role=row.role,
                    content=row.content,
                    createdAt=row.created_at.isoformat(),
                )
                for row in message_rows
            ],
            plan=plan,
            currentPlanVersion=getattr(plan_row, "version", None),
            clips=[self.build_clip_info(row) for row in clip_rows],
            events=self.build_event_response(event_rows),
            steps=steps,
            videoUrl=session_record.video_url,
            activeJobId=session_record.active_job_id,
            grounding=self._build_grounding_response(session_record),
            plannerTrace=session_record.planner_trace_json or {},
            diagnostic=(
                self.diagnostic_service.build_diagnostic(
                    session_record=session_record,
                    job_record=job_record,
                    event_rows=event_rows,
                )
                if self._should_include_session_diagnostic(session_record, job_record)
                else None
            ),
            error=(
                AgentError(
                    message=session_record.error_message,
                    retryableStep=session_record.error_retryable_step,
                )
                if session_record.error_message
                else None
            ),
            progress=session_record.progress,
            currentStep=session_record.current_step or "",
        )

    def build_task_detail(
        self,
        *,
        summary,
        job_record,
        session_record,
        plan_row,
        artifact_rows,
        event_rows,
        video_url,
        retryable_step,
    ) -> AgentTaskDetail:
        clip_rows = [row for row in artifact_rows if row.artifact_type == "clip"]
        return AgentTaskDetail(
            **summary.model_dump(),
            events=self.build_event_response(event_rows),
            clips=[self.build_clip_info(row) for row in clip_rows],
            diagnostic=self.diagnostic_service.build_diagnostic(
                session_record=session_record,
                job_record=job_record,
                event_rows=event_rows,
            ),
            steps=self.step_assembler.build_task_steps(
                session_record=session_record,
                job_record=job_record,
                plan_row=plan_row,
                artifact_rows=artifact_rows,
                event_rows=event_rows,
            ),
            error=(
                AgentError(
                    message=job_record.error_message,
                    retryableStep=retryable_step,
                )
                if job_record.error_message
                else None
            ),
            videoUrl=video_url,
        )

    def build_event_response(self, event_rows) -> list[AgentEvent]:
        return [
            AgentEvent(
                id=row.id,
                eventType=row.event_type,
                step=row.step,
                progress=row.progress,
                message=row.message,
                payload=row.payload_json or {},
                createdAt=row.created_at.isoformat(),
            )
            for row in event_rows
        ]

    def build_clip_info(self, row) -> ClipInfo:
        metadata = row.metadata_json or {}
        return ClipInfo(
            sceneId=int(row.scene_id) if row.scene_id is not None and str(row.scene_id).isdigit() else 0,
            sourceUrl=row.source_url or "",
            localPath=row.local_path or "",
            publicUrl=row.public_url or "",
            caption=metadata.get("caption", "") or "",
            duration=row.duration or 0.0,
            sourceDuration=float(metadata.get("sourceDuration", 0.0) or 0.0),
            trimStart=float(metadata.get("trimStart", 0.0) or 0.0),
            trimDuration=float(metadata.get("trimDuration", row.duration or 0.0) or 0.0),
        )

    def _should_include_session_diagnostic(self, session_record, job_record) -> bool:
        if getattr(session_record, "status", None) == "failed":
            return True
        if job_record is not None and getattr(job_record, "status", None) == "failed":
            return True
        return False

    def _build_grounding_response(self, session_record) -> AgentGroundingSummary | None:
        if not session_record.grounding_summary_json:
            return None

        grounding_json = self._normalize_grounding_json(session_record.grounding_summary_json or {})
        summary = AgentGroundingSummary.model_validate(grounding_json)
        return summary.model_copy(
            update={
                "status": session_record.grounding_status or summary.status,
                "selectedCandidateIds": (
                    session_record.selected_candidate_ids_json
                    or summary.selectedCandidateIds
                ),
                "candidates": [
                    AgentGroundingCandidate.model_validate(candidate)
                    for candidate in summary.candidates
                ],
            }
        )

    def _normalize_grounding_json(self, grounding_json: dict) -> dict:
        return {
            **grounding_json,
            "status": grounding_json.get("status") or "pending_search",
            "productName": grounding_json.get("productName") or "",
            "audience": grounding_json.get("audience") or "",
            "styleHint": grounding_json.get("styleHint") or "",
            "featureHints": grounding_json.get("featureHints") or [],
            "assumptions": grounding_json.get("assumptions") or [],
            "searchQueries": grounding_json.get("searchQueries") or [],
            "queryPlan": grounding_json.get("queryPlan") or [],
            "candidates": grounding_json.get("candidates") or [],
            "selectedCandidateIds": grounding_json.get("selectedCandidateIds") or [],
        }

    def _build_edit_plan(self, plan_row) -> EditPlan | None:
        if plan_row is None:
            return None

        execution_plan_json = getattr(plan_row, "execution_plan_json", None) or {}
        if execution_plan_json.get("scenes"):
            return execution_plan_to_edit_plan(execution_plan_json)
        return EditPlan.model_validate(plan_row.plan_json)

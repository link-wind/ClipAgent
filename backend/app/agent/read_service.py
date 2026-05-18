from backend.app.agent.step_projection_service import StepProjectionService
from backend.db.repositories import (
    AgentArtifactRepository,
    AgentEventRepository,
    AgentJobRepository,
    AgentMessageRepository,
    AgentPlanRepository,
    AgentSessionRepository,
    AgentStepRepository,
)
from backend.models.agent import (
    AgentError,
    AgentEvent,
    AgentGroundingCandidate,
    AgentGroundingSummary,
    AgentMessage,
    AgentSession,
    AgentStatus,
    ClipInfo,
    EditPlan,
)
from backend.app.planning.projection import execution_plan_to_edit_plan
from backend.services.agent_diagnostic_service import AgentDiagnosticService


class AgentReadService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.step_projection_service = StepProjectionService()
        self.diagnostic_service = AgentDiagnosticService()

    def read_session(self, session_id: str) -> AgentSession:
        # 读取并组装会话响应
        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            message_repo = AgentMessageRepository(db)
            session_record = session_repo.get(session_id)
            if session_record is None:
                raise KeyError(session_id)

            active_job_record = None
            if getattr(session_record, "active_job_id", None):
                active_job_record = AgentJobRepository(db).get(session_record.active_job_id)

            return self.build_session_response(
                session_record=session_record,
                message_rows=message_repo.list_for_session(session_id),
                plan_row=self.load_current_plan(db, session_record),
                artifact_rows=self.load_artifacts(db, session_id),
                event_rows=AgentEventRepository(db).list_for_session(session_id),
                persisted_step_rows=AgentStepRepository(db).list_for_session(session_id),
                job_record=active_job_record,
            )

    def load_current_plan(self, db_session, session_record):
        # 读取会话当前指针指向的计划
        current_plan_id = getattr(session_record, "current_plan_id", None)
        if not current_plan_id:
            return self.load_latest_plan(db_session, session_record.id)
        return AgentPlanRepository(db_session).get(current_plan_id)

    def load_latest_plan(self, db_session, session_id: str):
        # 兼容保留：按会话读取最新版本计划
        return AgentPlanRepository(db_session).get_latest_for_session(session_id)

    def load_artifacts(self, db_session, session_id: str):
        # 读取会话产物
        return AgentArtifactRepository(db_session).list_for_session(session_id)

    def load_events(self, db_session, session_id: str):
        # 读取会话事件
        return AgentEventRepository(db_session).list_for_session(session_id)

    def read_events(self, session_id: str) -> list[AgentEvent]:
        # 读取并映射事件列表
        with self.session_factory() as db:
            session_record = AgentSessionRepository(db).get(session_id)
            if session_record is None:
                raise KeyError(session_id)
            return self.build_event_response(self.load_events(db, session_id))

    def build_session_response(
        self,
        session_record,
        message_rows,
        plan_row,
        artifact_rows,
        event_rows,
        job_record=None,
        persisted_step_rows=None,
    ) -> AgentSession:
        # 将数据库行映射回 Pydantic 会话
        plan = self._build_edit_plan(plan_row)
        clip_rows = [row for row in artifact_rows if row.artifact_type == "clip"]
        steps = self.step_projection_service.build_session_steps(
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
            clips=[
                self._build_clip_info(row)
                for row in clip_rows
            ],
            events=[
                event
                for event in self.build_event_response(event_rows)
            ],
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

    def _build_clip_info(self, row) -> ClipInfo:
        # 从产物记录恢复片段信息
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

    def build_event_response(self, event_rows) -> list[AgentEvent]:
        # 将数据库事件映射回 Pydantic 结构
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

    def _build_edit_plan(self, plan_row) -> EditPlan | None:
        if plan_row is None:
            return None

        execution_plan_json = getattr(plan_row, "execution_plan_json", None) or {}
        if execution_plan_json.get("scenes"):
            return execution_plan_to_edit_plan(execution_plan_json)
        return EditPlan.model_validate(plan_row.plan_json)

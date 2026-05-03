from backend.db.repositories import (
    AgentArtifactRepository,
    AgentEventRepository,
    AgentMessageRepository,
    AgentPlanRepository,
    AgentSessionRepository,
)
from backend.models.agent import AgentError, AgentEvent, AgentMessage, AgentSession, AgentStatus, ClipInfo, EditPlan


class AgentReadService:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def read_session(self, session_id: str) -> AgentSession:
        # 读取并组装会话响应
        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            message_repo = AgentMessageRepository(db)
            session_record = session_repo.get(session_id)
            if session_record is None:
                raise KeyError(session_id)

            return self.build_session_response(
                session_record=session_record,
                message_rows=message_repo.list_for_session(session_id),
                plan_row=self.load_latest_plan(db, session_id),
                artifact_rows=self.load_artifacts(db, session_id),
                event_rows=AgentEventRepository(db).list_for_session(session_id),
            )

    def load_latest_plan(self, db_session, session_id: str):
        # 读取最新计划
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

    def build_session_response(self, session_record, message_rows, plan_row, artifact_rows, event_rows) -> AgentSession:
        # 将数据库行映射回 Pydantic 会话
        plan = EditPlan.model_validate(plan_row.plan_json) if plan_row is not None else None
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
            clips=[
                ClipInfo(
                    sceneId=int(row.scene_id) if row.scene_id is not None and str(row.scene_id).isdigit() else 0,
                    sourceUrl=row.source_url or "",
                    localPath=row.local_path or "",
                    publicUrl=row.public_url or "",
                    duration=row.duration or 0.0,
                )
                for row in artifact_rows
            ],
            events=[
                event
                for event in self.build_event_response(event_rows)
            ],
            videoUrl=session_record.video_url,
            activeJobId=session_record.active_job_id,
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

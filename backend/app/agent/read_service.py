from backend.app.read_models.session_assembler import SessionReadModelAssembler
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
    AgentEvent,
    AgentSession,
)


class AgentReadService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.session_assembler = SessionReadModelAssembler()

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

            return self.session_assembler.build_session(
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
            return self.session_assembler.build_event_response(self.load_events(db, session_id))

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
        return self.session_assembler.build_session(
            session_record=session_record,
            message_rows=message_rows,
            plan_row=plan_row,
            artifact_rows=artifact_rows,
            event_rows=event_rows,
            job_record=job_record,
            persisted_step_rows=persisted_step_rows,
        )

    def build_event_response(self, event_rows) -> list[AgentEvent]:
        return self.session_assembler.build_event_response(event_rows)

    def _build_clip_info(self, row):
        return self.session_assembler.build_clip_info(row)

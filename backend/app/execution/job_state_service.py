from datetime import datetime

from backend.app.execution.event_service import ExecutionEventService
from backend.app.execution.step_lifecycle import StepLifecycleService
from backend.db.repositories import AgentJobRepository, AgentSessionRepository


class JobStateService:
    def __init__(self, db_session):
        self.job_repo = AgentJobRepository(db_session)
        self.session_repo = AgentSessionRepository(db_session)
        self.event_service = ExecutionEventService(db_session)
        self.step_lifecycle = StepLifecycleService(db_session)

    def mark_job_running(self, *, session_id: str, job_id: str):
        self.job_repo.update_status(
            job_id,
            status="running",
            progress=35,
            current_step="正在搜索素材",
            started_at=datetime.utcnow(),
            error_message=None,
        )
        session_record = self.session_repo.get(session_id)
        session_record.status = "searching"
        session_record.progress = 35
        session_record.current_step = "正在搜索素材"
        session_record.error_message = None
        session_record.error_retryable_step = None
        self.event_service.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="job_started",
            step="searching",
            message="任务开始执行",
            progress=35,
        )
        self.step_lifecycle.ensure_step(
            session_id=session_id,
            job_id=job_id,
            step_key="search_assets",
            title="搜索素材",
            description="根据最终方案搜索候选素材并记录搜索结果。",
            sequence=6,
        )

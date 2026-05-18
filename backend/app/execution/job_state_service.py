from datetime import datetime

from backend.db.repositories import AgentJobRepository, AgentSessionRepository


class JobStateService:
    def __init__(self, db_session):
        self.job_repo = AgentJobRepository(db_session)
        self.session_repo = AgentSessionRepository(db_session)

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

from backend.db.repositories import AgentEventRepository


class ExecutionEventService:
    def __init__(self, db_session):
        self.event_repo = AgentEventRepository(db_session)

    def record_event(
        self,
        *,
        session_id: str,
        job_id: str,
        event_type: str,
        step: str,
        message: str,
        progress: float | None = None,
        payload: dict | None = None,
    ):
        return self.event_repo.create(
            session_id=session_id,
            job_id=job_id,
            event_type=event_type,
            step=step,
            progress=progress,
            message=message,
            payload_json=payload or None,
        )

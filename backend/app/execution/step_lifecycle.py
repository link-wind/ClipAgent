from backend.app.agent.step_service import AgentStepService
from backend.db.repositories import AgentStepRepository


class StepLifecycleService:
    def __init__(self, db_session):
        self.step_repo = AgentStepRepository(db_session)
        self.step_service = AgentStepService(db_session)

    def ensure_step(
        self,
        *,
        session_id: str,
        job_id: str,
        step_key: str,
        title: str,
        description: str,
        sequence: int,
    ):
        existing = self.step_repo.get_for_job_step(job_id, step_key)
        if existing is not None:
            return existing

        return self.step_service.start_step(
            session_id=session_id,
            job_id=job_id,
            step_key=step_key,
            title=title,
            description=description,
            sequence=sequence,
            actor_role="executor",
        )

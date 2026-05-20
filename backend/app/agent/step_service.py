from backend.db.repositories import AgentStepRepository, AgentTraceEventRepository
from backend.models.agent import AgentStep, AgentStepError
from backend.utils.time import utc_now_naive


class AgentStepService:
    def __init__(self, db_session):
        self.db = db_session
        self.step_repo = AgentStepRepository(db_session)
        self.trace_repo = AgentTraceEventRepository(db_session)

    def start_step(
        self,
        *,
        session_id: str,
        step_key: str,
        title: str,
        description: str,
        sequence: int,
        run_id: str | None = None,
        job_id: str | None = None,
        actor_role: str = "planner",
    ):
        step = self.step_repo.create(
            session_id=session_id,
            run_id=run_id,
            job_id=job_id,
            step_key=step_key,
            title=title,
            description=description,
            status="running",
            progress=0,
            sequence=sequence,
            actor_role=actor_role,
            started_at=utc_now_naive(),
        )
        self.trace_repo.create(
            session_id=session_id,
            run_id=run_id,
            step_id=step.id,
            job_id=job_id,
            event_type="step_started",
            message=title,
            actor_type=step.actor_type,
            actor_role=step.actor_role,
            actor_id=step.actor_id,
            agent_name=step.agent_name,
        )
        return step

    def succeed_step(self, step_id: str, summary: str = "", result: dict | None = None):
        step = self.step_repo.update_status(
            step_id,
            status="succeeded",
            progress=100,
            summary=summary,
            result_json=result or {},
            finished_at=utc_now_naive(),
        )
        if step is None:
            return None

        self.trace_repo.create(
            session_id=step.session_id,
            run_id=step.run_id,
            step_id=step.id,
            job_id=step.job_id,
            event_type="step_succeeded",
            message=summary or step.title,
            actor_type=step.actor_type,
            actor_role=step.actor_role,
            actor_id=step.actor_id,
            agent_name=step.agent_name,
        )
        return step

    def fail_step(
        self,
        step_id: str,
        message: str,
        retryable: bool = False,
        retryable_step: str | None = None,
    ):
        error = {
            "message": message,
            "retryable": retryable,
            "retryableStep": retryable_step,
        }
        step = self.step_repo.update_status(
            step_id,
            status="failed",
            error_json=error,
            finished_at=utc_now_naive(),
        )
        if step is None:
            return None

        self.trace_repo.create(
            session_id=step.session_id,
            run_id=step.run_id,
            step_id=step.id,
            job_id=step.job_id,
            event_type="step_failed",
            level="error",
            message=message,
            payload_json=error,
            actor_type=step.actor_type,
            actor_role=step.actor_role,
            actor_id=step.actor_id,
            agent_name=step.agent_name,
        )
        return step

    def to_api_step(self, record) -> AgentStep:
        error_json = record.error_json or None
        return AgentStep(
            id=record.step_key,
            title=record.title,
            description=record.description,
            status=record.status,
            progress=record.progress,
            summary=record.summary or "",
            result=record.result_json or None,
            error=AgentStepError.model_validate(error_json) if error_json else None,
            startedAt=record.started_at.isoformat() if record.started_at else None,
            finishedAt=record.finished_at.isoformat() if record.finished_at else None,
        )

from backend.db.repositories import (
    AgentRunRepository,
    AgentSessionRepository,
    AgentTraceEventRepository,
)
from backend.utils.time import utc_now_naive


class ActiveOperationConflict(RuntimeError):
    def __init__(self, operation_type: str, operation_id: str):
        super().__init__("Session has an active operation")
        self.operation_type = operation_type
        self.operation_id = operation_id


class AgentRunService:
    def __init__(self, db_session):
        self.db = db_session
        self.session_repo = AgentSessionRepository(db_session)
        self.run_repo = AgentRunRepository(db_session)
        self.trace_repo = AgentTraceEventRepository(db_session)

    def start_run(self, session_id: str, trigger_type: str, **values):
        run = self.run_repo.create(
            session_id=session_id,
            trigger_type=trigger_type,
            status="running",
            started_at=utc_now_naive(),
            **values,
        )
        if not self.session_repo.try_start_operation(session_id, "run", run.id):
            active_session = self.session_repo.get(session_id)
            raise ActiveOperationConflict(
                getattr(active_session, "active_operation_type", "unknown"),
                getattr(active_session, "active_operation_id", None) or "",
            )

        self.trace_repo.create(
            session_id=session_id,
            run_id=run.id,
            event_type="run_started",
            message="Agent run started",
            actor_type=run.actor_type,
            actor_role=run.actor_role,
            actor_id=run.actor_id,
            agent_name=run.agent_name,
        )
        return run

    def succeed_run(self, run_id: str, summary: str = "", output: dict | None = None):
        current = self.run_repo.get(run_id)
        merged_output = {
            **(current.output_json or {}),
            **(output or {}),
        } if current is not None else (output or {})
        run = self.run_repo.update_status(
            run_id,
            status="succeeded",
            summary=summary,
            output_json=merged_output,
            finished_at=utc_now_naive(),
        )
        if run is None:
            return None

        self.trace_repo.create(
            session_id=run.session_id,
            run_id=run.id,
            event_type="run_succeeded",
            message=summary or "Agent run succeeded",
            actor_type=run.actor_type,
            actor_role=run.actor_role,
            actor_id=run.actor_id,
            agent_name=run.agent_name,
        )
        self.session_repo.finish_operation(run.session_id, "run", run.id)
        return run

    def fail_run(self, run_id: str, message: str):
        run = self.run_repo.update_status(
            run_id,
            status="failed",
            error_message=message,
            finished_at=utc_now_naive(),
        )
        if run is None:
            return None

        self.trace_repo.create(
            session_id=run.session_id,
            run_id=run.id,
            event_type="run_failed",
            level="error",
            message=message,
            actor_type=run.actor_type,
            actor_role=run.actor_role,
            actor_id=run.actor_id,
            agent_name=run.agent_name,
        )
        self.session_repo.fail_operation(run.session_id, "run", run.id, message)
        return run

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TraceEvent:
    session_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    run_id: str | None = None
    step_id: str | None = None
    job_id: str | None = None
    level: str = "info"
    message: str | None = None
    actor_type: str = "agent"
    actor_role: str = "planner"
    actor_id: str | None = None
    agent_name: str | None = "clipforge_agent"


class TraceRecorder:
    def __init__(self, db_session=None):
        self.db = db_session

    def record(self, event: TraceEvent) -> None:
        if self.db is None:
            return None

        from backend.db.repositories import AgentTraceEventRepository

        message = event.message
        if message is None and isinstance(event.payload, dict):
            raw_message = event.payload.get("message")
            message = raw_message if isinstance(raw_message, str) else None

        AgentTraceEventRepository(self.db).create(
            session_id=event.session_id,
            run_id=event.run_id,
            step_id=event.step_id,
            job_id=event.job_id,
            event_type=event.event_type,
            level=event.level,
            message=message,
            payload_json=event.payload,
            actor_type=event.actor_type,
            actor_role=event.actor_role,
            actor_id=event.actor_id,
            agent_name=event.agent_name,
        )
        return None

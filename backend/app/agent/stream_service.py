import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.app.read_models.trace_assembler import TraceReadModelAssembler
from backend.db.models import AgentSessionRecord, AgentTraceEventRecord
from backend.db.repositories import AgentSessionRepository, AgentTraceEventRepository
from backend.models.agent import AgentTraceEvent


TERMINAL_SESSION_STATUSES = {"done", "failed"}


@dataclass(frozen=True)
class TraceBatch:
    events: list[AgentTraceEvent]
    last_sequence: int


def format_sse_event(event_name: str, payload: dict[str, Any], event_id: int | None = None) -> str:
    if event_id is None:
        sequence = payload.get("sequence")
        if sequence is not None:
            event_id = sequence

    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_name}")

    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    for line in data.splitlines() or [""]:
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"


def trace_record_to_model(record: AgentTraceEventRecord) -> AgentTraceEvent:
    return TraceReadModelAssembler().build_trace_events([record])[0]


class AgentStreamService:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.session_repo = AgentSessionRepository(db_session)
        self.trace_repo = AgentTraceEventRepository(db_session)
        self.trace_assembler = TraceReadModelAssembler()

    def require_session(self, session_id: str) -> AgentSessionRecord:
        session = self.session_repo.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def read_trace_batch(self, session_id: str, after_sequence: int, limit: int = 50) -> TraceBatch:
        records = self.trace_repo.list_for_session(
            session_id,
            after_sequence=after_sequence,
            limit=limit,
        )
        events = self.trace_assembler.build_trace_events(records)
        last_sequence = after_sequence
        if events:
            last_sequence = max(event.sequence for event in events)
        return TraceBatch(events=events, last_sequence=last_sequence)

    def should_close_stream(self, session_id: str) -> bool:
        session = self.require_session(session_id)
        return (
            session.status in TERMINAL_SESSION_STATUSES
            and session.active_operation_type == "none"
            and session.active_operation_id is None
        )

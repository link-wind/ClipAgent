from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.models import AgentTraceEventRecord


class AgentTraceEventRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, **values) -> AgentTraceEventRecord:
        if values.get("payload_json") is None:
            values["payload_json"] = {}
        if values.get("sequence") is None:
            values["sequence"] = self.next_sequence(values["session_id"])

        record = AgentTraceEventRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get(self, trace_event_id: str) -> AgentTraceEventRecord | None:
        return self.db.get(AgentTraceEventRecord, trace_event_id)

    def next_sequence(self, session_id: str) -> int:
        stmt = (
            select(func.max(AgentTraceEventRecord.sequence))
            .where(AgentTraceEventRecord.session_id == session_id)
        )
        return int(self.db.scalar(stmt) or 0) + 1

    def list_for_session(
        self,
        session_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[AgentTraceEventRecord]:
        stmt = (
            select(AgentTraceEventRecord)
            .where(AgentTraceEventRecord.session_id == session_id)
            .order_by(AgentTraceEventRecord.sequence.asc(), AgentTraceEventRecord.id.asc())
        )
        if after_sequence is not None:
            stmt = stmt.where(AgentTraceEventRecord.sequence > after_sequence)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt))

    def list_for_run(self, run_id: str) -> list[AgentTraceEventRecord]:
        stmt = (
            select(AgentTraceEventRecord)
            .where(AgentTraceEventRecord.run_id == run_id)
            .order_by(AgentTraceEventRecord.sequence.asc(), AgentTraceEventRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

    def list_for_step(self, step_id: str) -> list[AgentTraceEventRecord]:
        stmt = (
            select(AgentTraceEventRecord)
            .where(AgentTraceEventRecord.step_id == step_id)
            .order_by(AgentTraceEventRecord.sequence.asc(), AgentTraceEventRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

    def list_for_job(self, job_id: str) -> list[AgentTraceEventRecord]:
        stmt = (
            select(AgentTraceEventRecord)
            .where(AgentTraceEventRecord.job_id == job_id)
            .order_by(AgentTraceEventRecord.sequence.asc(), AgentTraceEventRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import AgentStepRecord


class AgentStepRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, **values) -> AgentStepRecord:
        if values.get("result_json") is None:
            values["result_json"] = None
        if values.get("error_json") is None:
            values["error_json"] = None

        record = AgentStepRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get(self, step_id: str) -> AgentStepRecord | None:
        return self.db.get(AgentStepRecord, step_id)

    def list_for_session(self, session_id: str) -> list[AgentStepRecord]:
        stmt = (
            select(AgentStepRecord)
            .where(AgentStepRecord.session_id == session_id)
            .order_by(AgentStepRecord.sequence.asc(), AgentStepRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

    def list_for_run(self, run_id: str) -> list[AgentStepRecord]:
        stmt = (
            select(AgentStepRecord)
            .where(AgentStepRecord.run_id == run_id)
            .order_by(AgentStepRecord.sequence.asc(), AgentStepRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

    def list_for_job(self, job_id: str) -> list[AgentStepRecord]:
        stmt = (
            select(AgentStepRecord)
            .where(AgentStepRecord.job_id == job_id)
            .order_by(AgentStepRecord.sequence.asc(), AgentStepRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

    def get_for_job_step(self, job_id: str, step_key: str) -> AgentStepRecord | None:
        stmt = (
            select(AgentStepRecord)
            .where(AgentStepRecord.job_id == job_id, AgentStepRecord.step_key == step_key)
            .order_by(AgentStepRecord.created_at.asc(), AgentStepRecord.id.asc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def update_status(
        self,
        step_id: str,
        *,
        status: str,
        progress: float | None = None,
        summary: str | None = None,
        result_json: dict | None = None,
        error_json: dict | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> AgentStepRecord | None:
        record = self.get(step_id)
        if record is None:
            return None

        record.status = status
        if progress is not None:
            record.progress = progress
        if summary is not None:
            record.summary = summary
        if result_json is not None:
            record.result_json = result_json
        if error_json is not None:
            record.error_json = error_json
        if started_at is not None:
            record.started_at = started_at
        if finished_at is not None:
            record.finished_at = finished_at

        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import AgentRunRecord


class AgentRunRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, **values) -> AgentRunRecord:
        if values.get("input_json") is None:
            values["input_json"] = {}
        if values.get("output_json") is None:
            values["output_json"] = {}
        if values.get("metadata_json") is None:
            values["metadata_json"] = {}

        record = AgentRunRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get(self, run_id: str) -> AgentRunRecord | None:
        return self.db.get(AgentRunRecord, run_id)

    def list_for_session(self, session_id: str) -> list[AgentRunRecord]:
        stmt = (
            select(AgentRunRecord)
            .where(AgentRunRecord.session_id == session_id)
            .order_by(AgentRunRecord.created_at.asc(), AgentRunRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

    def list_children(self, parent_run_id: str) -> list[AgentRunRecord]:
        stmt = (
            select(AgentRunRecord)
            .where(AgentRunRecord.parent_run_id == parent_run_id)
            .order_by(AgentRunRecord.created_at.asc(), AgentRunRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

    def update_status(
        self,
        run_id: str,
        *,
        status: str,
        summary: str | None = None,
        error_message: str | None = None,
        output_json: dict | None = None,
        finished_at: datetime | None = None,
    ) -> AgentRunRecord | None:
        record = self.get(run_id)
        if record is None:
            return None

        record.status = status
        if summary is not None:
            record.summary = summary
        if error_message is not None:
            record.error_message = error_message
        if output_json is not None:
            record.output_json = output_json
        if finished_at is not None:
            record.finished_at = finished_at

        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

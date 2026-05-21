from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import ToolCallRecord


class ToolCallRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_tool_call(self, **values) -> ToolCallRecord:
        record = ToolCallRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list_for_run(self, run_id: str) -> list[ToolCallRecord]:
        stmt = (
            select(ToolCallRecord)
            .where(ToolCallRecord.run_id == run_id)
            .order_by(ToolCallRecord.started_at.asc(), ToolCallRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

    def list_for_step(self, step_id: str) -> list[ToolCallRecord]:
        stmt = (
            select(ToolCallRecord)
            .where(ToolCallRecord.step_id == step_id)
            .order_by(ToolCallRecord.started_at.asc(), ToolCallRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

    def list_for_run_ids(self, run_ids: list[str]) -> list[ToolCallRecord]:
        if not run_ids:
            return []

        stmt = (
            select(ToolCallRecord)
            .where(ToolCallRecord.run_id.in_(run_ids))
            .order_by(ToolCallRecord.started_at.asc(), ToolCallRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

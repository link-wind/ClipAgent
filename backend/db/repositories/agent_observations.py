from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import AgentObservationRecord


class AgentObservationRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, **values) -> AgentObservationRecord:
        # 创建观察记录
        record = AgentObservationRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list_for_session(self, session_id: str) -> list[AgentObservationRecord]:
        # 按时间顺序列出会话观察
        stmt = (
            select(AgentObservationRecord)
            .where(AgentObservationRecord.session_id == session_id)
            .order_by(AgentObservationRecord.created_at.asc(), AgentObservationRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

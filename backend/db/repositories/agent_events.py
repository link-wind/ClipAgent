from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import AgentEventRecord


class AgentEventRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, **values) -> AgentEventRecord:
        # 创建事件记录
        record = AgentEventRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list_for_session(self, session_id: str) -> list[AgentEventRecord]:
        # 按时间顺序列出会话事件
        stmt = (
            select(AgentEventRecord)
            .where(AgentEventRecord.session_id == session_id)
            .order_by(AgentEventRecord.created_at.asc(), AgentEventRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

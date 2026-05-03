from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import AgentMessageRecord


class AgentMessageRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, **values) -> AgentMessageRecord:
        # 创建消息记录
        record = AgentMessageRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list_for_session(self, session_id: str) -> list[AgentMessageRecord]:
        # 按时间顺序列出会话消息
        stmt = (
            select(AgentMessageRecord)
            .where(AgentMessageRecord.session_id == session_id)
            .order_by(AgentMessageRecord.created_at.asc(), AgentMessageRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import AgentSessionRecord


class AgentSessionRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, **values) -> AgentSessionRecord:
        # 创建会话记录
        record = AgentSessionRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get(self, session_id: str) -> AgentSessionRecord | None:
        # 按主键读取会话
        return self.db.get(AgentSessionRecord, session_id)

    def list_recent(self, limit: int = 20) -> list[AgentSessionRecord]:
        # 按最近更新时间列出会话
        stmt = (
            select(AgentSessionRecord)
            .order_by(AgentSessionRecord.updated_at.desc(), AgentSessionRecord.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

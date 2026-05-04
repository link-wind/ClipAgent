from sqlalchemy import func, select
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

    def get_many(self, session_ids: list[str]) -> list[AgentSessionRecord]:
        # 批量读取会话
        if not session_ids:
            return []

        stmt = (
            select(AgentSessionRecord)
            .where(AgentSessionRecord.id.in_(session_ids))
        )
        return list(self.db.scalars(stmt))

    def count_all(self) -> int:
        # 统计会话总数
        stmt = select(func.count()).select_from(AgentSessionRecord)
        return int(self.db.scalar(stmt) or 0)

    def list_recent(self, limit: int = 20) -> list[AgentSessionRecord]:
        # 按最近更新时间列出会话
        stmt = (
            select(AgentSessionRecord)
            .order_by(AgentSessionRecord.updated_at.desc(), AgentSessionRecord.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

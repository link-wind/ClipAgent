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

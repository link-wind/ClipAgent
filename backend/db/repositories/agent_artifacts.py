from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import AgentArtifactRecord


class AgentArtifactRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, **values) -> AgentArtifactRecord:
        # 创建产物记录
        record = AgentArtifactRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list_for_session(self, session_id: str) -> list[AgentArtifactRecord]:
        # 按时间顺序列出会话产物
        stmt = (
            select(AgentArtifactRecord)
            .where(AgentArtifactRecord.session_id == session_id)
            .order_by(AgentArtifactRecord.created_at.asc(), AgentArtifactRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

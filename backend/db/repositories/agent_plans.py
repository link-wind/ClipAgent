from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.db.models import AgentPlanRecord


class AgentPlanRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, **values) -> AgentPlanRecord:
        # 创建计划记录
        record = AgentPlanRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get(self, plan_id: str) -> AgentPlanRecord | None:
        # 按主键读取计划
        return self.db.get(AgentPlanRecord, plan_id)

    def get_latest_for_session(self, session_id: str) -> AgentPlanRecord | None:
        # 读取会话最新版本计划
        stmt = (
            select(AgentPlanRecord)
            .where(AgentPlanRecord.session_id == session_id)
            .order_by(
                desc(AgentPlanRecord.version),
                desc(AgentPlanRecord.created_at),
                desc(AgentPlanRecord.id),
            )
            .limit(1)
        )
        return self.db.scalar(stmt)

    def list_for_session(self, session_id: str) -> list[AgentPlanRecord]:
        # 按版本和创建时间稳定列出会话计划
        stmt = (
            select(AgentPlanRecord)
            .where(AgentPlanRecord.session_id == session_id)
            .order_by(
                AgentPlanRecord.version.asc(),
                AgentPlanRecord.created_at.asc(),
                AgentPlanRecord.id.asc(),
            )
        )
        return list(self.db.scalars(stmt))

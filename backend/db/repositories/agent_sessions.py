from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.models import AgentSessionRecord


class AgentSessionRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, **values) -> AgentSessionRecord:
        # 创建会话记录
        if values.get("planner_trace_json") is None:
            values["planner_trace_json"] = {}
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

    def update_grounding_state(
        self,
        session_id: str,
        *,
        grounding_status: str | None = None,
        grounding_summary_json: dict | None = None,
        selected_candidate_ids_json: list | None = None,
    ) -> AgentSessionRecord | None:
        # 更新会话的 grounding 状态聚合字段
        record = self.get(session_id)
        if record is None:
            return None

        if grounding_status is not None:
            record.grounding_status = grounding_status
        if grounding_summary_json is not None:
            record.grounding_summary_json = grounding_summary_json
        if selected_candidate_ids_json is not None:
            record.selected_candidate_ids_json = selected_candidate_ids_json

        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.db.models import AgentJobRecord


class AgentJobRepository:
    _ALLOWED_STATUS_FIELDS = {
        "status",
        "attempt_count",
        "max_attempts",
        "progress",
        "current_step",
        "error_message",
        "worker_id",
        "started_at",
        "finished_at",
    }

    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, **values) -> AgentJobRecord:
        # 创建任务记录
        record = AgentJobRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get(self, job_id: str) -> AgentJobRecord | None:
        # 按主键读取任务
        return self.db.get(AgentJobRecord, job_id)

    def list_recent(self, limit: int = 50) -> list[AgentJobRecord]:
        # 按最近更新时间列出任务
        stmt = (
            select(AgentJobRecord)
            .order_by(AgentJobRecord.updated_at.desc(), AgentJobRecord.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def count_by_status(self, status: str) -> int:
        # 按状态统计任务数量
        stmt = (
            select(func.count())
            .select_from(AgentJobRecord)
            .where(AgentJobRecord.status == status)
        )
        return int(self.db.scalar(stmt) or 0)

    def count_by_statuses(self, statuses: set[str] | list[str] | tuple[str, ...]) -> int:
        # 按状态集合统计任务数量
        if not statuses:
            return 0

        stmt = (
            select(func.count())
            .select_from(AgentJobRecord)
            .where(AgentJobRecord.status.in_(tuple(statuses)))
        )
        return int(self.db.scalar(stmt) or 0)

    def update_status(self, job_id: str, **values) -> AgentJobRecord | None:
        # 更新任务状态相关字段
        invalid_fields = set(values) - self._ALLOWED_STATUS_FIELDS
        if invalid_fields:
            invalid_field_list = ", ".join(sorted(invalid_fields))
            raise ValueError(f"unsupported update_status fields: {invalid_field_list}")

        record = self.get(job_id)
        if record is None:
            return None

        for key, value in values.items():
            setattr(record, key, value)

        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def try_claim_job(self, job_id: str) -> AgentJobRecord | None:
        # 原子抢占任务，避免重复投递时多个 worker 同时执行。
        stmt = (
            update(AgentJobRecord)
            .where(AgentJobRecord.id == job_id, AgentJobRecord.status == "queued")
            .values(
                status="running",
                progress=35,
                current_step="正在搜索素材",
                started_at=datetime.utcnow(),
                error_message=None,
            )
        )
        result = self.db.execute(stmt)
        if result.rowcount != 1:
            self.db.flush()
            return None

        self.db.flush()
        record = self.get(job_id)
        if record is not None:
            self.db.refresh(record)
        return record

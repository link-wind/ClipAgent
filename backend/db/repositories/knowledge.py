from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import (
    AgentContextUsageRecord,
    KnowledgeChunkRecord,
    KnowledgeSourceRecord,
    KnowledgeVersionRecord,
)


class KnowledgeRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create_source(self, **values) -> KnowledgeSourceRecord:
        record = KnowledgeSourceRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get_source(self, source_id: str) -> KnowledgeSourceRecord | None:
        return self.db.get(KnowledgeSourceRecord, source_id)

    def create_version(self, **values) -> KnowledgeVersionRecord:
        record = KnowledgeVersionRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get_version(self, version_id: str) -> KnowledgeVersionRecord | None:
        return self.db.get(KnowledgeVersionRecord, version_id)

    def update_version_storage_path(self, version_id: str, storage_path: str) -> KnowledgeVersionRecord:
        record = self.get_version(version_id)
        if record is None:
            raise ValueError(f"knowledge version not found: {version_id}")
        record.storage_path = storage_path
        self.db.flush()
        self.db.refresh(record)
        return record

    def set_processing_version(self, source_id: str, version_id: str) -> KnowledgeSourceRecord:
        record = self.get_source(source_id)
        if record is None:
            raise ValueError(f"knowledge source not found: {source_id}")
        record.processing_version_id = version_id
        record.status = "processing"
        self.db.flush()
        self.db.refresh(record)
        return record

    def activate_version(self, version_id: str) -> KnowledgeVersionRecord:
        version = self.get_version(version_id)
        if version is None:
            raise ValueError(f"knowledge version not found: {version_id}")

        now = datetime.utcnow()
        source = self.get_source(version.source_id)
        if source is None:
            raise ValueError(f"knowledge source not found: {version.source_id}")

        version.status = "active"
        version.activated_at = now
        version.error_message = None
        source.active_version_id = version.id
        source.processing_version_id = None
        source.status = "ready"
        source.error_message = None
        self.db.flush()
        self.db.refresh(version)
        return version

    def mark_version_failed(self, version_id: str, error_message: str) -> KnowledgeVersionRecord:
        version = self.get_version(version_id)
        if version is None:
            raise ValueError(f"knowledge version not found: {version_id}")

        now = datetime.utcnow()
        source = self.get_source(version.source_id)
        if source is None:
            raise ValueError(f"knowledge source not found: {version.source_id}")

        version.status = "failed"
        version.error_message = error_message
        version.failed_at = now
        version.retry_count += 1
        source.processing_version_id = None
        source.last_failed_version_id = version.id
        source.status = "failed"
        source.error_message = error_message
        self.db.flush()
        self.db.refresh(version)
        return version

    def mark_source_deleting(self, source_id: str) -> KnowledgeSourceRecord:
        record = self.get_source(source_id)
        if record is None:
            raise ValueError(f"knowledge source not found: {source_id}")
        record.status = "deleting"
        record.deletion_requested_at = datetime.utcnow()
        self.db.flush()
        self.db.refresh(record)
        return record

    def mark_source_deleted(self, source_id: str) -> KnowledgeSourceRecord:
        record = self.get_source(source_id)
        if record is None:
            raise ValueError(f"knowledge source not found: {source_id}")
        record.status = "deleted"
        record.processing_version_id = None
        record.deleted_at = datetime.utcnow()
        self.db.flush()
        self.db.refresh(record)
        return record

    def create_chunk(self, **values) -> KnowledgeChunkRecord:
        if values.get("metadata_json") is None:
            values["metadata_json"] = {}
        record = KnowledgeChunkRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get_chunk(self, chunk_id: str) -> KnowledgeChunkRecord | None:
        return self.db.get(KnowledgeChunkRecord, chunk_id)

    def list_chunks(self, limit: int | None = None) -> list[KnowledgeChunkRecord]:
        stmt = select(KnowledgeChunkRecord).order_by(
            KnowledgeChunkRecord.created_at.asc(),
            KnowledgeChunkRecord.id.asc(),
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt))

    def list_active_chunks(self, source_id: str) -> list[KnowledgeChunkRecord]:
        source = self.get_source(source_id)
        if source is None or source.active_version_id is None:
            return []

        stmt = (
            select(KnowledgeChunkRecord)
            .where(KnowledgeChunkRecord.source_id == source_id)
            .where(KnowledgeChunkRecord.version_id == source.active_version_id)
            .order_by(KnowledgeChunkRecord.chunk_index.asc(), KnowledgeChunkRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

    def create_context_usage(self, **values) -> AgentContextUsageRecord:
        if values.get("metadata_json") is None:
            values["metadata_json"] = {}
        record = AgentContextUsageRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list_context_usages(self, session_id: str) -> list[AgentContextUsageRecord]:
        stmt = (
            select(AgentContextUsageRecord)
            .where(AgentContextUsageRecord.session_id == session_id)
            .order_by(AgentContextUsageRecord.created_at.asc(), AgentContextUsageRecord.id.asc())
        )
        return list(self.db.scalars(stmt))

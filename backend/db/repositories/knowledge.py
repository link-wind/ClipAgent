from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import (
    AgentContextUsageRecord,
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
    KnowledgeSourceRecord,
)


class KnowledgeRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create_source(self, **values) -> KnowledgeSourceRecord:
        if values.get("metadata_json") is None:
            values["metadata_json"] = {}
        record = KnowledgeSourceRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get_source(self, source_id: str) -> KnowledgeSourceRecord | None:
        return self.db.get(KnowledgeSourceRecord, source_id)

    def create_document(self, **values) -> KnowledgeDocumentRecord:
        if values.get("metadata_json") is None:
            values["metadata_json"] = {}
        record = KnowledgeDocumentRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get_document(self, document_id: str) -> KnowledgeDocumentRecord | None:
        return self.db.get(KnowledgeDocumentRecord, document_id)

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

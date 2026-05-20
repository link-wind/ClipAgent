from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import (
    AgentContextUsageRecord,
    KnowledgeChunkRecord,
    KnowledgeSourceRecord,
    KnowledgeVersionRecord,
)
from backend.utils.time import utc_now_naive


@dataclass(frozen=True)
class LegacyKnowledgeDocumentRecord:
    id: str
    source_id: str
    title: str
    content: str
    metadata_json: dict


class KnowledgeRepository:
    def __init__(self, db_session: Session):
        self.db = db_session
        self._legacy_documents: dict[str, dict[str, str]] = {}

    def create_source(self, **values) -> KnowledgeSourceRecord:
        normalized = dict(values)
        legacy_source_type = normalized.pop("source_type", None)
        normalized.pop("uri", None)
        normalized.pop("metadata_json", None)
        if "name" not in normalized:
            normalized["name"] = normalized.pop("title", None) or legacy_source_type or "knowledge-source"
        normalized.setdefault("project_key", "default")
        normalized.setdefault("content_type", legacy_source_type or "text/plain")
        normalized.setdefault("status", "pending")
        normalized.setdefault("active_version_id", None)
        normalized.setdefault("processing_version_id", None)
        normalized.setdefault("last_failed_version_id", None)
        record = KnowledgeSourceRecord(**normalized)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get_source_by_project_and_name(
        self,
        project_key: str,
        name: str,
        *,
        include_deleted: bool = True,
    ) -> KnowledgeSourceRecord | None:
        stmt = (
            select(KnowledgeSourceRecord)
            .where(KnowledgeSourceRecord.project_key == project_key)
            .where(KnowledgeSourceRecord.name == name)
            .order_by(KnowledgeSourceRecord.created_at.desc(), KnowledgeSourceRecord.id.desc())
            .limit(1)
        )
        source = self.db.scalar(stmt)
        if source is None:
            return None
        if not include_deleted and source.status == "deleted":
            return None
        return source

    def get_source(self, source_id: str) -> KnowledgeSourceRecord | None:
        return self.db.get(KnowledgeSourceRecord, source_id)

    def list_sources(self, project_key: str = "default") -> list[KnowledgeSourceRecord]:
        stmt = (
            select(KnowledgeSourceRecord)
            .where(KnowledgeSourceRecord.project_key == project_key)
            .where(KnowledgeSourceRecord.status != "deleted")
            .where(KnowledgeSourceRecord.deleted_at.is_(None))
            .order_by(KnowledgeSourceRecord.updated_at.desc(), KnowledgeSourceRecord.id.desc())
        )
        return list(self.db.scalars(stmt))

    def create_version(self, **values) -> KnowledgeVersionRecord:
        record = KnowledgeVersionRecord(**values)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list_versions(self, source_id: str) -> list[KnowledgeVersionRecord]:
        stmt = (
            select(KnowledgeVersionRecord)
            .where(KnowledgeVersionRecord.source_id == source_id)
            .order_by(KnowledgeVersionRecord.version_number.asc(), KnowledgeVersionRecord.created_at.asc())
        )
        return list(self.db.scalars(stmt))

    def get_version_by_content_hash(self, source_id: str, content_hash: str) -> KnowledgeVersionRecord | None:
        stmt = (
            select(KnowledgeVersionRecord)
            .where(KnowledgeVersionRecord.source_id == source_id)
            .where(KnowledgeVersionRecord.content_hash == content_hash)
            .order_by(KnowledgeVersionRecord.version_number.asc(), KnowledgeVersionRecord.created_at.asc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def get_next_version_number(self, source_id: str) -> int:
        versions = self.list_versions(source_id)
        if not versions:
            return 1
        return max(version.version_number for version in versions) + 1

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

    def set_processing_version(
        self,
        source_id: str,
        version_id: str,
        *,
        status: str = "processing",
    ) -> KnowledgeSourceRecord:
        record = self.get_source(source_id)
        if record is None:
            raise ValueError(f"knowledge source not found: {source_id}")
        record.processing_version_id = version_id
        record.status = status
        self.db.flush()
        self.db.refresh(record)
        return record

    def activate_version(self, version_id: str) -> KnowledgeVersionRecord:
        version = self.get_version(version_id)
        if version is None:
            raise ValueError(f"knowledge version not found: {version_id}")

        now = utc_now_naive()
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

        now = utc_now_naive()
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
        record.deletion_requested_at = utc_now_naive()
        self.db.flush()
        self.db.refresh(record)
        return record

    def mark_source_deleted(self, source_id: str) -> KnowledgeSourceRecord:
        record = self.get_source(source_id)
        if record is None:
            raise ValueError(f"knowledge source not found: {source_id}")
        record.status = "deleted"
        record.processing_version_id = None
        record.deleted_at = utc_now_naive()
        self.db.flush()
        self.db.refresh(record)
        return record

    def create_document(self, **values) -> LegacyKnowledgeDocumentRecord:
        source_id = values.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("knowledge document requires source_id")

        source = self.get_source(source_id)
        if source is None:
            raise ValueError(f"knowledge source not found: {source_id}")

        title = str(values.get("title") or source.name)
        content = str(values.get("content") or "")
        metadata_json = values.get("metadata_json") or {}

        if source.active_version_id is None:
            version = self.create_version(
                source_id=source_id,
                version_number=self.get_next_version_number(source_id),
                status="uploaded",
                content_hash=sha256(content.encode("utf-8")).hexdigest(),
                original_filename=title,
                file_size=len(content.encode("utf-8")),
                parser_type="text",
            )
            self.activate_version(version.id)
            source = self.get_source(source_id) or source

        document_id = str(values.get("id") or f"legacy-doc-{source_id}-{len(self._legacy_documents) + 1}")
        self._legacy_documents[document_id] = {
            "source_id": source_id,
            "version_id": source.active_version_id or "",
        }
        return LegacyKnowledgeDocumentRecord(
            id=document_id,
            source_id=source_id,
            title=title,
            content=content,
            metadata_json=metadata_json,
        )

    def create_chunk(self, **values) -> KnowledgeChunkRecord:
        legacy_document_id = values.pop("document_id", None)
        if legacy_document_id is not None:
            legacy_document = self._legacy_documents.get(str(legacy_document_id))
            if legacy_document is None:
                raise ValueError(f"knowledge document not found: {legacy_document_id}")
            values.setdefault("source_id", legacy_document["source_id"])
            values.setdefault("version_id", legacy_document["version_id"])
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

    def list_ready_active_chunks(self, project_key: str) -> list[KnowledgeChunkRecord]:
        stmt = (
            select(KnowledgeChunkRecord)
            .join(KnowledgeSourceRecord, KnowledgeChunkRecord.source_id == KnowledgeSourceRecord.id)
            .where(KnowledgeSourceRecord.project_key == project_key)
            .where(KnowledgeSourceRecord.status == "ready")
            .where(KnowledgeSourceRecord.deleted_at.is_(None))
            .where(KnowledgeSourceRecord.active_version_id.is_not(None))
            .where(KnowledgeChunkRecord.version_id == KnowledgeSourceRecord.active_version_id)
            .order_by(
                KnowledgeSourceRecord.created_at.asc(),
                KnowledgeChunkRecord.chunk_index.asc(),
                KnowledgeChunkRecord.id.asc(),
            )
        )
        return list(self.db.scalars(stmt))

    def delete_chunks_for_version(self, version_id: str) -> int:
        stmt = select(KnowledgeChunkRecord).where(KnowledgeChunkRecord.version_id == version_id)
        records = list(self.db.scalars(stmt))
        for record in records:
            self.db.delete(record)
        self.db.flush()
        return len(records)

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

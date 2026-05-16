from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from backend.app.knowledge.storage import LocalKnowledgeStorage
from backend.config import get_settings
from backend.db.repositories import KnowledgeRepository
from backend.models.knowledge import KnowledgeSourceSummary, KnowledgeVersionSummary


def _default_dispatch_ingestion(version_id: str) -> None:
    from backend.tasks.knowledge_tasks import dispatch_knowledge_version_ingestion

    dispatch_knowledge_version_ingestion(version_id)


def _infer_content_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".md":
        return "text/markdown"
    if suffix == ".txt":
        return "text/plain"
    return "application/octet-stream"


def _infer_parser_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".md":
        return "markdown"
    return "text"


class KnowledgeUploadService:
    def __init__(
        self,
        db_session: Session,
        storage: LocalKnowledgeStorage | None = None,
        dispatch_ingestion: Callable[[str], None] | None = None,
    ):
        self.repo = KnowledgeRepository(db_session)
        settings = get_settings()
        self.storage = storage or LocalKnowledgeStorage(Path(settings.knowledge_storage_dir))
        self.dispatch_ingestion = dispatch_ingestion or _default_dispatch_ingestion

    def upload(
        self,
        *,
        project_key: str = "default",
        filename: str,
        content: bytes,
        content_type: str | None = None,
    ) -> KnowledgeSourceSummary:
        normalized_filename = Path(filename).name or "knowledge-upload"
        payload = content if isinstance(content, bytes) else bytes(content)
        content_hash = sha256(payload).hexdigest()

        source = self.repo.get_source_by_project_and_name(project_key, normalized_filename)
        if source is not None and source.status == "deleting":
            raise ValueError("knowledge source is deleting")

        if source is None or source.status == "deleted":
            source = self.repo.create_source(
                project_key=project_key,
                name=normalized_filename,
                content_type=content_type or _infer_content_type(normalized_filename),
                status="pending",
            )

        existing_version = self.repo.get_version_by_content_hash(source.id, content_hash)
        if existing_version is not None:
            return self._build_source_summary(source.id)

        version = self.repo.create_version(
            source_id=source.id,
            version_number=self.repo.get_next_version_number(source.id),
            status="uploaded",
            content_hash=content_hash,
            original_filename=normalized_filename,
            file_size=len(payload),
            parser_type=_infer_parser_type(normalized_filename),
        )
        saved = self.storage.save_upload(
            project_key=project_key,
            source_id=source.id,
            version_number=version.version_number,
            filename=normalized_filename,
            content=payload,
        )
        self.repo.update_version_storage_path(version.id, saved.storage_path)
        self.repo.set_processing_version(source.id, version.id, status="pending")
        self.dispatch_ingestion(version.id)
        return self._build_source_summary(source.id)

    def upload_file(
        self,
        *,
        project_key: str = "default",
        filename: str,
        content: bytes,
        content_type: str | None = None,
    ) -> KnowledgeSourceSummary:
        return self.upload(
            project_key=project_key,
            filename=filename,
            content=content,
            content_type=content_type,
        )

    def _build_source_summary(self, source_id: str) -> KnowledgeSourceSummary:
        source = self.repo.get_source(source_id)
        if source is None:
            raise ValueError(f"knowledge source not found: {source_id}")

        return KnowledgeSourceSummary(
            id=source.id,
            name=source.name,
            status=source.status,
            contentType=source.content_type,
            createdAt=source.created_at.isoformat(),
            updatedAt=source.updated_at.isoformat(),
            errorSummary=source.error_message,
            activeVersion=self._build_version_summary(source.active_version_id),
            processingVersion=self._build_version_summary(source.processing_version_id),
            lastFailedVersion=self._build_version_summary(source.last_failed_version_id),
            deletionRequestedAt=source.deletion_requested_at.isoformat() if source.deletion_requested_at else None,
        )

    def _build_version_summary(self, version_id: str | None) -> KnowledgeVersionSummary | None:
        if version_id is None:
            return None
        version = self.repo.get_version(version_id)
        if version is None:
            return None
        return KnowledgeVersionSummary(
            id=version.id,
            versionNumber=version.version_number,
            contentHash=version.content_hash,
            status=version.status,
            createdAt=version.created_at.isoformat(),
            updatedAt=version.updated_at.isoformat(),
            failedAt=version.failed_at.isoformat() if version.failed_at else None,
            reason=version.error_message,
        )

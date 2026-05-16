from __future__ import annotations

from collections.abc import Callable

from backend.db.repositories import KnowledgeRepository
from backend.models.knowledge import KnowledgeSourceSummary, KnowledgeVersionSummary


def build_version_summary(repo: KnowledgeRepository, version_id: str | None) -> KnowledgeVersionSummary | None:
    if version_id is None:
        return None
    version = repo.get_version(version_id)
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


def build_source_summary(repo: KnowledgeRepository, source_id: str) -> KnowledgeSourceSummary:
    source = repo.get_source(source_id)
    if source is None:
        raise KeyError(source_id)
    return KnowledgeSourceSummary(
        id=source.id,
        name=source.name,
        status=source.status,
        contentType=source.content_type,
        createdAt=source.created_at.isoformat(),
        updatedAt=source.updated_at.isoformat(),
        errorSummary=source.error_message,
        activeVersion=build_version_summary(repo, source.active_version_id),
        processingVersion=build_version_summary(repo, source.processing_version_id),
        lastFailedVersion=build_version_summary(repo, source.last_failed_version_id),
        deletionRequestedAt=source.deletion_requested_at.isoformat() if source.deletion_requested_at else None,
    )


class KnowledgeSourceReadService:
    def __init__(self, session_factory: Callable[[], object]):
        self.session_factory = session_factory

    def get_summary(self, source_id: str) -> KnowledgeSourceSummary:
        with self.session_factory() as db:
            repo = KnowledgeRepository(db)
            return build_source_summary(repo, source_id)

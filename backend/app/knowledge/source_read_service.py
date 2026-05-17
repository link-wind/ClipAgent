from __future__ import annotations

from collections.abc import Callable

from backend.db.repositories import KnowledgeRepository
from backend.models.knowledge import KnowledgeChunkPreview, KnowledgeSourceDetail, KnowledgeSourceSummary, KnowledgeVersionSummary


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


def build_chunk_preview(chunk) -> KnowledgeChunkPreview:
    content_preview = chunk.content if len(chunk.content) <= 240 else f"{chunk.content[:237]}..."
    return KnowledgeChunkPreview(
        id=chunk.id,
        versionId=chunk.version_id,
        chunkIndex=chunk.chunk_index,
        chunkType=chunk.chunk_type,
        titlePath=chunk.title_path,
        contentPreview=content_preview,
        tokenCount=chunk.token_count,
        metadata=chunk.metadata_json or {},
    )


class KnowledgeSourceReadService:
    def __init__(self, session_factory: Callable[[], object]):
        self.session_factory = session_factory

    def list_summaries(self, project_key: str = "default") -> list[KnowledgeSourceSummary]:
        with self.session_factory() as db:
            repo = KnowledgeRepository(db)
            return [build_source_summary(repo, source.id) for source in repo.list_sources(project_key)]

    def get_summary(self, source_id: str) -> KnowledgeSourceSummary:
        with self.session_factory() as db:
            repo = KnowledgeRepository(db)
            return build_source_summary(repo, source_id)

    def get_detail(self, source_id: str) -> KnowledgeSourceDetail:
        with self.session_factory() as db:
            repo = KnowledgeRepository(db)
            source = build_source_summary(repo, source_id)
            return KnowledgeSourceDetail(
                source=source,
                activeChunks=[build_chunk_preview(chunk) for chunk in repo.list_active_chunks(source_id)],
            )

    def list_versions(self, source_id: str) -> list[KnowledgeVersionSummary]:
        with self.session_factory() as db:
            repo = KnowledgeRepository(db)
            if repo.get_source(source_id) is None:
                raise KeyError(source_id)
            versions = sorted(
                repo.list_versions(source_id),
                key=lambda version: (version.version_number, version.created_at, version.id),
                reverse=True,
            )
            return [
                summary
                for version in versions
                if (summary := build_version_summary(repo, version.id)) is not None
            ]

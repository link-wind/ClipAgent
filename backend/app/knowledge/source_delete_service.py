from __future__ import annotations

from collections.abc import Callable

from backend.app.knowledge.ingestion_service import KnowledgeIngestionService
from backend.app.knowledge.source_read_service import build_source_summary
from backend.db.repositories import KnowledgeRepository
from backend.models.knowledge import KnowledgeSourceSummary


class KnowledgeSourceDeleteService:
    def __init__(self, session_factory: Callable[[], object]):
        self.session_factory = session_factory

    def delete_source(self, source_id: str) -> KnowledgeSourceSummary:
        with self.session_factory() as db:
            repo = KnowledgeRepository(db)
            source = repo.get_source(source_id)
            if source is None:
                raise KeyError(source_id)

            if source.status == "deleted":
                return build_source_summary(repo, source.id)

            if source.status != "deleting":
                source = repo.mark_source_deleting(source.id)

            if source.processing_version_id is None:
                KnowledgeIngestionService(db).complete_source_deletion(source.id)
                source = repo.get_source(source.id)

            if source is None:
                raise KeyError(source_id)
            return build_source_summary(repo, source.id)

from __future__ import annotations

from collections.abc import Callable

from backend.app.knowledge.source_read_service import build_source_summary
from backend.db.repositories import KnowledgeRepository
from backend.models.knowledge import KnowledgeSourceSummary
from backend.tasks.knowledge_tasks import dispatch_knowledge_version_ingestion


class KnowledgeSourceRetryService:
    def __init__(
        self,
        session_factory: Callable[[], object],
        dispatch_ingestion: Callable[[str], None] | None = None,
    ):
        self.session_factory = session_factory
        self.dispatch_ingestion = dispatch_ingestion or dispatch_knowledge_version_ingestion

    def retry_source(self, source_id: str) -> KnowledgeSourceSummary:
        with self.session_factory() as db:
            repo = KnowledgeRepository(db)
            source = repo.get_source(source_id)
            if source is None:
                raise KeyError(source_id)
            if source.status != "failed" or source.last_failed_version_id is None:
                raise ValueError("knowledge source is not retryable")

            version = repo.get_version(source.last_failed_version_id)
            if version is None:
                raise ValueError("last failed knowledge version not found")

            version.status = "uploaded"
            version.error_message = None
            version.failed_at = None
            source.error_message = None
            source.last_failed_version_id = None
            repo.set_processing_version(source.id, version.id, status="pending")
            db.commit()
            self.dispatch_ingestion(version.id)
            return build_source_summary(repo, source.id)

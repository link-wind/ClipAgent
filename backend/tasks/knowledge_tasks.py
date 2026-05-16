from __future__ import annotations

from pathlib import Path

from backend.app.knowledge.ingestion_service import KnowledgeIngestionService
from backend.app.knowledge.storage import LocalKnowledgeStorage
from backend.config import get_settings
from backend.tasks.celery_app import celery_app


SessionLocal = None


def _session_local():
    global SessionLocal
    if SessionLocal is None:
        from backend.db import SessionLocal as _SessionLocal

        SessionLocal = _SessionLocal
    return SessionLocal


def build_knowledge_storage() -> LocalKnowledgeStorage:
    settings = get_settings()
    return LocalKnowledgeStorage(Path(settings.knowledge_storage_dir))


def dispatch_knowledge_version_ingestion(version_id: str) -> None:
    delay = getattr(ingest_knowledge_version, "delay", None)
    if callable(delay):
        delay(version_id)


@celery_app.task(
    bind=True,
    name="backend.tasks.knowledge_tasks.ingest_knowledge_version",
    queue=get_settings().knowledge_queue,
    max_retries=1,
)
def ingest_knowledge_version(self, version_id: str) -> None:
    session_factory = _session_local()
    with session_factory() as db:
        service = KnowledgeIngestionService(db, storage=build_knowledge_storage())
        try:
            service.ingest_version(version_id)
        except Exception as exc:
            if self.request.retries >= self.max_retries:
                raise
            raise self.retry(exc=exc, countdown=0)

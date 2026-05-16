from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.knowledge.chunking import ChunkDraft, chunk_markdown_text, chunk_text
from backend.app.knowledge.storage import LocalKnowledgeStorage
from backend.config import get_settings
from backend.db.repositories import KnowledgeRepository


class KnowledgeIngestionService:
    def __init__(self, db_session: Session, storage: LocalKnowledgeStorage | None = None):
        self.db = db_session
        self.repo = KnowledgeRepository(db_session)
        settings = get_settings()
        self.storage = storage or LocalKnowledgeStorage(Path(settings.knowledge_storage_dir))

    def ingest_text(
        self,
        *,
        source_type: str,
        title: str,
        content: str,
        uri: str | None = None,
    ) -> list[str]:
        normalized = (content or "").strip()
        if not normalized:
            raise ValueError("knowledge content cannot be blank")

        project_key = "default"
        filename = f"{title or 'knowledge-source'}.txt"
        source = self.repo.create_source(
            project_key=project_key,
            name=title or source_type or "knowledge-source",
            content_type="text/plain",
            status="pending",
        )
        version = self.repo.create_version(
            source_id=source.id,
            version_number=1,
            status="uploaded",
            content_hash=sha256(normalized.encode("utf-8")).hexdigest(),
            original_filename=filename,
            file_size=len(normalized.encode("utf-8")),
            parser_type="text",
        )
        saved = self.storage.save_upload(
            project_key=project_key,
            source_id=source.id,
            version_number=version.version_number,
            filename=filename,
            content=normalized.encode("utf-8"),
        )
        self.repo.update_version_storage_path(version.id, saved.storage_path)
        self.repo.set_processing_version(source.id, version.id, status="pending")
        return self.ingest_version(version.id)

    def start_version_processing(self, version_id: str) -> dict[str, str]:
        version = self._require_version(version_id)
        source = self._require_source(version.source_id)

        if source.status in {"deleting", "deleted"}:
            self.complete_source_deletion(source.id)
            return {"sourceId": source.id, "sourceStatus": "deleted", "versionId": version.id}

        version.status = "processing"
        version.error_message = None
        self.repo.set_processing_version(source.id, version.id, status="processing")
        self.db.flush()
        return {"sourceId": source.id, "sourceStatus": "processing", "versionId": version.id}

    def ingest_version(self, version_id: str) -> list[str]:
        version = self._require_version(version_id)
        source = self._require_source(version.source_id)

        if source.status in {"deleting", "deleted"}:
            self.complete_source_deletion(source.id)
            return []

        try:
            chunk_ids: list[str] = []
            with self.db.begin_nested():
                status_info = self.start_version_processing(version_id)
                if status_info.get("sourceStatus") == "deleted":
                    return []
                with self.storage.open(self._require_storage_path(version.id)) as handle:
                    content_bytes = handle.read()

                drafts = self._build_drafts(version, source, content_bytes)
                self.repo.delete_chunks_for_version(version.id)

                for index, draft in enumerate(drafts):
                    record = self.repo.create_chunk(
                        source_id=source.id,
                        version_id=version.id,
                        chunk_index=index,
                        chunk_type=draft.chunk_type,
                        title_path=draft.title_path or None,
                        content=draft.content,
                        token_count=draft.token_count,
                    )
                    chunk_ids.append(record.id)

                refreshed_source = self._require_source(source.id)
                if refreshed_source.status in {"deleting", "deleted"}:
                    self.complete_source_deletion(refreshed_source.id)
                    return []

                self.repo.activate_version(version.id)
            self.db.commit()
            return chunk_ids
        except Exception as exc:
            self.fail_version(version_id, str(exc))
            raise

    def fail_version(self, version_id: str, error_message: str) -> dict[str, str]:
        version = self._require_version(version_id)
        source = self._require_source(version.source_id)
        previous_active_version_id = source.active_version_id if source.active_version_id != version_id else None

        self.repo.mark_version_failed(version_id, error_message)
        refreshed_source = self._require_source(source.id)
        if previous_active_version_id:
            refreshed_source.status = "ready"
        self.db.commit()
        return {
            "sourceId": refreshed_source.id,
            "sourceStatus": refreshed_source.status,
            "versionId": version_id,
        }

    def complete_source_deletion(self, source_id: str) -> None:
        source = self.repo.get_source(source_id)
        if source is None or source.status == "deleted":
            return

        for version in self.repo.list_versions(source.id):
            if version.storage_path and self.storage.exists(version.storage_path):
                self.storage.delete(version.storage_path)

        self.repo.mark_source_deleted(source_id)
        self.db.commit()

    def _build_drafts(
        self,
        version,
        source,
        content_bytes: bytes,
    ) -> list[ChunkDraft]:
        content = content_bytes.decode("utf-8")
        parser_type = (version.parser_type or "").lower()
        filename = version.original_filename or source.name
        suffix = Path(filename).suffix.lower()

        if parser_type == "markdown" or suffix == ".md":
            return chunk_markdown_text(content)
        return chunk_text(content)

    def _require_source(self, source_id: str):
        source = self.repo.get_source(source_id)
        if source is None:
            raise ValueError(f"knowledge source not found: {source_id}")
        return source

    def _require_version(self, version_id: str):
        version = self.repo.get_version(version_id)
        if version is None:
            raise ValueError(f"knowledge version not found: {version_id}")
        return version

    def _require_storage_path(self, version_id: str) -> str:
        version = self._require_version(version_id)
        if not version.storage_path:
            raise FileNotFoundError(f"knowledge version storage path missing: {version_id}")
        return version.storage_path

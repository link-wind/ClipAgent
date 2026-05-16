from __future__ import annotations

from sqlalchemy.orm import Session

from backend.db.repositories import KnowledgeRepository


class KnowledgeIngestionService:
    def __init__(self, db_session: Session):
        self.repo = KnowledgeRepository(db_session)

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

        source = self.repo.create_source(source_type=source_type, title=title, uri=uri)
        document = self.repo.create_document(
            source_id=source.id,
            title=title,
            content=normalized,
        )
        chunk = self.repo.create_chunk(
            document_id=document.id,
            chunk_index=0,
            content=normalized,
            token_count=len(normalized.split()),
        )
        return [chunk.id]

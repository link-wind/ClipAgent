from __future__ import annotations

from sqlalchemy.orm import Session

from backend.db.repositories import KnowledgeRepository
from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalQuery, RetrievalResult
from backend.infrastructure.vector import LightweightVectorIndex


DEFAULT_SEED_CHUNKS = [
    KnowledgeChunk(
        id="seed-shortform-opening",
        document_id="seed-doc-shortform",
        content="短视频开头 3 秒需要明确产品和使用场景。",
        metadata={"source": "builtin_seed", "topic": "shortform_structure"},
    ),
    KnowledgeChunk(
        id="seed-asset-keywords",
        document_id="seed-doc-assets",
        content="每个 scene 的素材关键词应具体到对象、动作和画面风格。",
        metadata={"source": "builtin_seed", "topic": "asset_search"},
    ),
]


class KnowledgeRetrievalService:
    def __init__(
        self,
        db_session: Session | None = None,
        index: LightweightVectorIndex | None = None,
    ):
        self.db = db_session
        self.index = index or LightweightVectorIndex()

    def retrieve(self, query: RetrievalQuery) -> list[RetrievalResult]:
        chunks = self._load_chunks()
        return self.index.search(query, chunks)

    def _load_chunks(self) -> list[KnowledgeChunk]:
        if self.db is None:
            return list(DEFAULT_SEED_CHUNKS)

        records = KnowledgeRepository(self.db).list_chunks()
        if not records:
            return list(DEFAULT_SEED_CHUNKS)

        return [
            KnowledgeChunk(
                id=record.id,
                document_id=record.document_id,
                content=record.content,
                chunk_index=record.chunk_index,
                token_count=record.token_count,
                metadata=record.metadata_json or {},
            )
            for record in records
        ]

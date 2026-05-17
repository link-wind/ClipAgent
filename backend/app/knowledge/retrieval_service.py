from __future__ import annotations

from sqlalchemy.orm import Session

from backend.db.repositories import KnowledgeRepository
from backend.app.knowledge.retrieval_pipeline import RetrievalPipeline, RetrievalPipelineResult
from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalQuery, RetrievalResult
from backend.infrastructure.vector import VectorStore


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
        index: VectorStore | None = None,
        pipeline: RetrievalPipeline | None = None,
    ):
        self.db = db_session
        # Prefer the full pipeline when provided; index remains for older call sites.
        self.pipeline = pipeline or RetrievalPipeline(vector_store=index)

    def retrieve(self, query: RetrievalQuery) -> list[RetrievalResult]:
        return self.retrieve_with_diagnostics(query).results

    def retrieve_with_diagnostics(self, query: RetrievalQuery) -> RetrievalPipelineResult:
        chunks = self._load_chunks(query)
        if hasattr(self.pipeline, "retrieve_with_diagnostics"):
            return self.pipeline.retrieve_with_diagnostics(query, chunks)
        return RetrievalPipelineResult(results=self.pipeline.retrieve(query, chunks))

    def _load_chunks(self, query: RetrievalQuery | None = None) -> list[KnowledgeChunk]:
        if self.db is None:
            return list(DEFAULT_SEED_CHUNKS)

        project_key = self._project_key_from_query(query)
        records = KnowledgeRepository(self.db).list_ready_active_chunks(project_key)
        if not records:
            return list(DEFAULT_SEED_CHUNKS)

        return [
            KnowledgeChunk(
                id=record.id,
                document_id=record.source_id,
                content=record.content,
                chunk_index=record.chunk_index,
                token_count=record.token_count,
                metadata=self._chunk_metadata(record),
            )
            for record in records
        ]

    def _project_key_from_query(self, query: RetrievalQuery | None) -> str:
        if query is not None:
            metadata = query.metadata or {}
            project_key = metadata.get("project_key")
            if isinstance(project_key, str) and project_key.strip():
                return project_key.strip()
        return "default"

    def _chunk_metadata(self, record) -> dict[str, object]:
        metadata = dict(record.metadata_json or {})
        metadata.setdefault("source_id", record.source_id)
        metadata.setdefault("version_id", record.version_id)
        metadata.setdefault("title_path", record.title_path)
        metadata.setdefault("chunk_type", record.chunk_type)
        return metadata

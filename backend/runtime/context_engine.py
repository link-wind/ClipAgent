from dataclasses import dataclass, field
from typing import Any

from backend.app.knowledge.retrieval_service import KnowledgeRetrievalService
from backend.domain.knowledge.contracts import RetrievalQuery, RetrievalResult
from backend.runtime.trace_recorder import TraceEvent, TraceRecorder


@dataclass(frozen=True)
class ContextRequest:
    session_id: str
    message: str
    plan_version: int | None = None
    scope: str = "planning"
    run_id: str | None = None


@dataclass(frozen=True)
class ContextBundle:
    documents: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0


class ContextEngine:
    def __init__(
        self,
        *,
        db_session=None,
        retrieval_service: KnowledgeRetrievalService | None = None,
        trace_recorder: TraceRecorder | None = None,
        top_k: int = 3,
    ):
        self.db = db_session
        self.retrieval_service = retrieval_service or KnowledgeRetrievalService(db_session=db_session)
        self.trace_recorder = trace_recorder or TraceRecorder(db_session)
        self.top_k = top_k

    def build_context(self, request: ContextRequest) -> ContextBundle:
        query = RetrievalQuery(text=request.message, scope=request.scope, top_k=self.top_k)
        self._record(
            request,
            "rag_retrieval_started",
            {"scope": request.scope, "query": query.text, "topK": query.top_k},
        )
        try:
            results = self.retrieval_service.retrieve(query)
        except Exception as exc:
            self._record(
                request,
                "rag_retrieval_failed",
                {"scope": request.scope, "query": query.text, "error": str(exc)},
                level="warning",
                message="RAG context retrieval failed",
            )
            return ContextBundle()

        usage_ids = self._record_usage(request, query, results)
        bundle = self._bundle_from_results(results)
        self._record(
            request,
            "rag_retrieval_succeeded",
            {
                "scope": request.scope,
                "query": query.text,
                "chunkCount": len(results),
                "topScore": results[0].score if results else 0.0,
                "usageIds": usage_ids,
            },
        )
        return bundle

    def _bundle_from_results(self, results: list[RetrievalResult]) -> ContextBundle:
        documents = [
            {
                "chunkId": result.chunk.id,
                "documentId": result.chunk.document_id,
                "sourceId": result.chunk.metadata.get("source_id", result.chunk.document_id),
                "versionId": result.chunk.metadata.get("version_id"),
                "titlePath": result.chunk.metadata.get("title_path"),
                "chunkType": result.chunk.metadata.get("chunk_type"),
                "content": result.chunk.content,
                "score": result.score,
                "matchedTerms": result.matched_terms,
            }
            for result in results
        ]
        citations = [
            {
                "documentId": result.chunk.document_id,
                "chunkId": result.chunk.id,
                "sourceId": result.chunk.metadata.get("source_id", result.chunk.document_id),
                "versionId": result.chunk.metadata.get("version_id"),
                "score": result.score,
            }
            for result in results
        ]
        confidence = sum(result.score for result in results) / len(results) if results else 0.0
        observations = []
        if results:
            observations.append({"type": "retrieval_summary", "summary": f"命中 {len(results)} 条上下文。"})

        return ContextBundle(
            documents=documents,
            observations=observations,
            citations=citations,
            confidence=confidence,
        )

    def _record(
        self,
        request: ContextRequest,
        event_type: str,
        payload: dict[str, Any],
        *,
        level: str = "info",
        message: str | None = None,
    ) -> None:
        self.trace_recorder.record(
            TraceEvent(
                session_id=request.session_id,
                run_id=request.run_id,
                event_type=event_type,
                level=level,
                message=message,
                payload=payload,
                actor_role="context",
            )
        )

    def _record_usage(
        self,
        request: ContextRequest,
        query: RetrievalQuery,
        results: list[RetrievalResult],
    ) -> list[str]:
        if self.db is None or not results:
            return []

        try:
            from backend.app.knowledge.context_usage_service import ContextUsageService
            from backend.db.repositories import KnowledgeRepository

            repo = KnowledgeRepository(self.db)
            persisted_results = [
                result for result in results if repo.get_chunk(result.chunk.id) is not None
            ]
            if not persisted_results:
                return []

            with self.db.begin_nested():
                usages = ContextUsageService(self.db).record_results(
                    session_id=request.session_id,
                    run_id=request.run_id,
                    query_text=query.text,
                    results=persisted_results,
                )
            return [usage.chunk_id for usage in usages]
        except Exception as exc:
            self._record(
                request,
                "rag_context_usage_failed",
                {"scope": request.scope, "query": query.text, "error": str(exc)},
                level="warning",
                message="RAG context usage recording failed",
            )
            return []

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalQuery, RetrievalResult
from backend.infrastructure.vector import KeywordVectorStore, VectorStore


@dataclass(frozen=True)
class RetrievalDiagnostics:
    query_text: str = ""
    input_chunk_count: int = 0
    candidate_count: int = 0
    returned_count: int = 0
    candidate_chunk_ids: tuple[str, ...] = ()
    reranked_chunk_ids: tuple[str, ...] = ()
    returned_chunk_ids: tuple[str, ...] = ()
    top_score: float = 0.0


@dataclass(frozen=True)
class RetrievalPipelineResult:
    results: list[RetrievalResult] = field(default_factory=list)
    diagnostics: RetrievalDiagnostics = field(default_factory=RetrievalDiagnostics)


class Reranker(Protocol):
    def rerank(
        self,
        query: RetrievalQuery,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        ...


class IdentityReranker:
    def rerank(
        self,
        query: RetrievalQuery,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        return list(results)


class RetrievalPipeline:
    def __init__(
        self,
        *,
        vector_store: VectorStore | None = None,
        reranker: Reranker | None = None,
    ):
        self.vector_store = vector_store or KeywordVectorStore()
        self.reranker = reranker or IdentityReranker()

    def retrieve(
        self,
        query: RetrievalQuery,
        chunks: list[KnowledgeChunk],
    ) -> list[RetrievalResult]:
        return self.retrieve_with_diagnostics(query, chunks).results

    def retrieve_with_diagnostics(
        self,
        query: RetrievalQuery,
        chunks: list[KnowledgeChunk],
    ) -> RetrievalPipelineResult:
        if query.top_k <= 0:
            return RetrievalPipelineResult(
                diagnostics=RetrievalDiagnostics(
                    query_text=query.text,
                    input_chunk_count=len(chunks),
                )
            )

        candidates = self.vector_store.search(query, chunks)
        reranked = self.reranker.rerank(query, candidates)
        results = reranked[: query.top_k]
        return RetrievalPipelineResult(
            results=results,
            diagnostics=RetrievalDiagnostics(
                query_text=query.text,
                input_chunk_count=len(chunks),
                candidate_count=len(candidates),
                returned_count=len(results),
                candidate_chunk_ids=tuple(result.chunk.id for result in candidates),
                reranked_chunk_ids=tuple(result.chunk.id for result in reranked),
                returned_chunk_ids=tuple(result.chunk.id for result in results),
                top_score=max((result.score for result in results), default=0.0),
            ),
        )

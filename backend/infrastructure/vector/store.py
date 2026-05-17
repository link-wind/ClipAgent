from __future__ import annotations

from typing import Protocol

from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalQuery, RetrievalResult
from backend.infrastructure.vector.lightweight_index import LightweightVectorIndex


class VectorStore(Protocol):
    def search(
        self,
        query: RetrievalQuery,
        chunks: list[KnowledgeChunk],
    ) -> list[RetrievalResult]:
        ...


class KeywordVectorStore:
    def __init__(self, index: LightweightVectorIndex | None = None):
        self.index = index or LightweightVectorIndex()

    def search(
        self,
        query: RetrievalQuery,
        chunks: list[KnowledgeChunk],
    ) -> list[RetrievalResult]:
        return self.index.search(query, chunks)

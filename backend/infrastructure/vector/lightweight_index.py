from __future__ import annotations

import re

from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalQuery, RetrievalResult


TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+")


class LightweightVectorIndex:
    def search(
        self,
        query: RetrievalQuery,
        chunks: list[KnowledgeChunk],
    ) -> list[RetrievalResult]:
        terms = self._terms(query.text)
        if not terms or query.top_k <= 0:
            return []

        results: list[RetrievalResult] = []
        for chunk in chunks:
            content = chunk.content or ""
            matched_terms = [term for term in terms if term in content]
            if not matched_terms:
                continue
            score = len(matched_terms) / len(terms)
            results.append(
                RetrievalResult(
                    chunk=chunk,
                    score=score,
                    matched_terms=matched_terms,
                )
            )

        return sorted(results, key=lambda result: (-result.score, result.chunk.id))[: query.top_k]

    def _terms(self, text: str) -> list[str]:
        raw_terms = [term.strip() for term in TOKEN_PATTERN.findall(text or "") if term.strip()]
        terms: list[str] = []
        for term in raw_terms:
            if term not in terms:
                terms.append(term)
        return terms

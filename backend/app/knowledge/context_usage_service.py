from __future__ import annotations

from sqlalchemy.orm import Session

from backend.db.repositories import KnowledgeRepository
from backend.domain.knowledge.contracts import ContextUsage, RetrievalResult


class ContextUsageService:
    def __init__(self, db_session: Session):
        self.repo = KnowledgeRepository(db_session)

    def record_results(
        self,
        *,
        session_id: str,
        query_text: str,
        results: list[RetrievalResult],
        run_id: str | None = None,
        usage_type: str = "planning_context",
    ) -> list[ContextUsage]:
        usages: list[ContextUsage] = []
        for result in results:
            record = self.repo.create_context_usage(
                session_id=session_id,
                run_id=run_id,
                query_text=query_text,
                chunk_id=result.chunk.id,
                score=result.score,
                usage_type=usage_type,
                metadata_json={"matchedTerms": result.matched_terms},
            )
            usages.append(
                ContextUsage(
                    session_id=record.session_id,
                    run_id=record.run_id,
                    query_text=record.query_text,
                    chunk_id=record.chunk_id,
                    score=record.score,
                    usage_type=record.usage_type,
                    metadata=record.metadata_json or {},
                )
            )
        return usages

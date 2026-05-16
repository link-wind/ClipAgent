from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class KnowledgeSource:
    id: str
    source_type: str
    title: str
    uri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeDocument:
    id: str
    source_id: str
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    document_id: str
    content: str
    chunk_index: int = 0
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalQuery:
    text: str
    scope: str = "planning"
    top_k: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
    chunk: KnowledgeChunk
    score: float
    matched_terms: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContextUsage:
    session_id: str
    query_text: str
    chunk_id: str
    score: float
    usage_type: str = "planning_context"
    run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

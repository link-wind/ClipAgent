from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextRequest:
    session_id: str
    message: str
    plan_version: int | None = None
    scope: str = "planning"


@dataclass(frozen=True)
class ContextBundle:
    documents: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0


class ContextEngine:
    def build_context(self, request: ContextRequest) -> ContextBundle:
        return ContextBundle()

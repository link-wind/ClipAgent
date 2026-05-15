from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TraceEvent:
    session_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


class TraceRecorder:
    def record(self, event: TraceEvent) -> None:
        return None

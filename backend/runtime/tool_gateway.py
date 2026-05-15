from dataclasses import dataclass, field
from typing import Any, Literal


ToolCallStatus = Literal["succeeded", "failed", "skipped"]


@dataclass(frozen=True)
class ToolCallRequest:
    session_id: str
    tool_id: str
    arguments: dict[str, Any] = field(default_factory=dict)
    permission_scope: str = "session"


@dataclass(frozen=True)
class ToolCallResult:
    status: ToolCallStatus
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class ToolGateway:
    def call_tool(self, request: ToolCallRequest) -> ToolCallResult:
        return ToolCallResult(
            status="skipped",
            error=f"Tool is not registered: {request.tool_id}",
        )

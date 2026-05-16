from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ToolCallStatus = Literal["started", "succeeded", "failed", "skipped"]
PermissionScope = Literal["system", "project", "session"]


@dataclass(frozen=True)
class ToolPermission:
    scope: PermissionScope
    mode: str = "read_only"


@dataclass(frozen=True)
class ToolDefinition:
    id: str
    name: str
    description: str
    category: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    permissions: dict[str, Any] = field(default_factory=dict)
    source_type: str = "local_builtin"
    status: str = "active"
    mcp_server_id: str | None = None
    tool_name: str = ""
    timeout_ms: int = 3000


@dataclass(frozen=True)
class ToolCallRequest:
    session_id: str
    run_id: str
    step_id: str
    tool_id: str
    arguments: dict[str, Any] = field(default_factory=dict)
    actor: str = "agent_runtime"
    actor_role: str = "planner"
    permission_scope: PermissionScope = "session"


@dataclass(frozen=True)
class ToolCallResult:
    status: ToolCallStatus
    data: dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    result_ref: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class ToolCallSummary:
    tool_id: str
    status: ToolCallStatus
    result_summary: str = ""
    result_ref: str = ""
    error_message: str = ""

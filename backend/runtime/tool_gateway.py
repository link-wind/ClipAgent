from dataclasses import dataclass, field
from typing import Any, Literal

from backend.app.tools import BuiltinToolRegistry, ToolCallService, ToolPermissionService, build_default_tool_registry
from backend.domain.tools.contracts import ToolCallRequest as ToolCallRequestContract
from backend.domain.tools.contracts import ToolCallResult as ToolCallResultContract
from backend.domain.tools.contracts import ToolPermission
from backend.infrastructure.tools import LocalToolAdapter, MCPToolAdapter

ToolCallStatus = Literal["succeeded", "failed", "skipped"]


@dataclass(frozen=True)
class ToolCallRequest:
    session_id: str
    run_id: str
    step_id: str
    tool_id: str
    arguments: dict[str, Any] = field(default_factory=dict)
    actor: str = "agent_runtime"
    actor_role: str = "planner"
    permission_scope: str = "session"


@dataclass(frozen=True)
class ToolCallResult:
    status: ToolCallStatus
    data: dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    result_ref: str = ""
    error_message: str = ""


def _normalize_result(tool_id: str, raw_result: Any) -> ToolCallResult:
    if isinstance(raw_result, ToolCallResultContract):
        return ToolCallResult(
            status=raw_result.status,
            data=raw_result.data,
            result_summary=raw_result.result_summary,
            result_ref=raw_result.result_ref,
            error_message=raw_result.error_message,
        )

    data: dict[str, Any]
    if isinstance(raw_result, dict):
        data = raw_result
    elif raw_result is None:
        data = {}
    else:
        data = {"value": raw_result}

    summary = ""
    if isinstance(data.get("summary"), str):
        summary = data["summary"]
    elif isinstance(data.get("result_summary"), str):
        summary = data["result_summary"]
    elif isinstance(raw_result, str):
        summary = raw_result
    else:
        summary = f"Tool {tool_id} completed."

    result_ref = ""
    if isinstance(data.get("result_ref"), str):
        result_ref = data["result_ref"]
    elif isinstance(data.get("ref"), str):
        result_ref = data["ref"]
    else:
        result_ref = f"tool:{tool_id}"

    error_message = ""
    if isinstance(data.get("error_message"), str):
        error_message = data["error_message"]

    return ToolCallResult(
        status="succeeded",
        data=data,
        result_summary=summary,
        result_ref=result_ref,
        error_message=error_message,
    )


class ToolGateway:
    def __init__(
        self,
        registry: BuiltinToolRegistry | None = None,
        permission_service: ToolPermissionService | None = None,
        local_adapter: LocalToolAdapter | None = None,
        mcp_adapter: MCPToolAdapter | None = None,
        tool_call_service: ToolCallService | None = None,
    ) -> None:
        self.registry = registry or build_default_tool_registry()
        self.permission_service = permission_service or ToolPermissionService()
        self.local_adapter = local_adapter or LocalToolAdapter()
        self.mcp_adapter = mcp_adapter or MCPToolAdapter()
        self.tool_call_service = tool_call_service

    def call_tool(self, request: ToolCallRequest) -> ToolCallResult:
        try:
            definition = self.registry.get_definition(request.tool_id)
        except LookupError as exc:
            result = ToolCallResult(status="skipped", error_message=str(exc))
            self._record_call(request, result)
            return result

        permission = ToolPermission(**definition.permissions)
        decision = self.permission_service.decide(permission, request.permission_scope)
        if not decision.allowed:
            result = ToolCallResult(status="skipped", error_message=decision.reason)
            self._record_call(request, result)
            return result

        try:
            if definition.source_type == "local_builtin":
                handler = self.registry.resolve_handler(request.tool_id)
                raw_result = self.local_adapter.call(handler, arguments=request.arguments)
            elif definition.source_type == "mcp":
                raw_result = self.mcp_adapter.call(request=request, definition=definition)
            else:
                raw_result = ToolCallResult(
                    status="skipped",
                    error_message=f"Unsupported tool source type: {definition.source_type}",
                )
            result = _normalize_result(request.tool_id, raw_result)
        except Exception as exc:
            result = ToolCallResult(
                status="failed",
                error_message=str(exc),
                result_summary=f"Tool {request.tool_id} failed.",
                result_ref=f"tool:{request.tool_id}",
            )

        self._record_call(request, result)
        return result

    def _record_call(self, request: ToolCallRequest, result: ToolCallResult) -> None:
        if self.tool_call_service is None:
            return
        contract_request = ToolCallRequestContract(
            session_id=request.session_id,
            run_id=request.run_id,
            step_id=request.step_id,
            tool_id=request.tool_id,
            arguments=request.arguments,
            actor=request.actor,
            actor_role=request.actor_role,
            permission_scope=request.permission_scope,
        )
        contract_result = ToolCallResultContract(
            status=result.status,
            data=result.data,
            result_summary=result.result_summary,
            result_ref=result.result_ref,
            error_message=result.error_message,
        )
        self.tool_call_service.record_tool_call(contract_request, contract_result)

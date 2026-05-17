from __future__ import annotations

from typing import Any, Protocol

from backend.domain.tools.contracts import ToolCallResult, ToolDefinition


class MCPToolClient(Protocol):
    def call_tool(
        self,
        *,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_ms: int,
    ) -> ToolCallResult | dict[str, Any]:
        ...


class DisabledMCPToolClient:
    def call_tool(
        self,
        *,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_ms: int,
    ) -> ToolCallResult:
        return ToolCallResult(
            status="skipped",
            result_ref=f"mcp:{server_id}/{tool_name}",
            error_message="MCP client is not configured in this foundation.",
        )


def _normalize_mcp_result(tool_id: str, raw_result: ToolCallResult | dict[str, Any]) -> ToolCallResult:
    if isinstance(raw_result, ToolCallResult):
        return raw_result

    summary = raw_result.get("summary")
    if not isinstance(summary, str):
        summary = raw_result.get("result_summary")
    if not isinstance(summary, str):
        summary = f"MCP tool {tool_id} completed."

    result_ref = raw_result.get("result_ref")
    if not isinstance(result_ref, str):
        result_ref = raw_result.get("ref")
    if not isinstance(result_ref, str):
        result_ref = f"mcp:{tool_id}"

    error_message = raw_result.get("error_message")
    if not isinstance(error_message, str):
        error_message = ""

    return ToolCallResult(
        status="succeeded",
        data=raw_result,
        result_summary=summary,
        result_ref=result_ref,
        error_message=error_message,
    )


class MCPToolAdapter:
    def __init__(self, client: MCPToolClient | None = None) -> None:
        self.client = client

    def call(self, *, request, definition: ToolDefinition) -> ToolCallResult:
        if self.client is None:
            return ToolCallResult(
                status="skipped",
                error_message="MCP adapter is not configured in this foundation.",
            )
        if not definition.mcp_server_id:
            return ToolCallResult(
                status="skipped",
                error_message=f"MCP tool {definition.id} is missing mcp_server_id.",
            )
        if not definition.tool_name:
            return ToolCallResult(
                status="skipped",
                error_message=f"MCP tool {definition.id} is missing tool_name.",
            )

        try:
            raw_result = self.client.call_tool(
                server_id=definition.mcp_server_id,
                tool_name=definition.tool_name,
                arguments=request.arguments,
                timeout_ms=definition.timeout_ms,
            )
        except Exception as exc:
            return ToolCallResult(
                status="failed",
                result_summary=f"MCP tool {definition.id} failed.",
                result_ref=f"mcp:{definition.mcp_server_id}/{definition.tool_name}",
                error_message=str(exc),
            )
        return _normalize_mcp_result(definition.id, raw_result)


def build_default_mcp_tool_client() -> MCPToolClient:
    return DisabledMCPToolClient()


def build_default_mcp_tool_adapter() -> MCPToolAdapter:
    return MCPToolAdapter(client=build_default_mcp_tool_client())

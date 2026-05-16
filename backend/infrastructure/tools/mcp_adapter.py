from __future__ import annotations

from backend.domain.tools.contracts import ToolCallResult


class MCPToolAdapter:
    def call(self, *_args, **_kwargs) -> ToolCallResult:
        return ToolCallResult(
            status="skipped",
            error_message="MCP adapter is not configured in this foundation.",
        )

from __future__ import annotations

from backend.domain.tools.contracts import ToolDefinition


TOOL_DEFINITION = ToolDefinition(
    id="read_last_failure_diagnostic",
    name="Read Last Failure Diagnostic",
    description="Read the latest failure diagnostic for the current run.",
    category="diagnostics",
    permissions={"scope": "session", "mode": "read_only"},
    source_type="local_builtin",
    tool_name="backend.tools.builtin.diagnostics:read_last_failure_diagnostic",
    status="active",
)


def read_last_failure_diagnostic(*_args, **_kwargs) -> dict[str, object]:
    return {"items": [], "summary": "Diagnostics are read only in this foundation."}

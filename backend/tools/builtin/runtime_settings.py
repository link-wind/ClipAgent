from __future__ import annotations

from backend.domain.tools.contracts import ToolDefinition


TOOL_DEFINITION = ToolDefinition(
    id="read_runtime_settings",
    name="Read Runtime Settings",
    description="Read effective runtime settings for the current session.",
    category="runtime",
    permissions={"scope": "session", "mode": "read_only"},
    source_type="local_builtin",
    tool_name="backend.tools.builtin.runtime_settings:read_runtime_settings",
    status="active",
)


def read_runtime_settings(*_args, **_kwargs) -> dict[str, object]:
    return {"items": [], "summary": "Runtime settings are read only in this foundation."}

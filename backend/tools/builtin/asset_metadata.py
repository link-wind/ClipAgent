from __future__ import annotations

from backend.domain.tools.contracts import ToolDefinition


TOOL_DEFINITION = ToolDefinition(
    id="read_asset_metadata",
    name="Read Asset Metadata",
    description="Read metadata for project assets.",
    category="assets",
    permissions={"scope": "project", "mode": "read_only"},
    source_type="local_builtin",
    tool_name="backend.tools.builtin.asset_metadata:read_asset_metadata",
    status="active",
)


def read_asset_metadata(*_args, **_kwargs) -> dict[str, object]:
    return {"items": [], "summary": "Asset metadata is read only in this foundation."}

from __future__ import annotations

from backend.domain.tools.contracts import ToolDefinition


TOOL_DEFINITION = ToolDefinition(
    id="read_project_knowledge",
    name="Read Project Knowledge",
    description="Read knowledge sources for the current project.",
    category="knowledge",
    permissions={"scope": "project", "mode": "read_only"},
    source_type="local_builtin",
    tool_name="backend.tools.builtin.project_knowledge:read_project_knowledge",
    status="active",
)


def read_project_knowledge(*_args, **_kwargs) -> dict[str, object]:
    return {"items": [], "summary": "Project knowledge is read only in this foundation."}

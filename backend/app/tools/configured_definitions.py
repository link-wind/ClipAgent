from __future__ import annotations

import json
from typing import Any

from backend.domain.tools.contracts import ToolDefinition
from backend.services.runtime_config_service import RuntimeConfigService, runtime_config_service


MCP_TOOLS_JSON_KEY = "CLIPFORGE_MCP_TOOLS_JSON"


def load_configured_mcp_tool_definitions(
    service: RuntimeConfigService = runtime_config_service,
) -> list[ToolDefinition]:
    raw_value = service.get_effective_value(MCP_TOOLS_JSON_KEY)
    if raw_value is None or str(raw_value).strip() == "":
        return []

    try:
        data = json.loads(str(raw_value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{MCP_TOOLS_JSON_KEY} must be valid JSON") from exc

    if not isinstance(data, list):
        raise ValueError(f"{MCP_TOOLS_JSON_KEY} must be a JSON array")

    return [_definition_from_config(item, index) for index, item in enumerate(data)]


def _definition_from_config(item: Any, index: int) -> ToolDefinition:
    if not isinstance(item, dict):
        raise ValueError(f"{MCP_TOOLS_JSON_KEY}[{index}] must be an object")

    tool_id = _required_string(item, "id", index)
    name = _required_string(item, "name", index)
    description = _required_string(item, "description", index)
    category = _required_string(item, "category", index)
    server_id = _required_string(item, "mcpServerId", index)
    tool_name = _required_string(item, "toolName", index)
    scope = str(item.get("scope") or "session").strip()
    timeout_ms = _timeout_ms(item.get("timeoutMs"), default=3000)

    return ToolDefinition(
        id=tool_id,
        name=name,
        description=description,
        category=category,
        permissions={"scope": scope, "mode": "read_only"},
        source_type="mcp",
        mcp_server_id=server_id,
        tool_name=tool_name,
        timeout_ms=timeout_ms,
    )


def _required_string(item: dict[str, Any], key: str, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{MCP_TOOLS_JSON_KEY}[{index}].{key} must be a non-empty string")
    return value.strip()


def _timeout_ms(value: Any, *, default: int) -> int:
    if value is None:
        return default
    try:
        timeout_ms = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("MCP tool timeoutMs must be an integer") from exc
    if timeout_ms <= 0:
        raise ValueError("MCP tool timeoutMs must be greater than 0")
    return timeout_ms

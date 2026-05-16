from __future__ import annotations

from importlib import import_module
from typing import Any

from backend.domain.tools.contracts import ToolDefinition
from backend.tools.builtin import BUILTIN_TOOL_DEFINITION_MODULES


class BuiltinToolRegistry:
    def __init__(self, definition_modules: tuple[str, ...] | None = None) -> None:
        self._definition_modules = definition_modules or BUILTIN_TOOL_DEFINITION_MODULES
        self._definitions_by_id: dict[str, ToolDefinition] | None = None

    def list_definitions(self) -> list[ToolDefinition]:
        return list(self._load_definitions().values())

    def get_definition(self, tool_id: str) -> ToolDefinition:
        definitions = self._load_definitions()
        try:
            return definitions[tool_id]
        except KeyError as exc:
            raise LookupError(f"Unknown builtin tool: {tool_id}") from exc

    def resolve_handler(self, tool_id: str) -> Any:
        definition = self.get_definition(tool_id)
        module_name, function_name = definition.tool_name.split(":", maxsplit=1)
        module = import_module(module_name)
        return getattr(module, function_name)

    def _load_definitions(self) -> dict[str, ToolDefinition]:
        if self._definitions_by_id is None:
            definitions: dict[str, ToolDefinition] = {}
            for module_name in self._definition_modules:
                module = import_module(module_name)
                definition = getattr(module, "TOOL_DEFINITION")
                definitions[definition.id] = definition
            self._definitions_by_id = definitions
        return self._definitions_by_id

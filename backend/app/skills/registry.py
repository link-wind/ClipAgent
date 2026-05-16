from __future__ import annotations

from importlib import import_module
from typing import Callable

from backend.domain.skills.contracts import PlannerRequest, SkillDefinition, SkillSelectionRequest
from backend.skills.builtin import BUILTIN_SKILL_DEFINITION_MODULES


Handler = Callable[[SkillSelectionRequest], PlannerRequest]


class BuiltinSkillRegistry:
    def __init__(self, definition_modules: tuple[str, ...] | None = None) -> None:
        self._definition_modules = definition_modules or BUILTIN_SKILL_DEFINITION_MODULES
        self._definitions_by_id: dict[str, SkillDefinition] | None = None

    def list_definitions(self) -> list[SkillDefinition]:
        return list(self._load_definitions().values())

    def get_definition(self, skill_id: str) -> SkillDefinition:
        definitions = self._load_definitions()
        try:
            return definitions[skill_id]
        except KeyError as exc:
            raise LookupError(f"Unknown builtin skill: {skill_id}") from exc

    def resolve_handler(self, skill_id: str) -> Handler:
        definition = self.get_definition(skill_id)
        module_name, function_name = definition.handler.split(":", maxsplit=1)
        module = import_module(module_name)
        return getattr(module, function_name)

    def _load_definitions(self) -> dict[str, SkillDefinition]:
        if self._definitions_by_id is None:
            definitions: dict[str, SkillDefinition] = {}
            for module_name in self._definition_modules:
                module = import_module(module_name)
                definition = getattr(module, "SKILL_DEFINITION")
                definitions[definition.id] = definition
            self._definitions_by_id = definitions
        return self._definitions_by_id

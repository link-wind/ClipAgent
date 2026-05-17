from __future__ import annotations

from backend.app.skills.registry import BuiltinSkillRegistry, Handler
from backend.domain.skills.contracts import SkillSelection, SkillSelectionRequest


class SkillSelectionService:
    def __init__(self, registry: BuiltinSkillRegistry | None = None) -> None:
        self._registry = registry or BuiltinSkillRegistry()

    def select_skill(self, request: SkillSelectionRequest) -> SkillSelection:
        for definition in self._registry.list_definitions():
            supported_run_types = definition.trigger_conditions.get("runTypes", [])
            if request.run_type in supported_run_types:
                return SkillSelection(
                    skill_id=definition.id,
                    version=definition.version,
                    reason=f"run_type={request.run_type} matched {definition.id}",
                )
        raise LookupError(request.run_type)

    def resolve_handler(self, skill_id: str) -> Handler:
        return self._registry.resolve_handler(skill_id)

from dataclasses import dataclass, field

from backend.app.skills.selection_service import SkillSelectionService
from backend.domain.skills.contracts import SkillSelection, SkillSelectionRequest


@dataclass
class SkillEngine:
    selection_service: SkillSelectionService = field(default_factory=SkillSelectionService)

    def select_skill(self, request: SkillSelectionRequest) -> SkillSelection:
        return self.selection_service.select_skill(request)

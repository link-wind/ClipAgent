from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillSelectionRequest:
    session_id: str
    user_message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillSelection:
    skill_id: str
    version: str
    reason: str = ""


class SkillEngine:
    def select_skill(self, request: SkillSelectionRequest) -> SkillSelection:
        return SkillSelection(
            skill_id="builtin.product_intro_video",
            version="0.1.0",
            reason="Default ClipForge video generation skill",
        )

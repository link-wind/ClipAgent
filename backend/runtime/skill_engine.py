from dataclasses import dataclass, field

from backend.app.skills.registry import BuiltinSkillRegistry
from backend.app.skills.selection_service import SkillSelectionService
from backend.domain.skills.contracts import PlannerRequest, SkillRunSummary, SkillSelection, SkillSelectionRequest


@dataclass(frozen=True)
class PlannerRequestBuildResult:
    selection: SkillSelection
    planner_request: PlannerRequest | None
    summary: SkillRunSummary


@dataclass
class SkillEngine:
    selection_service: SkillSelectionService = field(default_factory=SkillSelectionService)

    @classmethod
    def from_registry(cls, registry: BuiltinSkillRegistry) -> "SkillEngine":
        return cls(selection_service=SkillSelectionService(registry=registry))

    def select_skill(self, request: SkillSelectionRequest) -> SkillSelection:
        return self.selection_service.select_skill(request)

    def build_planner_request(
        self,
        request: SkillSelectionRequest,
        *,
        selection: SkillSelection | None = None,
    ) -> PlannerRequestBuildResult:
        selection = selection or self.select_skill(request)
        try:
            handler = self.selection_service.resolve_handler(selection.skill_id)
            planner_request = handler(request)
        except Exception as exc:
            return PlannerRequestBuildResult(
                selection=selection,
                planner_request=None,
                summary=SkillRunSummary(
                    skill_id=selection.skill_id,
                    skill_version=selection.version,
                    status="failed",
                    input_summary=f"run_type={request.run_type}",
                    error_message=str(exc),
                ),
            )

        return PlannerRequestBuildResult(
            selection=selection,
            planner_request=planner_request,
            summary=SkillRunSummary(
                skill_id=selection.skill_id,
                skill_version=selection.version,
                status="succeeded",
                input_summary=f"run_type={request.run_type}",
                output_summary=f"planner_request action={planner_request.action}",
            ),
        )

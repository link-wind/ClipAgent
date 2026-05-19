from backend.models.agent import EditPlan, PlanScene
from backend.domain.planning.contracts import ExecutionPlan


def execution_plan_to_edit_plan(plan: ExecutionPlan) -> EditPlan:
    if isinstance(plan, dict):
        plan = ExecutionPlan.model_validate(plan)

    return EditPlan(
        title=plan.title,
        targetDuration=plan.targetDuration,
        style=plan.style,
        scenes=[
            PlanScene(
                id=scene.id,
                description=scene.description,
                keywords=scene.keywords,
                duration=scene.duration,
                searchQuery=scene.searchQuery,
            )
            for scene in plan.scenes
        ],
    )

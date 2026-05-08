from backend.config import get_settings
from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime


def get_planner_runtime():
    settings = get_settings()
    if settings.planner_mode == "deterministic":
        return DeterministicPlannerRuntime()

    from backend.services.planner_runtime_openai import OpenAIPlannerRuntime

    return OpenAIPlannerRuntime(model_name=settings.planner_model)

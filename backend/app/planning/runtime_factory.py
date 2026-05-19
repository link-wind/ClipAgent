from backend.app.planning.runtime_deterministic import DeterministicPlannerRuntime


def get_planner_runtime():
    from backend.config import get_settings

    settings = get_settings()
    if settings.planner_mode == "deterministic":
        return DeterministicPlannerRuntime()

    if settings.planner_mode == "langchain":
        from backend.app.planning.runtime_langchain import LangChainPlannerRuntime

        return LangChainPlannerRuntime(model_name=settings.planner_model)

    raise ValueError(f"Unknown planner mode: {settings.planner_mode}")

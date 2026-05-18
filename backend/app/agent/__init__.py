__all__ = [
    "AgentReadService",
    "AgentSessionService",
    "StepProjectionService",
]


def __getattr__(name: str):
    if name == "AgentReadService":
        from backend.app.agent.read_service import AgentReadService

        return AgentReadService
    if name == "AgentSessionService":
        from backend.app.agent.session_service import AgentSessionService

        return AgentSessionService
    if name == "StepProjectionService":
        from backend.app.agent.step_projection_service import StepProjectionService

        return StepProjectionService
    raise AttributeError(name)

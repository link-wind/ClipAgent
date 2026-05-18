from dataclasses import dataclass
from typing import Any

from backend.runtime.context_engine import ContextEngine
from backend.runtime.skill_engine import SkillEngine
from backend.runtime.tool_gateway import ToolGateway
from backend.runtime.trace_recorder import TraceRecorder


@dataclass
class AgentRuntime:
    session_service: Any
    execution_service: Any
    context_engine: ContextEngine
    skill_engine: SkillEngine
    tool_gateway: ToolGateway
    trace_recorder: TraceRecorder

    def create_session(self, message: str | None = None):
        return self.session_service.create_session(message)

    def submit_message(self, session_id: str, message: str):
        return self.session_service.add_user_message(session_id, message)

    def confirm_grounding(self, session_id: str, candidate_ids: list[str]):
        return self.session_service.confirm_grounding_candidates(session_id, candidate_ids)

    def confirm_plan(self, session_id: str):
        return self.execution_service.confirm_session(session_id)


def build_agent_runtime(
    *,
    session_service: Any | None = None,
    execution_service: Any | None = None,
    context_engine: ContextEngine | None = None,
    skill_engine: SkillEngine | None = None,
    tool_gateway: ToolGateway | None = None,
    trace_recorder: TraceRecorder | None = None,
) -> AgentRuntime:
    context_engine = context_engine or ContextEngine()
    skill_engine = skill_engine or SkillEngine()
    tool_gateway = tool_gateway or ToolGateway()
    trace_recorder = trace_recorder or TraceRecorder()

    if session_service is None or execution_service is None:
        from backend.app.agent.session_service import AgentSessionService
        from backend.app.execution.execution_service import AgentExecutionService
        from backend.app.planning.orchestrator import PlannerOrchestrator
        from backend.db import SessionLocal

        planner_orchestrator = PlannerOrchestrator(
            context_engine=context_engine,
            skill_engine=skill_engine,
            trace_recorder=trace_recorder,
        )
        session_service = session_service or AgentSessionService(
            session_factory=SessionLocal,
            planner_orchestrator=planner_orchestrator,
        )
        execution_service = execution_service or AgentExecutionService(session_factory=SessionLocal)

    return AgentRuntime(
        session_service=session_service,
        execution_service=execution_service,
        context_engine=context_engine,
        skill_engine=skill_engine,
        tool_gateway=tool_gateway,
        trace_recorder=trace_recorder,
    )

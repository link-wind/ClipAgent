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

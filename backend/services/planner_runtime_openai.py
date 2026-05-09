from langchain_openai import ChatOpenAI

from backend.services.planner_models import (
    AgentPlan,
    CandidateConfirmationFeedback,
    ExecutionPlan,
    GroundingFeedback,
)


class OpenAIPlannerRuntime:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.llm = ChatOpenAI(model=model_name, temperature=0)

    def build_plan_from_brief(self, brief: str) -> tuple[AgentPlan, ExecutionPlan]:
        raise NotImplementedError(
            "OpenAI planner runtime is enabled in later tasks of the rollout"
        )

    def replan_after_grounding(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        grounding_feedback: GroundingFeedback,
        confirmation_feedback: CandidateConfirmationFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        raise NotImplementedError(
            "OpenAI grounding replanning runtime is enabled in later tasks of the rollout"
        )

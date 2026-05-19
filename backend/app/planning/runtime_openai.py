from langchain_openai import ChatOpenAI

from backend.domain.planning.contracts import (
    AgentPlan,
    CandidateConfirmationFeedback,
    ExecutionPlan,
    GroundingFeedback,
    SearchExecutionFeedback,
    UserRevisionFeedback,
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

    def replan_after_user_revision(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        revision_feedback: UserRevisionFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        raise NotImplementedError(
            "OpenAI user revision replanning runtime is enabled in later tasks of the rollout"
        )

    def replan_after_execution_feedback(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        execution_feedback: SearchExecutionFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        raise NotImplementedError(
            "OpenAI execution feedback replanning runtime is enabled in later tasks of the rollout"
        )

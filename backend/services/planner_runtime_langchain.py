from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.services.planner_models import (
    AgentPlan,
    CandidateConfirmationFeedback,
    ExecutionPlan,
    GroundingFeedback,
    InitialPlanningResult,
    SearchExecutionFeedback,
    UserRevisionFeedback,
)
from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

INITIAL_PLANNER_SYSTEM_PROMPT = """
You are a planning runtime for product intro videos.
Return an InitialPlanningResult with 2 to 4 scenes.
AgentPlan and ExecutionPlan must contain the same number of scenes and matching scene ids.
Scene ids must start at 1 and remain consecutive.
ExecutionPlan searchQuery values must be short English retrieval phrases.
Each agent scene keywords field must be non-empty and concise.
""".strip()


class LangChainPlannerRuntime:
    def __init__(
        self,
        model_name: str,
        *,
        llm=None,
        deterministic_delegate: DeterministicPlannerRuntime | None = None,
    ):
        self.model_name = model_name
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0)
        self.deterministic_delegate = deterministic_delegate or DeterministicPlannerRuntime()

    def _planner_runnable(self):
        return self.llm.with_structured_output(InitialPlanningResult)

    def build_plan_from_brief(self, brief: str) -> tuple[AgentPlan, ExecutionPlan]:
        goal = brief.strip() or "生成产品介绍视频"
        result = self._planner_runnable().invoke(
            [
                SystemMessage(content=INITIAL_PLANNER_SYSTEM_PROMPT),
                HumanMessage(content=goal),
            ]
        )
        normalized = self._normalize_result(result)
        self._validate_result(normalized)
        return normalized.agentPlan, normalized.executionPlan

    def _normalize_result(self, result: InitialPlanningResult) -> InitialPlanningResult:
        normalized_agent = result.agentPlan.model_copy(
            update={
                "title": result.agentPlan.title.strip(),
                "goal": result.agentPlan.goal.strip(),
                "summary": result.agentPlan.summary.strip(),
                "scenes": [
                    scene.model_copy(
                        update={
                            "purpose": scene.purpose.strip(),
                            "description": scene.description.strip(),
                            "keywords": [keyword.strip() for keyword in scene.keywords if keyword.strip()],
                        }
                    )
                    for scene in result.agentPlan.scenes
                ],
            }
        )
        normalized_execution = result.executionPlan.model_copy(
            update={
                "title": result.executionPlan.title.strip(),
                "style": result.executionPlan.style.strip(),
                "scenes": [
                    scene.model_copy(
                        update={
                            "description": scene.description.strip(),
                            "keywords": [keyword.strip() for keyword in scene.keywords if keyword.strip()],
                            "searchQuery": " ".join(scene.searchQuery.split()),
                        }
                    )
                    for scene in result.executionPlan.scenes
                ],
            }
        )
        return InitialPlanningResult(
            agentPlan=normalized_agent,
            executionPlan=normalized_execution,
        )

    def _validate_result(self, result: InitialPlanningResult) -> None:
        agent_plan = result.agentPlan
        execution_plan = result.executionPlan

        if not agent_plan.title or not agent_plan.goal or not agent_plan.summary:
            raise ValueError("title, goal, and summary are required")
        if not execution_plan.title or not execution_plan.style:
            raise ValueError("execution plan title and style are required")
        if not agent_plan.scenes or not execution_plan.scenes:
            raise ValueError("agent and execution plans must include scenes")

        agent_scene_ids = [scene.id for scene in agent_plan.scenes]
        execution_scene_ids = [scene.id for scene in execution_plan.scenes]
        if agent_scene_ids != execution_scene_ids:
            raise ValueError("agent and execution scene ids must match")

        expected_scene_ids = list(range(1, len(agent_scene_ids) + 1))
        if agent_scene_ids != expected_scene_ids:
            raise ValueError("scene ids must start at 1 and be consecutive")

        for scene in agent_plan.scenes:
            if not scene.keywords:
                raise ValueError("agent scene keywords are required")
            if scene.duration <= 0:
                raise ValueError("agent scene duration must be greater than 0")

        execution_duration_sum = 0.0
        for scene in execution_plan.scenes:
            if not scene.searchQuery:
                raise ValueError("execution searchQuery is required")
            if scene.duration <= 0:
                raise ValueError("execution scene duration must be greater than 0")
            execution_duration_sum += scene.duration

        if execution_plan.targetDuration < execution_duration_sum:
            raise ValueError("execution targetDuration must cover scene durations")

    def replan_after_grounding(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        grounding_feedback: GroundingFeedback,
        confirmation_feedback: CandidateConfirmationFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        return self.deterministic_delegate.replan_after_grounding(
            current_agent=current_agent,
            current_execution=current_execution,
            grounding_feedback=grounding_feedback,
            confirmation_feedback=confirmation_feedback,
        )

    def replan_after_user_revision(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        revision_feedback: UserRevisionFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        return self.deterministic_delegate.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=revision_feedback,
        )

    def replan_after_execution_feedback(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        execution_feedback: SearchExecutionFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        return self.deterministic_delegate.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=execution_feedback,
        )

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.services.planner_models import (
    AgentPlan,
    CandidateConfirmationFeedback,
    ExecutionPlan,
    GroundingFeedback,
    InitialPlanningResult,
    RevisionPlanningResult,
    RevisionScenePatch,
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

REVISION_PLANNER_SYSTEM_PROMPT = """
You are revising an existing product intro plan based on new user feedback.
Return a RevisionPlanningResult only.
Do not add or remove scenes.
Do not change scene ids.
Do not change scene durations.
Do not change execution targetDuration.
If explicit scene keyword overrides are provided, treat them as hard constraints.
Only patch fields that should change after the revision.
Keep searchQuery concise and non-empty for every patched scene.
Keep keywords concise and non-empty for every patched scene.
""".strip()

_MISSING_OPEN_ISSUES = object()


class _RevisionFallbackError(Exception):
    """Signals revision outputs that should fall back to the deterministic delegate."""


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

    def _revision_runnable(self):
        return self.llm.with_structured_output(RevisionPlanningResult)

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

    def _build_revision_messages(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        revision_feedback: UserRevisionFeedback,
    ):
        return [
            SystemMessage(content=REVISION_PLANNER_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    "Current AgentPlan:\n"
                    f"{current_agent.model_dump_json(indent=2)}\n\n"
                    "Current ExecutionPlan:\n"
                    f"{current_execution.model_dump_json(indent=2)}\n\n"
                    "Revision feedback:\n"
                    f"{revision_feedback.model_dump_json(indent=2)}"
                )
            ),
        ]

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

    def _normalize_revision_result(
        self,
        result: RevisionPlanningResult,
    ) -> RevisionPlanningResult:
        seen_patch_ids = set()
        normalized_scene_patches = []
        for patch in result.scenePatches:
            if patch.id in seen_patch_ids:
                raise _RevisionFallbackError(f"Duplicate revision patch scene id: {patch.id}")
            seen_patch_ids.add(patch.id)
            normalized_scene_patches.append(
                RevisionScenePatch(
                    id=patch.id,
                    description=patch.description.strip(),
                    keywords=[keyword.strip() for keyword in patch.keywords if keyword.strip()],
                    searchQuery=" ".join(patch.searchQuery.split()),
                )
            )

        open_issues = (
            result.openIssues
            if "openIssues" in result.model_fields_set
            else _MISSING_OPEN_ISSUES
        )

        return RevisionPlanningResult.model_construct(
            summary=result.summary.strip(),
            audience=result.audience.strip(),
            styleHint=result.styleHint.strip(),
            style=result.style.strip(),
            openIssues=open_issues,
            changeSummary=result.changeSummary.strip(),
            scenePatches=normalized_scene_patches,
        )

    def _apply_revision_result(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        revision_feedback: UserRevisionFeedback,
        result: RevisionPlanningResult,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        agent_scene_lookup = {scene.id: scene for scene in current_agent.scenes}
        execution_scene_lookup = {scene.id: scene for scene in current_execution.scenes}
        patch_lookup = {}

        for patch in result.scenePatches:
            if patch.id not in agent_scene_lookup or patch.id not in execution_scene_lookup:
                raise _RevisionFallbackError(f"Unknown revision patch scene id: {patch.id}")
            patch_lookup[patch.id] = patch

        updated_agent_scenes = []
        updated_execution_scenes = []
        for agent_scene, execution_scene in zip(current_agent.scenes, current_execution.scenes):
            patch = patch_lookup.get(agent_scene.id)
            override_keywords = revision_feedback.sceneKeywordUpdates.get(agent_scene.id)

            next_description = agent_scene.description
            next_execution_description = execution_scene.description
            next_keywords = list(agent_scene.keywords)
            next_execution_keywords = list(execution_scene.keywords)
            next_search_query = execution_scene.searchQuery

            if patch is not None:
                next_description = patch.description or agent_scene.description
                next_execution_description = patch.description or execution_scene.description
                next_keywords = patch.keywords
                next_execution_keywords = patch.keywords
                next_search_query = patch.searchQuery

            if override_keywords:
                next_keywords = list(override_keywords)
                next_execution_keywords = list(override_keywords)
                next_search_query = " ".join(override_keywords)

            if patch is not None or override_keywords:
                if not next_keywords:
                    raise _RevisionFallbackError(f"Revision patch keywords are required for scene {agent_scene.id}")
                if not next_search_query:
                    raise _RevisionFallbackError(f"Revision patch searchQuery is required for scene {agent_scene.id}")

            updated_agent_scenes.append(
                agent_scene.model_copy(
                    update={
                        "description": next_description,
                        "keywords": next_keywords,
                    },
                    deep=True,
                )
            )
            updated_execution_scenes.append(
                execution_scene.model_copy(
                    update={
                        "description": next_execution_description,
                        "keywords": next_execution_keywords,
                        "searchQuery": next_search_query,
                    },
                    deep=True,
                )
            )

        next_agent = current_agent.model_copy(
            update={
                "summary": result.summary or current_agent.summary,
                "understanding": current_agent.understanding.model_copy(
                    update={
                        "audience": result.audience or current_agent.understanding.audience,
                        "styleHint": result.styleHint or current_agent.understanding.styleHint,
                    },
                    deep=True,
                ),
                "openIssues": (
                    result.openIssues
                    if result.openIssues is not _MISSING_OPEN_ISSUES
                    else current_agent.openIssues
                ),
                "scenes": updated_agent_scenes,
                "replanHistory": [
                    *current_agent.replanHistory,
                    {
                        "triggerType": "user_revision",
                        "summary": result.changeSummary,
                        "message": revision_feedback.message.strip(),
                        "runtime": "langchain",
                    },
                ],
            },
            deep=True,
        )
        next_execution = current_execution.model_copy(
            update={
                "style": result.style or current_execution.style,
                "scenes": updated_execution_scenes,
            },
            deep=True,
        )
        self._validate_revision_merge(
            current_agent=current_agent,
            current_execution=current_execution,
            next_agent=next_agent,
            next_execution=next_execution,
        )
        return next_agent, next_execution, result.changeSummary

    def _validate_revision_merge(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        next_agent: AgentPlan,
        next_execution: ExecutionPlan,
    ) -> None:
        current_agent_ids = [scene.id for scene in current_agent.scenes]
        current_execution_ids = [scene.id for scene in current_execution.scenes]
        next_agent_ids = [scene.id for scene in next_agent.scenes]
        next_execution_ids = [scene.id for scene in next_execution.scenes]

        if next_agent_ids != current_agent_ids or next_execution_ids != current_execution_ids:
            raise _RevisionFallbackError("Revision merge must preserve scene ids")
        if len(next_agent.scenes) != len(current_agent.scenes) or len(next_execution.scenes) != len(
            current_execution.scenes
        ):
            raise _RevisionFallbackError("Revision merge must preserve scene count")
        if next_execution.targetDuration != current_execution.targetDuration:
            raise _RevisionFallbackError("Revision merge must preserve targetDuration")

        for current_scene, next_scene in zip(current_agent.scenes, next_agent.scenes):
            if next_scene.duration != current_scene.duration:
                raise _RevisionFallbackError(
                    f"Revision merge must preserve agent scene duration for scene {current_scene.id}"
                )
        for current_scene, next_scene in zip(current_execution.scenes, next_execution.scenes):
            if next_scene.duration != current_scene.duration:
                raise _RevisionFallbackError(
                    f"Revision merge must preserve execution scene duration for scene {current_scene.id}"
                )
            if not next_scene.searchQuery:
                raise _RevisionFallbackError(f"Revision merge requires searchQuery for scene {current_scene.id}")
            if not next_scene.keywords:
                raise _RevisionFallbackError(f"Revision merge requires keywords for scene {current_scene.id}")

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
        runnable = self._revision_runnable()
        try:
            try:
                result = runnable.invoke(
                    self._build_revision_messages(
                        current_agent=current_agent,
                        current_execution=current_execution,
                        revision_feedback=revision_feedback,
                    )
                )
            except Exception as exc:
                raise _RevisionFallbackError("Revision planning invoke failed") from exc
            normalized = self._normalize_revision_result(result)
            return self._apply_revision_result(
                current_agent=current_agent,
                current_execution=current_execution,
                revision_feedback=revision_feedback,
                result=normalized,
            )
        except _RevisionFallbackError:
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

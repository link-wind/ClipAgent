from backend.services.planner_models import (
    AgentPlan,
    CandidateConfirmationFeedback,
    ExecutionPlan,
    GroundingFeedback,
)


class DeterministicPlannerRuntime:
    def build_plan_from_brief(self, brief: str) -> tuple[AgentPlan, ExecutionPlan]:
        title = "智能剪辑短片"
        goal = brief.strip() or "生成产品介绍视频"
        plan = AgentPlan(
            title=title,
            goal=goal,
            summary="根据用户 brief 生成的初版计划",
            scenes=[
                {
                    "id": 1,
                    "purpose": "建立产品识别",
                    "description": "开场展示产品主题",
                    "keywords": ["product", "interface"],
                    "duration": 6,
                },
                {
                    "id": 2,
                    "purpose": "突出核心卖点",
                    "description": "展示重点功能或体验",
                    "keywords": ["feature", "workflow"],
                    "duration": 8,
                },
            ],
        )
        execution = ExecutionPlan(
            title=title,
            targetDuration=30,
            style="快节奏社媒短片",
            scenes=[
                {
                    "id": 1,
                    "description": "开场展示产品主题",
                    "keywords": ["product", "interface"],
                    "searchQuery": "product interface",
                    "duration": 6,
                },
                {
                    "id": 2,
                    "description": "展示重点功能或体验",
                    "keywords": ["feature", "workflow"],
                    "searchQuery": "feature workflow",
                    "duration": 8,
                },
            ],
        )
        return plan, execution

    def replan_after_grounding(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        grounding_feedback: GroundingFeedback,
        confirmation_feedback: CandidateConfirmationFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        selected_ids = (
            confirmation_feedback.selectedCandidateIds
            or grounding_feedback.selectedCandidateIds
        )
        style = grounding_feedback.styleHint or current_execution.style
        feature_hints = grounding_feedback.featureHints or ["product", "workflow"]

        next_execution = current_execution.model_copy(
            update={
                "style": style,
                "scenes": [
                    scene.model_copy(
                        update={
                            "keywords": feature_hints[:2] or scene.keywords,
                            "searchQuery": " ".join(feature_hints[:2] or scene.keywords),
                            "groundingCandidateIds": selected_ids,
                        }
                    )
                    for scene in current_execution.scenes
                ],
            }
        )
        next_agent = current_agent.model_copy(
            update={
                "replanHistory": [
                    *current_agent.replanHistory,
                    {
                        "triggerType": "grounding_confirmation",
                        "selectedCandidateIds": selected_ids,
                        "summary": "基于候选确认完成重规划",
                    },
                ],
                "scenes": [
                    scene.model_copy(
                        update={
                            "groundingCandidateIds": selected_ids,
                            "status": "grounded",
                        }
                    )
                    for scene in current_agent.scenes
                ],
                "grounding": {
                    **current_agent.grounding,
                    "selectedCandidateIds": selected_ids,
                    "productName": grounding_feedback.productName,
                    "audience": grounding_feedback.audience,
                    "styleHint": style,
                    "featureHints": grounding_feedback.featureHints or current_agent.grounding.get("featureHints", []),
                    "candidates": grounding_feedback.candidates,
                },
            }
        )
        return next_agent, next_execution, "grounding 确认后已重规划"

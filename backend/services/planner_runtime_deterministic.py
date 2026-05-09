from backend.services.planner_models import (
    AgentPlan,
    CandidateConfirmationFeedback,
    ExecutionPlan,
    GroundingFeedback,
    SearchExecutionFeedback,
    UserRevisionFeedback,
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

    def replan_after_user_revision(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        revision_feedback: UserRevisionFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        message = revision_feedback.message.strip()
        updated_style = current_execution.style
        if "商务" in message:
            updated_style = "商务演示风格"
        elif "品牌感" in message:
            updated_style = "品牌展示风格"

        updated_audience = current_agent.understanding.audience
        if "销售团队" in message:
            updated_audience = "销售团队"

        updated_execution_scenes = []
        for scene in current_execution.scenes:
            override_keywords = revision_feedback.sceneKeywordUpdates.get(scene.id)
            if override_keywords:
                updated_execution_scenes.append(
                    scene.model_copy(
                        update={
                            "keywords": override_keywords,
                            "searchQuery": " ".join(override_keywords),
                        }
                    )
                )
            else:
                updated_execution_scenes.append(scene.model_copy(deep=True))

        updated_agent_scenes = []
        for scene in current_agent.scenes:
            override_keywords = revision_feedback.sceneKeywordUpdates.get(scene.id)
            if override_keywords:
                updated_agent_scenes.append(
                    scene.model_copy(
                        update={
                            "keywords": override_keywords,
                        }
                    )
                )
            else:
                updated_agent_scenes.append(scene.model_copy(deep=True))

        next_execution = current_execution.model_copy(
            update={
                "style": updated_style,
                "scenes": updated_execution_scenes,
            }
        )
        next_agent = current_agent.model_copy(
            update={
                "summary": f"{current_agent.summary}；已根据最新 revision 调整",
                "understanding": current_agent.understanding.model_copy(
                    update={"audience": updated_audience}
                ),
                "scenes": updated_agent_scenes,
                "replanHistory": [
                    *current_agent.replanHistory,
                    {
                        "triggerType": "user_revision",
                        "summary": "基于最新用户 revision 完成重规划",
                        "message": message,
                    },
                ],
            }
        )
        return next_agent, next_execution, "revision 驱动的计划重规划已完成"

    def replan_after_execution_feedback(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        execution_feedback: SearchExecutionFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        failed_scene_ids = set(execution_feedback.failedSceneIds)

        updated_execution_scenes = []
        for scene in current_execution.scenes:
            if scene.id in failed_scene_ids:
                next_keywords = [*scene.keywords[:2], "alternative"]
                updated_execution_scenes.append(
                    scene.model_copy(
                        update={
                            "keywords": next_keywords,
                            "searchQuery": " ".join(next_keywords),
                        }
                    )
                )
            else:
                updated_execution_scenes.append(scene.model_copy(deep=True))

        updated_agent_scenes = []
        for scene in current_agent.scenes:
            if scene.id in failed_scene_ids:
                updated_agent_scenes.append(
                    scene.model_copy(
                        update={
                            "status": "draft",
                            "keywords": [*scene.keywords[:2], "alternative"],
                        }
                    )
                )
            else:
                updated_agent_scenes.append(scene.model_copy(deep=True))

        next_execution = current_execution.model_copy(update={"scenes": updated_execution_scenes})
        next_agent = current_agent.model_copy(
            update={
                "scenes": updated_agent_scenes,
                "replanHistory": [
                    *current_agent.replanHistory,
                    {
                        "triggerType": "execution_feedback",
                        "summary": "基于执行失败反馈重写检索查询",
                        "failedSceneIds": sorted(failed_scene_ids),
                        "failureReason": execution_feedback.failureReason,
                    },
                ],
            }
        )
        return next_agent, next_execution, "execution feedback 驱动的重规划已完成"

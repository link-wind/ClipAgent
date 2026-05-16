from backend.services.planner_models import (
    AgentPlan,
    CandidateConfirmationFeedback,
    ExecutionPlan,
    GroundingFeedback,
    SearchExecutionFeedback,
    UserRevisionFeedback,
)

_BRIEF_KEYWORD_RULES = (
    (
        ("咖啡", "latte", "barista", "拉花"),
        [
            ("开场展示咖啡与拉花细节", ["coffee", "latte", "art"], 6),
            ("展示 barista 手作与生活方式氛围", ["barista", "coffee", "lifestyle"], 8),
        ],
    ),
    (
        ("城市", "车流", "黄昏", "夜景", "霓虹"),
        [
            ("开场建立城市黄昏与车流氛围", ["城市", "黄昏", "车流"], 6),
            ("展示夜景霓虹与都市节奏", ["夜景", "霓虹", "城市"], 8),
        ],
    ),
    (
        ("海边", "日落", "海", "夕阳"),
        [
            ("开场展示海边日落全景", ["海边", "日落", "风景"], 6),
            ("延续金色海面与慢节奏氛围", ["夕阳", "海面", "自然"], 8),
        ],
    ),
    (
        ("雪山", "山", "航拍"),
        [
            ("开场建立雪山与航拍视角", ["雪山", "航拍", "自然"], 6),
            ("展示山脊层次与辽阔风景", ["山脊", "风景", "自然"], 8),
        ],
    ),
    (
        ("竹林", "冥想", "风"),
        [
            ("开场展示竹林与阳光穿透", ["竹林", "自然", "阳光"], 6),
            ("延续风声与冥想氛围", ["微风", "竹林", "冥想"], 8),
        ],
    ),
)

_KNOWN_FAILURE_CATEGORIES = {
    "platform_blocked",
    "no_inventory",
    "download_transient",
    "generic_retry",
}

_KNOWN_REWRITE_STRATEGIES = {
    "stock_footage_fallback",
    "inventory_broaden",
    "candidate_alternative",
}


def _classify_execution_failure(failure_reason: str) -> str:
    text = (failure_reason or "").lower()
    if any(
        token in text
        for token in ("po token", "sign in", "not a bot", "challenge", "signature", "401", "403")
    ):
        return "platform_blocked"
    if any(
        token in failure_reason
        for token in ("没有返回候选素材", "没有可下载候选素材", "没有下载到可用素材")
    ):
        return "no_inventory"
    if any(token in text for token in ("download failed", "timeout", "connection reset")):
        return "download_transient"
    return "generic_retry"


def _rewrite_strategy_for_failure_category(category: str) -> str:
    if category == "platform_blocked":
        return "stock_footage_fallback"
    if category == "no_inventory":
        return "inventory_broaden"
    return "candidate_alternative"


def _resolve_failure_category(execution_feedback: SearchExecutionFeedback) -> str:
    structured_category = (execution_feedback.failureCategory or "").strip()
    if structured_category in _KNOWN_FAILURE_CATEGORIES:
        return structured_category
    return _classify_execution_failure(execution_feedback.failureReason)


def _resolve_rewrite_strategy(
    execution_feedback: SearchExecutionFeedback,
    failure_category: str,
) -> str:
    structured_strategy = (execution_feedback.retryStrategyHint or "").strip()
    if structured_strategy in _KNOWN_REWRITE_STRATEGIES:
        return structured_strategy
    return _rewrite_strategy_for_failure_category(failure_category)


def _rewrite_keywords_for_failed_scene(scene_keywords: list[str], rewrite_strategy: str) -> list[str]:
    core_keywords = [keyword for keyword in scene_keywords[:2] if keyword]
    keyword_set = set(core_keywords)

    if rewrite_strategy == "stock_footage_fallback":
        if {"product", "interface"} <= keyword_set:
            return ["software", "dashboard", "laptop"]
        if {"feature", "workflow"} <= keyword_set:
            return ["team", "workflow", "laptop"]
        lead = core_keywords[:1] or ["product"]
        return [*lead, "stock", "footage"]

    if rewrite_strategy == "inventory_broaden":
        return [*core_keywords, "generic"]

    return [*core_keywords, "alternative"]


def _match_brief_scene_specs(brief: str) -> list[tuple[str, list[str], int]]:
    normalized = (brief or "").lower()
    for triggers, scenes in _BRIEF_KEYWORD_RULES:
        if any(trigger.lower() in normalized for trigger in triggers):
            return scenes
    return [
        ("开场展示产品主题", ["product", "interface"], 6),
        ("展示重点功能或体验", ["feature", "workflow"], 8),
    ]


class DeterministicPlannerRuntime:
    def build_plan_from_brief(self, brief: str) -> tuple[AgentPlan, ExecutionPlan]:
        title = "智能剪辑短片"
        goal = brief.strip() or "生成产品介绍视频"
        scene_specs = _match_brief_scene_specs(brief)
        plan = AgentPlan(
            title=title,
            goal=goal,
            summary="根据用户 brief 生成的初版计划",
            scenes=[
                {
                    "id": index,
                    "purpose": "建立主题识别" if index == 1 else "突出核心内容",
                    "description": description,
                    "keywords": keywords,
                    "duration": duration,
                }
                for index, (description, keywords, duration) in enumerate(scene_specs, start=1)
            ],
        )
        execution = ExecutionPlan(
            title=title,
            targetDuration=30,
            style="快节奏社媒短片",
            scenes=[
                {
                    "id": index,
                    "description": description,
                    "keywords": keywords,
                    "searchQuery": " ".join(keywords),
                    "duration": duration,
                }
                for index, (description, keywords, duration) in enumerate(scene_specs, start=1)
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
        failure_category = _resolve_failure_category(execution_feedback)
        rewrite_strategy = _resolve_rewrite_strategy(
            execution_feedback,
            failure_category,
        )

        updated_execution_scenes = []
        for scene in current_execution.scenes:
            if scene.id in failed_scene_ids:
                next_keywords = _rewrite_keywords_for_failed_scene(
                    scene.keywords,
                    rewrite_strategy,
                )
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
                next_keywords = _rewrite_keywords_for_failed_scene(
                    scene.keywords,
                    rewrite_strategy,
                )
                updated_agent_scenes.append(
                    scene.model_copy(
                        update={
                            "status": "draft",
                            "keywords": next_keywords,
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
                        "failureCategory": failure_category,
                        "rewriteStrategy": rewrite_strategy,
                    },
                ],
            }
        )
        return next_agent, next_execution, "execution feedback 驱动的重规划已完成"

import unittest

from backend.services.planner_models import AgentObservation, AgentPlan, ExecutionPlan


class PlannerModelTests(unittest.TestCase):
    def test_initial_planning_result_wraps_agent_and_execution_plan(self):
        from backend.services.planner_models import InitialPlanningResult

        result = InitialPlanningResult(
            agentPlan={
                "title": "Notion AI 产品介绍",
                "goal": "生成 30 秒产品介绍视频",
                "summary": "突出真实产品体验",
                "scenes": [
                    {
                        "id": 1,
                        "description": "展示产品首页",
                        "keywords": ["product", "interface"],
                        "duration": 6,
                    }
                ],
            },
            executionPlan={
                "title": "Notion AI 产品介绍",
                "targetDuration": 30,
                "style": "快节奏社媒短片",
                "scenes": [
                    {
                        "id": 1,
                        "description": "展示产品首页",
                        "keywords": ["product", "interface"],
                        "searchQuery": "product interface",
                        "duration": 6,
                    }
                ],
            },
        )

        self.assertEqual(result.agentPlan.title, "Notion AI 产品介绍")
        self.assertEqual(
            result.executionPlan.scenes[0].searchQuery, "product interface"
        )

    def test_agent_plan_defaults_are_stable(self):
        plan = AgentPlan(
            title="Notion AI 产品介绍",
            goal="生成 30 秒产品介绍视频",
            summary="突出真实产品体验",
        )

        self.assertEqual(plan.openIssues, [])
        self.assertEqual(plan.replanHistory, [])
        self.assertEqual(plan.scenes, [])

    def test_execution_plan_scene_supports_grounding_candidate_ids(self):
        plan = ExecutionPlan(
            title="Demo",
            targetDuration=30,
            style="科技感",
            scenes=[
                {
                    "id": 1,
                    "description": "展示首页",
                    "searchQuery": "notion ai homepage",
                    "duration": 6,
                    "groundingCandidateIds": ["fixture:1"],
                }
            ],
        )

        self.assertEqual(plan.scenes[0].groundingCandidateIds, ["fixture:1"])

    def test_observation_payload_round_trips(self):
        observation = AgentObservation(
            id="obs-1",
            sessionId="session-1",
            observationType="user_message",
            payload={"message": "做一个产品视频"},
            createdAt="2026-05-08T00:00:00Z",
        )

        self.assertEqual(observation.payload["message"], "做一个产品视频")

    def test_grounding_feedback_contract_defaults(self):
        from backend.services.planner_models import (
            CandidateConfirmationFeedback,
            GroundingFeedback,
        )

        feedback = GroundingFeedback(
            productName="Notion",
            audience="销售团队",
            styleHint="快节奏社媒短片",
            selectedCandidateIds=["fixture:1", "fixture:2"],
            candidates=[{"id": "fixture:1", "title": "Notion product demo"}],
        )
        confirmation = CandidateConfirmationFeedback(
            selectedCandidateIds=["fixture:1", "fixture:2"],
            confirmationSource="user_select",
        )

        self.assertEqual(feedback.selectedCandidateIds, ["fixture:1", "fixture:2"])
        self.assertEqual(confirmation.confirmationSource, "user_select")

    def test_user_revision_feedback_defaults(self):
        from backend.services.planner_models import UserRevisionFeedback

        feedback = UserRevisionFeedback(
            message="整体再商务一点，品牌感再强一点",
            sceneKeywordUpdates={1: ["城市", "车流", "黄昏"]},
        )

        self.assertEqual(feedback.message, "整体再商务一点，品牌感再强一点")
        self.assertEqual(feedback.sceneKeywordUpdates[1], ["城市", "车流", "黄昏"])
        self.assertEqual(feedback.revisionSource, "user_message")

    def test_revision_scene_patch_defaults(self):
        from backend.services.planner_models import RevisionScenePatch

        patch = RevisionScenePatch(id=1)

        self.assertEqual(patch.id, 1)
        self.assertEqual(patch.description, "")
        self.assertEqual(patch.keywords, [])
        self.assertEqual(patch.searchQuery, "")

    def test_revision_planning_result_wraps_scene_patches(self):
        from backend.services.planner_models import RevisionPlanningResult

        result = RevisionPlanningResult(
            summary="整体更偏商务演示",
            audience="销售团队",
            styleHint="商务演示风格",
            style="商务演示风格",
            changeSummary="已根据最新修改意见完成计划重写",
            scenePatches=[
                {
                    "id": 1,
                    "description": "城市节奏感开场，建立商务氛围",
                    "keywords": ["city", "traffic", "dusk"],
                    "searchQuery": "city traffic dusk",
                }
            ],
        )

        self.assertEqual(result.audience, "销售团队")
        self.assertEqual(result.scenePatches[0].id, 1)
        self.assertEqual(result.scenePatches[0].searchQuery, "city traffic dusk")

    def test_search_execution_feedback_defaults(self):
        from backend.services.planner_models import SearchExecutionFeedback

        feedback = SearchExecutionFeedback(
            failedSceneIds=[1, 2],
            failureReason="素材检索失败",
            retryable=True,
        )

        self.assertEqual(feedback.failedSceneIds, [1, 2])
        self.assertEqual(feedback.failureReason, "素材检索失败")
        self.assertEqual(feedback.feedbackSource, "worker_failure")

    def test_search_execution_feedback_supports_structured_diagnostics(self):
        from backend.services.planner_models import SearchExecutionFeedback

        feedback = SearchExecutionFeedback(
            failedSceneIds=[1],
            failureReason="",
            failureCategory="platform_blocked",
            primaryProvider="youtube",
            providerDiagnostics=[
                {
                    "provider": "youtube",
                    "message": "YouTube 当前要求 PO Token，公开视频下载被平台策略限制。",
                }
            ],
            sceneDiagnostics=[
                {
                    "sceneId": 1,
                    "retryable": True,
                    "summary": "YouTube blocked the download path",
                }
            ],
            retryStrategyHint="stock_footage_fallback",
        )

        self.assertEqual(feedback.failureReason, "")
        self.assertEqual(feedback.failureCategory, "platform_blocked")
        self.assertEqual(feedback.primaryProvider, "youtube")
        self.assertEqual(
            feedback.providerDiagnostics[0]["message"],
            "YouTube 当前要求 PO Token，公开视频下载被平台策略限制。",
        )
        self.assertEqual(feedback.sceneDiagnostics[0]["sceneId"], 1)
        self.assertEqual(feedback.retryStrategyHint, "stock_footage_fallback")

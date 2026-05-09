import unittest

from backend.services.planner_models import AgentObservation, AgentPlan, ExecutionPlan


class PlannerModelTests(unittest.TestCase):
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

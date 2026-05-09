import unittest
from unittest.mock import Mock, patch


class PlannerGraphTests(unittest.TestCase):
    def test_build_plan_graph_returns_initial_plan_state(self):
        from backend.services.planner_graph import run_initial_planning
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

        agent_plan, execution_plan = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品视频"
        )
        fake_runtime = Mock()
        fake_runtime.build_plan_from_brief.return_value = (agent_plan, execution_plan)

        with patch(
            "backend.services.planner_graph.get_planner_runtime",
            return_value=fake_runtime,
        ):
            state = run_initial_planning(
                session_id="session-1",
                brief="给 Notion AI 做一个 30 秒产品视频",
            )

        self.assertEqual(state["status"], "planning_complete")
        self.assertIn("agentPlan", state)
        self.assertIn("executionPlan", state)

    def test_run_grounding_replan_returns_replanning_complete_state(self):
        from backend.services.planner_graph import run_grounding_replan
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief("做一个产品视频")
        with patch(
            "backend.services.planner_graph.get_planner_runtime",
            return_value=runtime,
        ):
            state = run_grounding_replan(
                session_id="session-1",
                current_agent_plan=current_agent.model_dump(mode="json"),
                current_execution_plan=current_execution.model_dump(mode="json"),
                grounding_feedback={
                    "productName": "Notion",
                    "selectedCandidateIds": ["fixture:1"],
                    "candidates": [{"id": "fixture:1", "title": "Notion demo"}],
                },
                confirmation_feedback={
                    "selectedCandidateIds": ["fixture:1"],
                    "confirmationSource": "user_select",
                },
            )

        self.assertEqual(state["status"], "replanning_complete")
        self.assertEqual(state["triggerType"], "grounding_confirmation")
        self.assertIn("changeSummary", state)

    def test_run_user_revision_replan_returns_replanning_complete_state(self):
        from backend.services.planner_graph import run_user_revision_replan
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief("做一个产品视频")

        with patch(
            "backend.services.planner_graph.get_planner_runtime",
            return_value=runtime,
        ):
            state = run_user_revision_replan(
                session_id="session-1",
                current_agent_plan=current_agent.model_dump(mode="json"),
                current_execution_plan=current_execution.model_dump(mode="json"),
                revision_feedback={
                    "message": "更商务一点，目标受众改成销售团队",
                    "sceneKeywordUpdates": {1: ["城市", "车流", "黄昏"]},
                    "revisionSource": "user_message",
                },
            )

        self.assertEqual(state["status"], "replanning_complete")
        self.assertEqual(state["triggerType"], "user_revision")
        self.assertIn("changeSummary", state)

    def test_run_execution_feedback_replan_returns_replanning_complete_state(self):
        from backend.services.planner_graph import run_execution_feedback_replan
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief("做一个产品视频")

        with patch(
            "backend.services.planner_graph.get_planner_runtime",
            return_value=runtime,
        ):
            state = run_execution_feedback_replan(
                session_id="session-1",
                current_agent_plan=current_agent.model_dump(mode="json"),
                current_execution_plan=current_execution.model_dump(mode="json"),
                execution_feedback={
                    "failedSceneIds": [1],
                    "failureReason": "素材检索失败",
                    "retryable": True,
                    "feedbackSource": "worker_failure",
                },
            )

        self.assertEqual(state["status"], "replanning_complete")
        self.assertEqual(state["triggerType"], "execution_feedback")
        self.assertIn("changeSummary", state)

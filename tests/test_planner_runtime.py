import unittest
from unittest.mock import patch


class PlannerRuntimeTests(unittest.TestCase):
    def test_deterministic_runtime_builds_stable_two_scene_plan(self):
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        agent_plan, execution_plan = runtime.build_plan_from_brief("给 Notion AI 做一个视频")

        self.assertEqual(agent_plan.title, "智能剪辑短片")
        self.assertEqual(agent_plan.goal, "给 Notion AI 做一个视频")
        self.assertEqual(len(agent_plan.scenes), 2)
        self.assertEqual(len(execution_plan.scenes), 2)
        self.assertEqual(execution_plan.scenes[0].searchQuery, "product interface")
        self.assertEqual(execution_plan.scenes[1].searchQuery, "feature workflow")

    def test_deterministic_runtime_uses_default_goal_for_blank_brief(self):
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        agent_plan, _execution_plan = runtime.build_plan_from_brief("   ")

        self.assertEqual(agent_plan.goal, "生成产品介绍视频")

    def test_selector_returns_deterministic_runtime_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            from backend.config import get_settings
            from backend.services.planner_runtime import get_planner_runtime

            get_settings.cache_clear()
            runtime = get_planner_runtime()
            self.assertEqual(runtime.__class__.__name__, "DeterministicPlannerRuntime")
            get_settings.cache_clear()

    def test_deterministic_runtime_replans_after_grounding(self):
        from backend.services.planner_models import (
            CandidateConfirmationFeedback,
            GroundingFeedback,
        )
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个产品短片"
        )
        next_agent, next_execution, change_summary = runtime.replan_after_grounding(
            current_agent=current_agent,
            current_execution=current_execution,
            grounding_feedback=GroundingFeedback(
                productName="Notion",
                audience="销售团队",
                styleHint="商务演示风格",
                featureHints=["协作", "看板"],
                selectedCandidateIds=["fixture:1", "fixture:2"],
                candidates=[{"id": "fixture:1", "title": "Notion dashboard"}],
            ),
            confirmation_feedback=CandidateConfirmationFeedback(
                selectedCandidateIds=["fixture:1", "fixture:2"],
                confirmationSource="user_select",
            ),
        )

        self.assertIn("grounding", change_summary)
        self.assertEqual(next_execution.style, "商务演示风格")
        self.assertEqual(
            next_execution.scenes[0].groundingCandidateIds,
            ["fixture:1", "fixture:2"],
        )
        self.assertGreaterEqual(len(next_agent.replanHistory), 1)

    def test_deterministic_runtime_replans_after_user_revision(self):
        from backend.services.planner_models import UserRevisionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        next_agent, next_execution, change_summary = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="整体再商务一点，目标受众改成销售团队，场景1：城市 车流 黄昏",
                sceneKeywordUpdates={1: ["城市", "车流", "黄昏"]},
            ),
        )

        self.assertIn("revision", change_summary)
        self.assertEqual(next_execution.style, "商务演示风格")
        self.assertEqual(next_execution.scenes[0].keywords, ["城市", "车流", "黄昏"])
        self.assertEqual(next_execution.scenes[0].searchQuery, "城市 车流 黄昏")
        self.assertEqual(next_agent.understanding.audience, "销售团队")
        self.assertGreaterEqual(len(next_agent.replanHistory), 1)

    def test_deterministic_runtime_replans_after_execution_feedback(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        next_agent, next_execution, change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[1],
                failureReason="素材检索失败",
                retryable=True,
            ),
        )

        self.assertIn("execution", change_summary)
        self.assertEqual(next_execution.scenes[0].searchQuery, "product interface alternative")
        self.assertEqual(
            next_execution.scenes[0].keywords,
            ["product", "interface", "alternative"],
        )
        self.assertGreaterEqual(len(next_agent.replanHistory), 1)

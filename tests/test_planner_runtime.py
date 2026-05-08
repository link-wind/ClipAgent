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

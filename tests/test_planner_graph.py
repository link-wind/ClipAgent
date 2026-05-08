import unittest


class PlannerGraphTests(unittest.TestCase):
    def test_build_plan_graph_returns_initial_plan_state(self):
        from backend.services.planner_graph import run_initial_planning

        state = run_initial_planning(
            session_id="session-1",
            brief="给 Notion AI 做一个 30 秒产品视频",
        )

        self.assertEqual(state["status"], "planning_complete")
        self.assertIn("agentPlan", state)
        self.assertIn("executionPlan", state)

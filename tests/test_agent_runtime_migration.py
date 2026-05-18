import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.models.agent import AgentSession, AgentStatus


ROOT = Path(__file__).resolve().parents[1]


class AgentRuntimeMigrationTests(unittest.TestCase):
    def test_build_agent_runtime_wires_runtime_dependencies(self):
        from backend.runtime.agent_runtime import AgentRuntime, build_agent_runtime

        runtime = build_agent_runtime(
            session_service=object(),
            execution_service=object(),
        )

        self.assertIsInstance(runtime, AgentRuntime)
        self.assertTrue(hasattr(runtime, "context_engine"))
        self.assertTrue(hasattr(runtime, "skill_engine"))
        self.assertTrue(hasattr(runtime, "tool_gateway"))
        self.assertTrue(hasattr(runtime, "trace_recorder"))

    def test_build_agent_runtime_injects_shared_runtime_components_into_session_service(self):
        from backend.runtime.agent_runtime import build_agent_runtime

        runtime = build_agent_runtime()

        self.assertIs(runtime.session_service.planner_orchestrator.context_engine, runtime.context_engine)
        self.assertIs(runtime.session_service.planner_orchestrator.skill_engine, runtime.skill_engine)
        self.assertIs(runtime.session_service.planner_orchestrator.trace_recorder, runtime.trace_recorder)

    def test_agent_api_routes_create_session_through_runtime(self):
        import backend.api.agent as agent_api

        class FakeRuntime:
            def __init__(self):
                self.messages = []

            def create_session(self, message):
                self.messages.append(message)
                return AgentSession(id="runtime-session", status=AgentStatus.IDLE)

        runtime = FakeRuntime()

        async def run_test():
            with patch.object(agent_api, "build_agent_runtime", return_value=runtime):
                response = await agent_api.create_session(agent_api.SessionCreateRequest(message="hello"))
            self.assertEqual(response.id, "runtime-session")
            self.assertEqual(runtime.messages, ["hello"])

        asyncio.run(run_test())

    def test_agent_api_routes_confirm_plan_through_runtime(self):
        import backend.api.agent as agent_api

        class FakeRuntime:
            def __init__(self):
                self.confirmed_session_ids = []

            def confirm_plan(self, session_id):
                self.confirmed_session_ids.append(session_id)
                return AgentSession(id=session_id, status=AgentStatus.QUEUED)

        runtime = FakeRuntime()

        async def run_test():
            with patch.object(agent_api, "build_agent_runtime", return_value=runtime):
                response = await agent_api.confirm_session("session-1")
            self.assertEqual(response.id, "session-1")
            self.assertEqual(response.status, AgentStatus.QUEUED)
            self.assertEqual(runtime.confirmed_session_ids, ["session-1"])

        asyncio.run(run_test())

    def test_agent_api_source_calls_runtime_facade_for_write_routes(self):
        source = (ROOT / "backend" / "api" / "agent.py").read_text(encoding="utf-8")

        self.assertIn("build_agent_runtime", source)
        self.assertIn("runtime.create_session", source)
        self.assertIn("runtime.submit_message", source)
        self.assertIn("runtime.confirm_grounding", source)
        self.assertIn("runtime.confirm_plan", source)


if __name__ == "__main__":
    unittest.main()

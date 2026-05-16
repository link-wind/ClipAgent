from __future__ import annotations

import unittest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base


class MCPFoundationDomainTests(unittest.TestCase):
    def test_tool_definition_contract_is_stable(self) -> None:
        from backend.domain.tools.contracts import ToolDefinition

        definition = ToolDefinition(
            id="read_project_knowledge",
            name="Read Project Knowledge",
            description="Read knowledge sources for the current project.",
            category="knowledge",
            permissions={"scope": "project", "mode": "read_only"},
            source_type="local_builtin",
            tool_name="read_project_knowledge",
            status="active",
            timeout_ms=3000,
        )

        self.assertEqual(definition.id, "read_project_knowledge")
        self.assertEqual(definition.name, "Read Project Knowledge")
        self.assertEqual(
            definition.description,
            "Read knowledge sources for the current project.",
        )
        self.assertEqual(definition.category, "knowledge")
        self.assertEqual(definition.input_schema, {})
        self.assertEqual(definition.output_schema, {})
        self.assertEqual(definition.permissions["mode"], "read_only")
        self.assertEqual(definition.permissions["scope"], "project")
        self.assertEqual(definition.source_type, "local_builtin")
        self.assertEqual(definition.status, "active")
        self.assertIsNone(definition.mcp_server_id)
        self.assertEqual(definition.tool_name, "read_project_knowledge")
        self.assertEqual(definition.timeout_ms, 3000)

    def test_tool_call_summary_contract_keeps_result_reference(self) -> None:
        from backend.domain.tools.contracts import ToolCallSummary

        summary = ToolCallSummary(
            tool_id="read_last_failure_diagnostic",
            status="succeeded",
            result_summary="Read latest failure diagnostic summary.",
            result_ref="observation:diag-1",
            error_message="",
        )

        self.assertEqual(summary.tool_id, "read_last_failure_diagnostic")
        self.assertEqual(summary.status, "succeeded")
        self.assertEqual(
            summary.result_summary,
            "Read latest failure diagnostic summary.",
        )
        self.assertEqual(summary.result_ref, "observation:diag-1")
        self.assertEqual(summary.error_message, "")


class MCPFoundationRegistryTests(unittest.TestCase):
    def test_builtin_tool_registry_lists_four_read_only_definitions(self) -> None:
        from backend.app.tools.registry import BuiltinToolRegistry

        registry = BuiltinToolRegistry()

        definitions = registry.list_definitions()

        self.assertEqual(
            [definition.id for definition in definitions],
            [
                "read_project_knowledge",
                "read_asset_metadata",
                "read_runtime_settings",
                "read_last_failure_diagnostic",
            ],
        )
        self.assertTrue(all(definition.source_type == "local_builtin" for definition in definitions))
        self.assertTrue(all(definition.permissions["mode"] == "read_only" for definition in definitions))

    def test_builtin_tool_registry_reads_builtin_tool_modules(self) -> None:
        from backend.app.tools.registry import BuiltinToolRegistry

        registry = BuiltinToolRegistry()

        definition = registry.get_definition("read_project_knowledge")

        self.assertEqual(definition.name, "Read Project Knowledge")
        self.assertEqual(definition.category, "knowledge")
        self.assertTrue(definition.tool_name.endswith(":read_project_knowledge"))

    def test_tool_permission_service_allows_matching_read_only_scope(self) -> None:
        from backend.app.tools.permission_service import PermissionDecision, ToolPermissionService
        from backend.domain.tools.contracts import ToolPermission

        service = ToolPermissionService()

        decision = service.decide(
            ToolPermission(scope="project", mode="read_only"),
            requested_scope="project",
        )

        self.assertIsInstance(decision, PermissionDecision)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "allowed")

    def test_tool_permission_service_denies_scope_mismatch(self) -> None:
        from backend.app.tools.permission_service import ToolPermissionService
        from backend.domain.tools.contracts import ToolPermission

        service = ToolPermissionService()

        decision = service.decide(
            ToolPermission(scope="project", mode="read_only"),
            requested_scope="session",
        )

        self.assertFalse(decision.allowed)
        self.assertIn("session", decision.reason)


class MCPFoundationGatewayTests(unittest.TestCase):
    def test_tool_gateway_dispatches_builtin_tool_and_normalizes_result(self) -> None:
        from backend.app.tools.tool_call_service import ToolCallService
        from backend.db.repositories.tool_calls import ToolCallRepository
        from backend.runtime.tool_gateway import ToolCallRequest, ToolGateway
        from backend.runtime.trace_recorder import TraceRecorder

        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine, future=True)
        db = SessionLocal()

        from backend.db.models import AgentRunRecord, AgentSessionRecord

        db.add(
            AgentSessionRecord(
                id="session-1",
                status="active",
                progress=0.0,
                active_operation_type="none",
                planner_trace_json={},
            )
        )
        db.commit()
        db.add(
            AgentRunRecord(
                id="run-1",
                session_id="session-1",
                trigger_type="planning",
                status="running",
            )
        )
        db.commit()
        from backend.db.repositories import AgentStepRepository

        step = AgentStepRepository(db).create(
            id="step-record-1",
            session_id="session-1",
            run_id="run-1",
            step_key="retrieve_context",
            title="Retrieve context",
            description="",
            status="running",
        )
        db.commit()

        gateway = ToolGateway(
            tool_call_service=ToolCallService(
                db_session=db,
                tool_call_repository=ToolCallRepository(db),
                trace_recorder=TraceRecorder(db),
            )
        )

        result = gateway.call_tool(
            ToolCallRequest(
                session_id="session-1",
                run_id="run-1",
                step_id=step.id,
                tool_id="read_project_knowledge",
                arguments={"documentId": "doc-1"},
                permission_scope="project",
            )
        )

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.data["summary"], "Project knowledge is read only in this foundation.")
        self.assertEqual(result.result_summary, "Project knowledge is read only in this foundation.")
        self.assertTrue(result.result_ref.startswith("tool:read_project_knowledge"))
        self.assertEqual(result.error_message, "")

        from backend.db.repositories import AgentTraceEventRepository
        from backend.db.repositories.tool_calls import ToolCallRepository

        tool_calls = ToolCallRepository(db).list_for_run("run-1")
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0].actor, "agent_runtime")
        self.assertEqual(tool_calls[0].actor_role, "planner")
        self.assertLessEqual(len(tool_calls[0].id), 64)

        events = AgentTraceEventRepository(db).list_for_session("session-1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "tool_call_recorded")
        self.assertEqual(events[0].actor_role, "planner")

        db.close()
        engine.dispose()

    def test_tool_gateway_denies_scope_mismatch_before_dispatch(self) -> None:
        from backend.runtime.tool_gateway import ToolCallRequest, ToolGateway

        gateway = ToolGateway()

        result = gateway.call_tool(
            ToolCallRequest(
                session_id="session-1",
                run_id="run-1",
                step_id="retrieve_context",
                tool_id="read_project_knowledge",
                permission_scope="session",
            )
        )

        self.assertEqual(result.status, "skipped")
        self.assertIn("scope mismatch", result.error_message)

    def test_tool_gateway_normalizes_handler_failure(self) -> None:
        from backend.domain.tools.contracts import ToolDefinition
        from backend.runtime.tool_gateway import ToolCallRequest, ToolGateway

        class FailingRegistry:
            def get_definition(self, _tool_id: str) -> ToolDefinition:
                return ToolDefinition(
                    id="failing_tool",
                    name="Failing Tool",
                    description="Always fails.",
                    category="diagnostics",
                    permissions={"scope": "session", "mode": "read_only"},
                    source_type="local_builtin",
                    tool_name="ignored",
                )

            def resolve_handler(self, _tool_id: str):
                def _raise(**_kwargs):
                    raise RuntimeError("boom")

                return _raise

        gateway = ToolGateway(registry=FailingRegistry())

        result = gateway.call_tool(
            ToolCallRequest(
                session_id="session-1",
                run_id="run-1",
                step_id="step-1",
                tool_id="failing_tool",
                permission_scope="session",
            )
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.result_summary, "Tool failing_tool failed.")
        self.assertEqual(result.result_ref, "tool:failing_tool")
        self.assertIn("boom", result.error_message)


class MCPFoundationPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

        @event.listens_for(self.engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, future=True)
        self.db = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_tool_call_repository_creates_and_reads_tool_calls(self) -> None:
        from backend.db.models import AgentRunRecord, AgentSessionRecord
        from backend.db.repositories.tool_calls import ToolCallRepository

        session = AgentSessionRecord(
            id="session-1",
            status="active",
            progress=0.0,
            active_operation_type="none",
            planner_trace_json={},
        )
        self.db.add(session)
        self.db.commit()

        run = AgentRunRecord(
            id="run-1",
            session_id="session-1",
            trigger_type="planning",
            status="running",
        )
        self.db.add(run)
        self.db.commit()

        repository = ToolCallRepository(self.db)
        record = repository.create_tool_call(
            id="tool-call-1",
            run_id="run-1",
            step_id="retrieve_context",
            tool_id="read_project_knowledge",
            status="succeeded",
            arguments_json={"documentId": "doc-1"},
            result_summary="Read one project knowledge document.",
            result_ref="knowledge:doc-1",
            error_message="",
            actor="agent_runtime",
            actor_role="planner",
        )

        self.assertEqual(record.tool_id, "read_project_knowledge")
        loaded = repository.list_for_run("run-1")
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].result_ref, "knowledge:doc-1")

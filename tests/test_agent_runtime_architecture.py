from __future__ import annotations

import importlib
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AgentRuntimeArchitectureTests(unittest.TestCase):
    def test_target_architecture_packages_exist(self) -> None:
        expected_paths = [
            "backend/app/__init__.py",
            "backend/app/agent/__init__.py",
            "backend/app/execution/__init__.py",
            "backend/app/planning/__init__.py",
            "backend/runtime/__init__.py",
            "backend/runtime/agent_runtime.py",
            "backend/runtime/context_engine.py",
            "backend/runtime/skill_engine.py",
            "backend/runtime/tool_gateway.py",
            "backend/runtime/trace_recorder.py",
            "backend/domain/__init__.py",
            "backend/domain/agent/__init__.py",
            "backend/domain/skills/__init__.py",
            "backend/domain/skills/contracts.py",
            "backend/domain/planning/__init__.py",
            "backend/infrastructure/__init__.py",
            "backend/infrastructure/config/__init__.py",
            "backend/infrastructure/media/__init__.py",
            "backend/workers/__init__.py",
            "backend/workers/tasks/__init__.py",
        ]

        for relative_path in expected_paths:
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)

    def test_application_boundary_reexports_existing_use_cases(self) -> None:
        session_use_cases = importlib.import_module("backend.app.agent.session_use_cases")
        job_use_cases = importlib.import_module("backend.app.execution.job_use_cases")
        planning_orchestrator = importlib.import_module("backend.app.planning.orchestrator")

        self.assertTrue(hasattr(session_use_cases, "AgentSessionService"))
        self.assertTrue(hasattr(session_use_cases, "AgentReadService"))
        self.assertTrue(hasattr(job_use_cases, "AgentExecutionService"))
        self.assertTrue(hasattr(job_use_cases, "AgentTaskReadService"))
        self.assertTrue(hasattr(planning_orchestrator, "PlannerOrchestrator"))

    def test_planning_orchestrator_lives_in_app_planning_boundary(self) -> None:
        source_path = ROOT / "backend" / "app" / "planning" / "orchestrator.py"
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertTrue(
            any(isinstance(node, ast.ClassDef) and node.name == "PlannerOrchestrator" for node in module.body),
            "PlannerOrchestrator must be implemented in backend.app.planning.orchestrator",
        )
        self.assertIn("ContextEngine", source)
        self.assertIn("SkillEngine", source)
        self.assertIn("run_initial_planning", source)

    def test_legacy_planner_orchestrator_module_is_shim(self) -> None:
        source_path = ROOT / "backend" / "services" / "planner_orchestrator.py"
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertIn(
            "from backend.app.planning.orchestrator import PlannerOrchestrator",
            source,
        )
        self.assertFalse(
            any(isinstance(node, ast.ClassDef) and node.name == "PlannerOrchestrator" for node in module.body),
            "backend.services.planner_orchestrator must remain a shim",
        )

    def test_media_infrastructure_does_not_reexport_services_render_module(self) -> None:
        render_source = (ROOT / "backend" / "infrastructure" / "media" / "render_service.py").read_text(encoding="utf-8")

        self.assertNotIn("from backend.services.render_service import", render_source)

    def test_execution_services_use_media_infrastructure_adapters(self) -> None:
        asset_source = (ROOT / "backend" / "app" / "execution" / "asset_execution_service.py").read_text(encoding="utf-8")
        render_source = (ROOT / "backend" / "app" / "execution" / "render_execution_service.py").read_text(encoding="utf-8")

        self.assertIn("backend.infrastructure.media.search_service", asset_source)
        self.assertIn("backend.infrastructure.media.render_service", render_source)

    def test_app_agent_contains_real_session_and_read_implementations(self) -> None:
        session_source = (ROOT / "backend" / "app" / "agent" / "session_service.py").read_text(encoding="utf-8")
        read_source = (ROOT / "backend" / "app" / "agent" / "read_service.py").read_text(encoding="utf-8")

        self.assertIn("class AgentSessionService", session_source)
        self.assertIn("class AgentReadService", read_source)
        self.assertIn("PlannerOrchestrator", session_source)
        self.assertIn("StepProjectionService", read_source)

    def test_migrated_agent_services_are_compatibility_shims(self) -> None:
        session_source = (ROOT / "backend" / "services" / "agent_session_service.py").read_text(encoding="utf-8")
        read_source = (ROOT / "backend" / "services" / "agent_read_service.py").read_text(encoding="utf-8")

        self.assertIn("from backend.app.agent.session_service import AgentSessionService", session_source)
        self.assertIn("from backend.app.agent.read_service import AgentReadService", read_source)
        self.assertNotIn("class AgentSessionService", session_source)
        self.assertNotIn("class AgentReadService", read_source)

    def test_agent_session_and_read_services_live_in_app_agent_boundary(self) -> None:
        expected_classes = {
            "read_service.py": "AgentReadService",
            "session_service.py": "AgentSessionService",
        }

        for filename, class_name in expected_classes.items():
            source_path = ROOT / "backend" / "app" / "agent" / filename
            self.assertTrue(source_path.is_file(), str(source_path))
            module = ast.parse(source_path.read_text(encoding="utf-8"))
            self.assertTrue(
                any(isinstance(node, ast.ClassDef) and node.name == class_name for node in module.body),
                f"{class_name} must be implemented in backend.app.agent.{source_path.stem}",
            )

    def test_legacy_agent_service_modules_are_shims(self) -> None:
        shim_modules = {
            "agent_read_service.py": (
                "AgentReadService",
                "from backend.app.agent.read_service import AgentReadService",
            ),
            "agent_session_service.py": (
                "AgentSessionService",
                "from backend.app.agent.session_service import AgentSessionService",
            ),
        }

        for filename, (class_name, expected_import) in shim_modules.items():
            source_path = ROOT / "backend" / "services" / filename
            source = source_path.read_text(encoding="utf-8")
            module = ast.parse(source)
            self.assertIn(expected_import, source)
            self.assertFalse(
                any(isinstance(node, ast.ClassDef) and node.name == class_name for node in module.body),
                f"backend.services.{source_path.stem} must remain a shim",
            )

    def test_runtime_contracts_import_without_side_effects(self) -> None:
        context_engine = importlib.import_module("backend.runtime.context_engine")
        skill_engine = importlib.import_module("backend.runtime.skill_engine")
        tool_gateway = importlib.import_module("backend.runtime.tool_gateway")
        trace_recorder = importlib.import_module("backend.runtime.trace_recorder")
        agent_runtime = importlib.import_module("backend.runtime.agent_runtime")

        self.assertTrue(hasattr(context_engine, "ContextEngine"))
        self.assertTrue(hasattr(skill_engine, "SkillEngine"))
        self.assertTrue(hasattr(tool_gateway, "ToolGateway"))
        self.assertTrue(hasattr(trace_recorder, "TraceRecorder"))
        self.assertTrue(hasattr(agent_runtime, "AgentRuntime"))

    def test_runtime_factory_builds_app_layer_services_not_service_layer_directly(self) -> None:
        source = (ROOT / "backend" / "runtime" / "agent_runtime.py").read_text(encoding="utf-8")

        self.assertIn("from backend.app.agent.session_service import AgentSessionService", source)
        self.assertIn("from backend.app.execution.job_use_cases import AgentExecutionService", source)
        self.assertNotIn("from backend.services.agent_session_service import", source)

    def test_mcp_foundation_boundaries_import(self) -> None:
        tool_contracts = importlib.import_module("backend.domain.tools.contracts")
        tool_registry = importlib.import_module("backend.app.tools.registry")
        permission_service = importlib.import_module("backend.app.tools.permission_service")
        tool_call_service = importlib.import_module("backend.app.tools.tool_call_service")
        local_adapter = importlib.import_module("backend.infrastructure.tools.local_adapter")
        mcp_adapter = importlib.import_module("backend.infrastructure.tools.mcp_adapter")

        self.assertTrue(hasattr(tool_contracts, "ToolDefinition"))
        self.assertTrue(hasattr(tool_contracts, "ToolCallSummary"))
        self.assertTrue(hasattr(tool_registry, "BuiltinToolRegistry"))
        self.assertTrue(hasattr(permission_service, "ToolPermissionService"))
        self.assertTrue(hasattr(tool_call_service, "ToolCallService"))
        self.assertTrue(hasattr(local_adapter, "LocalToolAdapter"))
        self.assertTrue(hasattr(mcp_adapter, "MCPToolAdapter"))

    def test_infrastructure_and_worker_boundaries_reexport_existing_adapters(self) -> None:
        runtime_config = importlib.import_module("backend.infrastructure.config.runtime_config_service")
        render_service = importlib.import_module("backend.infrastructure.media.render_service")
        asset_providers = importlib.import_module("backend.infrastructure.media.asset_providers")
        celery_app = importlib.import_module("backend.workers.celery_app")
        agent_job = importlib.import_module("backend.workers.tasks.agent_job")

        self.assertTrue(hasattr(runtime_config, "runtime_config_service"))
        self.assertTrue(hasattr(runtime_config, "DEFAULT_YTDLP_FORMAT"))
        self.assertTrue(hasattr(render_service, "render_video"))
        self.assertTrue(hasattr(render_service, "RenderClip"))
        self.assertTrue(hasattr(render_service, "RenderProgressCallback"))
        self.assertTrue(hasattr(asset_providers, "ProviderDiagnostic"))
        self.assertTrue(hasattr(asset_providers, "ProviderResult"))
        self.assertTrue(hasattr(celery_app, "celery_app"))
        self.assertTrue(hasattr(agent_job, "run_agent_job"))

    def test_asset_provider_infrastructure_submodules_reexport_existing_adapters(self) -> None:
        config = importlib.import_module("backend.infrastructure.media.asset_providers.config")
        fixture = importlib.import_module("backend.infrastructure.media.asset_providers.fixture")
        metadata = importlib.import_module("backend.infrastructure.media.asset_providers.metadata")
        pexels = importlib.import_module("backend.infrastructure.media.asset_providers.pexels")
        youtube = importlib.import_module("backend.infrastructure.media.asset_providers.youtube")

        self.assertTrue(hasattr(config, "get_asset_provider_order"))
        self.assertTrue(hasattr(config, "YoutubeProviderConfig"))
        self.assertTrue(hasattr(fixture, "search_fixture_candidates"))
        self.assertTrue(hasattr(fixture, "download_fixture_candidate"))
        self.assertTrue(hasattr(metadata, "remember_clip_metadata"))
        self.assertTrue(hasattr(metadata, "pop_clip_metadata"))
        self.assertTrue(hasattr(pexels, "search_pexels_candidates"))
        self.assertTrue(hasattr(pexels, "download_pexels_candidate"))
        self.assertTrue(hasattr(youtube, "build_youtube_search_options"))
        self.assertTrue(hasattr(youtube, "search_youtube_candidates"))

    def test_agent_runtime_accepts_existing_services(self) -> None:
        from backend.runtime.agent_runtime import AgentRuntime
        from backend.runtime.context_engine import ContextEngine
        from backend.runtime.skill_engine import SkillEngine
        from backend.runtime.tool_gateway import ToolGateway
        from backend.runtime.trace_recorder import TraceRecorder

        runtime = AgentRuntime(
            session_service=object(),
            execution_service=object(),
            context_engine=ContextEngine(),
            skill_engine=SkillEngine(),
            tool_gateway=ToolGateway(),
            trace_recorder=TraceRecorder(),
        )

        self.assertIsNotNone(runtime)

    def test_agent_api_imports_use_application_boundary(self) -> None:
        source = (ROOT / "backend" / "api" / "agent.py").read_text(encoding="utf-8")

        self.assertIn(
            "from backend.app.agent.session_use_cases import AgentReadService, AgentSessionService",
            source,
        )
        self.assertIn(
            "from backend.app.execution.job_use_cases import AgentExecutionService, AgentTaskReadService",
            source,
        )
        self.assertNotIn("from backend.services.agent_execution_service import", source)
        self.assertNotIn("from backend.services.agent_session_service import", source)

    def test_readme_documents_agent_runtime_architecture(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Agent Runtime 架构", readme)
        self.assertIn("Context Engine", readme)
        self.assertIn("Skill Engine", readme)
        self.assertIn("Tool Gateway", readme)
        self.assertIn("RAG", readme)
        self.assertIn("MCP", readme)

    def test_rag_foundation_boundaries_import(self) -> None:
        knowledge_contracts = importlib.import_module("backend.domain.knowledge.contracts")
        retrieval_service = importlib.import_module("backend.app.knowledge.retrieval_service")
        ingestion_service = importlib.import_module("backend.app.knowledge.ingestion_service")
        context_usage_service = importlib.import_module("backend.app.knowledge.context_usage_service")
        retrieval_pipeline = importlib.import_module("backend.app.knowledge.retrieval_pipeline")
        lightweight_index = importlib.import_module("backend.infrastructure.vector.lightweight_index")
        vector_store = importlib.import_module("backend.infrastructure.vector.store")

        self.assertTrue(hasattr(knowledge_contracts, "KnowledgeChunk"))
        self.assertTrue(hasattr(knowledge_contracts, "RetrievalResult"))
        self.assertTrue(hasattr(knowledge_contracts, "ContextUsage"))
        self.assertTrue(hasattr(retrieval_service, "KnowledgeRetrievalService"))
        self.assertTrue(hasattr(ingestion_service, "KnowledgeIngestionService"))
        self.assertTrue(hasattr(context_usage_service, "ContextUsageService"))
        self.assertTrue(hasattr(retrieval_pipeline, "RetrievalDiagnostics"))
        self.assertTrue(hasattr(retrieval_pipeline, "RetrievalPipelineResult"))
        self.assertTrue(hasattr(retrieval_pipeline, "RetrievalPipeline"))
        self.assertTrue(hasattr(retrieval_pipeline, "IdentityReranker"))
        self.assertTrue(hasattr(lightweight_index, "LightweightVectorIndex"))
        self.assertTrue(hasattr(vector_store, "VectorStore"))
        self.assertTrue(hasattr(vector_store, "KeywordVectorStore"))

    def test_skill_foundation_boundaries_import(self) -> None:
        skill_contracts = importlib.import_module("backend.domain.skills.contracts")
        skill_domain = importlib.import_module("backend.domain.skills")
        skill_registry = importlib.import_module("backend.app.skills.registry")
        selection_service = importlib.import_module("backend.app.skills.selection_service")
        product_handlers = importlib.import_module("backend.skills.builtin.product_intro_video.handlers")
        repair_handlers = importlib.import_module(
            "backend.skills.builtin.execution_feedback_replan.handlers"
        )

        self.assertTrue(hasattr(skill_contracts, "SkillDefinition"))
        self.assertTrue(hasattr(skill_contracts, "PlannerRequest"))
        self.assertTrue(hasattr(skill_contracts, "SkillSelectionRequest"))
        self.assertTrue(hasattr(skill_contracts, "SkillSelection"))
        self.assertTrue(hasattr(skill_contracts, "SkillRunSummary"))
        self.assertTrue(hasattr(skill_domain, "SkillDefinition"))
        self.assertTrue(hasattr(skill_domain, "PlannerRequest"))
        self.assertTrue(hasattr(skill_domain, "SkillSelectionRequest"))
        self.assertTrue(hasattr(skill_domain, "SkillSelection"))
        self.assertTrue(hasattr(skill_domain, "SkillRunSummary"))
        self.assertTrue(hasattr(skill_registry, "BuiltinSkillRegistry"))
        self.assertTrue(hasattr(selection_service, "SkillSelectionService"))
        self.assertTrue(hasattr(product_handlers, "build_product_intro_planner_request"))
        self.assertTrue(hasattr(repair_handlers, "build_execution_feedback_replan_request"))

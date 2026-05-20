from __future__ import annotations

import importlib
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FROZEN_COMPAT_MODULES: set[str] = set()
TASK6_RETIRED_TEST_SERVICE_MODULES = {
    "backend.services.runtime_config_service",
    "backend.services.render_service",
    "backend.services.grounding_planner_models",
    "backend.services.grounding_planner_runtime",
    "backend.services.grounding_service",
    "backend.services.agent_diagnostic_service",
    "backend.services.agent_progress_service",
    "backend.services.planner_orchestrator",
}


def _collect_legacy_module_references(source: str, *, module_name: str) -> set[str]:
    module = ast.parse(source)
    references: set[str] = set()
    parent_module, _, leaf_name = module_name.rpartition(".")

    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom) and node.module == module_name:
            references.add(module_name)
        elif isinstance(node, ast.ImportFrom) and node.module == parent_module:
            if any(alias.name == leaf_name for alias in node.names):
                references.add(module_name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_name:
                    references.add(module_name)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value == module_name or node.value.startswith(f"{module_name}."):
                references.add(node.value)

    return references


def _assert_no_legacy_module_references(
    test_case: unittest.TestCase,
    source: str,
    *,
    module_name: str,
    context: str,
) -> None:
    references = _collect_legacy_module_references(source, module_name=module_name)
    test_case.assertEqual(
        sorted(references),
        [],
        f"{context}: {sorted(references)}",
    )


def _get_function_source(source: str, *, function_name: str) -> str:
    module = ast.parse(source)

    for node in ast.walk(module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return ast.get_source_segment(source, node) or ""

    raise AssertionError(f"Function {function_name} not found")


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
            "backend/compat/__init__.py",
            "backend/compat/agent_service.py",
            "backend/infrastructure/__init__.py",
            "backend/infrastructure/ai/__init__.py",
            "backend/infrastructure/config/__init__.py",
            "backend/infrastructure/media/__init__.py",
            "backend/infrastructure/media/asset_providers/types.py",
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

    def test_planning_graph_lives_in_app_planning_boundary(self) -> None:
        source_path = ROOT / "backend" / "app" / "planning" / "graph.py"
        self.assertTrue(source_path.is_file(), str(source_path))
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        expected_functions = {
            "build_planning_graph",
            "build_grounding_replan_graph",
            "build_user_revision_replan_graph",
            "build_execution_feedback_replan_graph",
            "run_initial_planning",
            "run_grounding_replan",
            "run_user_revision_replan",
            "run_execution_feedback_replan",
        }
        implemented = {
            node.name
            for node in module.body
            if isinstance(node, ast.FunctionDef)
        }
        self.assertTrue(
            expected_functions.issubset(implemented),
            "planner graph entrypoints must be implemented in backend.app.planning.graph",
        )

    def test_legacy_planner_graph_module_is_shim(self) -> None:
        source_path = ROOT / "backend" / "services" / "planner_graph.py"
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertIn(
            "from backend.app.planning.graph import",
            source,
        )
        self.assertFalse(
            any(isinstance(node, ast.FunctionDef) and node.name == "run_initial_planning" for node in module.body),
            "backend.services.planner_graph must remain a shim",
        )

    def test_planning_projection_lives_in_app_planning_boundary(self) -> None:
        source_path = ROOT / "backend" / "app" / "planning" / "projection.py"
        self.assertTrue(source_path.is_file(), str(source_path))
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertTrue(
            any(isinstance(node, ast.FunctionDef) and node.name == "execution_plan_to_edit_plan" for node in module.body),
            "execution_plan_to_edit_plan must be implemented in backend.app.planning.projection",
        )

    def test_grounding_service_lives_in_app_planning_boundary(self) -> None:
        source_path = ROOT / "backend" / "app" / "planning" / "grounding_service.py"
        self.assertTrue(source_path.is_file(), str(source_path))
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertTrue(
            any(isinstance(node, ast.ClassDef) and node.name == "GroundingService" for node in module.body),
            "GroundingService must be implemented in backend.app.planning.grounding_service",
        )
        self.assertNotIn("from backend.services.grounding_planner_models import", source)
        self.assertNotIn("from backend.services.grounding_planner_runtime import", source)

    def test_grounding_planner_modules_live_in_app_planning_boundary(self) -> None:
        expected_modules = {
            "grounding_planner_models.py": {"RetrievalQuery", "RetrievalQueryPack"},
            "grounding_planner_runtime.py": {"GroundingPlannerRuntime"},
        }

        for filename, expected_classes in expected_modules.items():
            source_path = ROOT / "backend" / "app" / "planning" / filename
            self.assertTrue(source_path.is_file(), str(source_path))
            source = source_path.read_text(encoding="utf-8")
            module = ast.parse(source)
            implemented = {
                node.name
                for node in module.body
                if isinstance(node, ast.ClassDef)
            }
            self.assertTrue(
                expected_classes.issubset(implemented),
                f"{source_path.stem} must be implemented in backend.app.planning",
            )
            self.assertNotIn("from backend.services.", source)

    def test_legacy_planner_projection_module_is_shim(self) -> None:
        source_path = ROOT / "backend" / "services" / "planner_projection.py"
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertIn(
            "from backend.app.planning.projection import execution_plan_to_edit_plan",
            source,
        )
        self.assertFalse(
            any(isinstance(node, ast.FunctionDef) and node.name == "execution_plan_to_edit_plan" for node in module.body),
            "backend.services.planner_projection must remain a shim",
        )

    def test_legacy_grounding_service_module_is_shim(self) -> None:
        source_path = ROOT / "backend" / "services" / "grounding_service.py"
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertIn(
            "from backend.app.planning.grounding_service import",
            source,
        )
        self.assertFalse(
            any(isinstance(node, ast.ClassDef) and node.name == "GroundingService" for node in module.body),
            "backend.services.grounding_service must remain a shim",
        )

    def test_legacy_grounding_planner_modules_are_shims(self) -> None:
        shim_modules = {
            "grounding_planner_models.py": (
                "from backend.app.planning.grounding_planner_models import",
                {"RetrievalQuery", "RetrievalQueryPack"},
            ),
            "grounding_planner_runtime.py": (
                "from backend.app.planning.grounding_planner_runtime import GroundingPlannerRuntime",
                {"GroundingPlannerRuntime"},
            ),
        }

        for filename, (expected_import, forbidden_classes) in shim_modules.items():
            source_path = ROOT / "backend" / "services" / filename
            source = source_path.read_text(encoding="utf-8")
            module = ast.parse(source)
            self.assertIn(expected_import, source)
            self.assertFalse(
                any(isinstance(node, ast.ClassDef) and node.name in forbidden_classes for node in module.body),
                f"backend.services.{source_path.stem} must remain a shim",
            )

    def test_planning_contracts_live_in_domain_boundary(self) -> None:
        source_path = ROOT / "backend" / "domain" / "planning" / "contracts.py"
        self.assertTrue(source_path.is_file(), str(source_path))
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        expected_classes = {
            "BriefUnderstanding",
            "AgentScene",
            "AgentPlan",
            "ExecutionScene",
            "ExecutionPlan",
            "InitialPlanningResult",
            "RevisionScenePatch",
            "RevisionPlanningResult",
            "AgentObservation",
            "GroundingFeedback",
            "CandidateConfirmationFeedback",
            "UserRevisionFeedback",
            "SearchExecutionFeedback",
            "RenderReadinessFeedback",
        }
        implemented = {
            node.name
            for node in module.body
            if isinstance(node, ast.ClassDef)
        }
        self.assertTrue(
            expected_classes.issubset(implemented),
            "planner contracts must be implemented in backend.domain.planning.contracts",
        )

    def test_legacy_planner_models_module_is_shim(self) -> None:
        source_path = ROOT / "backend" / "services" / "planner_models.py"
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertIn(
            "from backend.domain.planning.contracts import",
            source,
        )
        self.assertFalse(
            any(isinstance(node, ast.ClassDef) and node.name == "ExecutionPlan" for node in module.body),
            "backend.services.planner_models must remain a shim",
        )

    def test_runtime_config_service_lives_in_infrastructure_boundary(self) -> None:
        source_path = ROOT / "backend" / "infrastructure" / "config" / "runtime_config_service.py"
        self.assertTrue(source_path.is_file(), str(source_path))
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertTrue(
            any(isinstance(node, ast.ClassDef) and node.name == "RuntimeConfigService" for node in module.body),
            "RuntimeConfigService must be implemented in backend.infrastructure.config.runtime_config_service",
        )

    def test_gpt_service_lives_in_infrastructure_ai_boundary(self) -> None:
        source_path = ROOT / "backend" / "infrastructure" / "ai" / "gpt_service.py"
        self.assertTrue(source_path.is_file(), str(source_path))
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertTrue(
            any(isinstance(node, ast.ClassDef) and node.name == "GPTService" for node in module.body),
            "GPTService must be implemented in backend.infrastructure.ai.gpt_service",
        )
        self.assertNotIn("from backend.services.gpt_service import", source)

    def test_planner_runtime_factory_lives_in_app_planning_boundary(self) -> None:
        source_path = ROOT / "backend" / "app" / "planning" / "runtime_factory.py"
        self.assertTrue(source_path.is_file(), str(source_path))
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertTrue(
            any(isinstance(node, ast.FunctionDef) and node.name == "get_planner_runtime" for node in module.body),
            "get_planner_runtime must be implemented in backend.app.planning.runtime_factory",
        )
        self.assertNotIn("from backend.services.planner_runtime_deterministic import", source)
        self.assertNotIn("from backend.services.planner_runtime_langchain import", source)

    def test_planner_runtime_implementations_live_in_app_planning_boundary(self) -> None:
        expected_modules = {
            "runtime_deterministic.py": "DeterministicPlannerRuntime",
            "runtime_langchain.py": "LangChainPlannerRuntime",
            "runtime_openai.py": "OpenAIPlannerRuntime",
        }

        for filename, class_name in expected_modules.items():
            source_path = ROOT / "backend" / "app" / "planning" / filename
            self.assertTrue(source_path.is_file(), str(source_path))
            source = source_path.read_text(encoding="utf-8")
            module = ast.parse(source)
            self.assertTrue(
                any(isinstance(node, ast.ClassDef) and node.name == class_name for node in module.body),
                f"{class_name} must be implemented in backend.app.planning.{source_path.stem}",
            )
            self.assertNotIn("from backend.services.", source)

    def test_legacy_runtime_config_service_module_is_shim(self) -> None:
        source_path = ROOT / "backend" / "services" / "runtime_config_service.py"
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertIn(
            "from backend.infrastructure.config.runtime_config_service import",
            source,
        )
        self.assertFalse(
            any(isinstance(node, ast.ClassDef) and node.name == "RuntimeConfigService" for node in module.body),
            "backend.services.runtime_config_service must remain a shim",
        )

    def test_legacy_gpt_service_module_is_shim(self) -> None:
        source_path = ROOT / "backend" / "services" / "gpt_service.py"
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertIn(
            "from backend.infrastructure.ai.gpt_service import",
            source,
        )
        self.assertFalse(
            any(isinstance(node, ast.ClassDef) and node.name == "GPTService" for node in module.body),
            "backend.services.gpt_service must remain a shim",
        )

    def test_legacy_planner_runtime_module_is_shim(self) -> None:
        source_path = ROOT / "backend" / "services" / "planner_runtime.py"
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertIn(
            "from backend.app.planning.runtime_factory import get_planner_runtime",
            source,
        )
        self.assertFalse(
            any(isinstance(node, ast.FunctionDef) and node.name == "get_planner_runtime" for node in module.body),
            "backend.services.planner_runtime must remain a shim",
        )

    def test_legacy_planner_runtime_implementation_modules_are_shims(self) -> None:
        shim_modules = {
            "planner_runtime_deterministic.py": (
                "DeterministicPlannerRuntime",
                "from backend.app.planning.runtime_deterministic import DeterministicPlannerRuntime",
            ),
            "planner_runtime_langchain.py": (
                "LangChainPlannerRuntime",
                "backend.app.planning.runtime_langchain",
            ),
            "planner_runtime_openai.py": (
                "OpenAIPlannerRuntime",
                "from backend.app.planning.runtime_openai import OpenAIPlannerRuntime",
            ),
        }

        for filename, (class_name, expected_import) in shim_modules.items():
            source_path = ROOT / "backend" / "services" / filename
            source = source_path.read_text(encoding="utf-8")
            module = ast.parse(source)
            self.assertIn(expected_import, source)
            if filename == "planner_runtime_langchain.py":
                self.assertFalse(
                    any(isinstance(node, ast.FunctionDef) and node.name == "build_plan_from_brief" for node in module.body),
                    "backend.services.planner_runtime_langchain must not carry the full runtime implementation",
                )
            else:
                self.assertFalse(
                    any(isinstance(node, ast.ClassDef) and node.name == class_name for node in module.body),
                    f"backend.services.{source_path.stem} must remain a shim",
                )

    def test_planner_runtime_tests_import_langchain_runtime_from_app_boundary(self) -> None:
        source_path = ROOT / "tests" / "test_planner_runtime.py"
        source = source_path.read_text(encoding="utf-8")

        _assert_no_legacy_module_references(
            self,
            source,
            module_name="backend.services.planner_runtime_langchain",
            context="tests/test_planner_runtime.py still imports legacy langchain runtime alias",
        )

    def test_media_infrastructure_does_not_reexport_services_render_module(self) -> None:
        render_source = (ROOT / "backend" / "infrastructure" / "media" / "render_service.py").read_text(encoding="utf-8")

        self.assertNotIn("from backend.services.render_service import", render_source)

    def test_search_service_lives_in_infrastructure_media_boundary(self) -> None:
        source_path = ROOT / "backend" / "infrastructure" / "media" / "search_service.py"
        self.assertTrue(source_path.is_file(), str(source_path))
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        expected_functions = {
            "normalize_duration",
            "calculate_trim_window",
            "summarize_download_error",
            "search_and_download_all",
            "search_and_download_agent_clips",
        }
        implemented = {
            node.name
            for node in module.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertTrue(
            expected_functions.issubset(implemented),
            "search service entrypoints must be implemented in backend.infrastructure.media.search_service",
        )
        self.assertNotIn("from backend.services.search_service import", source)
        self.assertNotIn("import backend.services.search_service", source)

    def test_legacy_search_service_module_is_shim(self) -> None:
        source_path = ROOT / "backend" / "services" / "search_service.py"
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertIn(
            "from backend.infrastructure.media.search_service import",
            source,
        )
        self.assertFalse(
            any(isinstance(node, ast.AsyncFunctionDef) and node.name == "search_and_download_agent_clips" for node in module.body),
            "backend.services.search_service must remain a shim",
        )

    def test_legacy_search_service_patch_contract_is_explicit(self) -> None:
        namespace: dict[str, object] = {}
        exec((ROOT / "backend" / "services" / "search_service.py").read_text(encoding="utf-8"), namespace)

        self.assertEqual(
            set(namespace["_PATCHABLE_EXPORTS"]),
            {
                "download_video",
                "search_youtube_candidates",
                "search_pexels_candidates",
                "download_pexels_candidate",
                "get_asset_provider_order",
                "get_pexels_config",
            },
        )

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

    def test_app_agent_contains_real_stream_service_implementation(self) -> None:
        source_path = ROOT / "backend" / "app" / "agent" / "stream_service.py"
        self.assertTrue(source_path.is_file(), str(source_path))
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertTrue(
            any(isinstance(node, ast.ClassDef) and node.name == "AgentStreamService" for node in module.body),
            "AgentStreamService must be implemented in backend.app.agent.stream_service",
        )
        self.assertTrue(
            any(isinstance(node, ast.FunctionDef) and node.name == "format_sse_event" for node in module.body),
            "format_sse_event must be implemented in backend.app.agent.stream_service",
        )
        self.assertTrue(hasattr(importlib.import_module("backend.app.agent.stream_service"), "TraceBatch"))

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

    def test_agent_run_step_and_snapshot_services_live_in_app_agent_boundary(self) -> None:
        expected_classes = {
            "run_service.py": "AgentRunService",
            "step_service.py": "AgentStepService",
            "step_snapshot_service.py": "AgentStepSnapshotService",
        }

        for filename, class_name in expected_classes.items():
            source_path = ROOT / "backend" / "app" / "agent" / filename
            self.assertTrue(source_path.is_file(), str(source_path))
            module = ast.parse(source_path.read_text(encoding="utf-8"))
            self.assertTrue(
                any(isinstance(node, ast.ClassDef) and node.name == class_name for node in module.body),
                f"{class_name} must be implemented in backend.app.agent.{source_path.stem}",
            )

    def test_execution_entry_and_task_read_services_live_in_app_execution_boundary(self) -> None:
        expected_classes = {
            "diagnostic_service.py": "AgentDiagnosticService",
            "execution_service.py": "AgentExecutionService",
            "progress_service.py": "AgentProgressService",
            "task_read_service.py": "AgentTaskReadService",
        }

        for filename, class_name in expected_classes.items():
            source_path = ROOT / "backend" / "app" / "execution" / filename
            self.assertTrue(source_path.is_file(), str(source_path))
            module = ast.parse(source_path.read_text(encoding="utf-8"))
            self.assertTrue(
                any(isinstance(node, ast.ClassDef) and node.name == class_name for node in module.body),
                f"{class_name} must be implemented in backend.app.execution.{source_path.stem}",
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
            "agent_stream_service.py": (
                "AgentStreamService",
                "from backend.app.agent.stream_service import",
            ),
            "agent_run_service.py": (
                "AgentRunService",
                "from backend.app.agent.run_service import",
            ),
            "agent_step_service.py": (
                "AgentStepService",
                "from backend.app.agent.step_service import AgentStepService",
            ),
            "agent_step_snapshot_service.py": (
                "AgentStepSnapshotService",
                "from backend.app.agent.step_snapshot_service import",
            ),
            "agent_execution_service.py": (
                "AgentExecutionService",
                "from backend.app.execution.execution_service import AgentExecutionService",
            ),
            "agent_task_read_service.py": (
                "AgentTaskReadService",
                "from backend.app.execution.task_read_service import AgentTaskReadService",
            ),
            "agent_progress_service.py": (
                "AgentProgressService",
                "from backend.app.execution.progress_service import AgentProgressService",
            ),
            "agent_diagnostic_service.py": (
                "AgentDiagnosticService",
                "from backend.app.execution.diagnostic_service import AgentDiagnosticService",
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
        self.assertIn("from backend.app.execution.execution_service import AgentExecutionService", source)
        self.assertNotIn("from backend.app.execution.job_use_cases import AgentExecutionService", source)
        self.assertNotIn("from backend.services.agent_session_service import", source)
        self.assertNotIn("from backend.services.agent_execution_service import", source)

    def test_execution_workflow_service_does_not_import_legacy_progress_service(self) -> None:
        source = (ROOT / "backend" / "app" / "execution" / "workflow_service.py").read_text(encoding="utf-8")

        self.assertNotIn("from backend.services.agent_progress_service import", source)
        self.assertNotIn("import backend.services.agent_progress_service", source)

    def test_agent_and_execution_read_services_do_not_import_legacy_diagnostic_service(self) -> None:
        for relative_path in [
            "backend/app/agent/read_service.py",
            "backend/app/execution/task_read_service.py",
        ]:
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertNotIn(
                "backend.services.agent_diagnostic_service",
                source,
                f"{relative_path} should not import legacy diagnostic service",
            )

    def test_api_runtime_and_tasks_do_not_import_legacy_progress_service(self) -> None:
        for relative_path in [
            "backend/api/agent.py",
            "backend/runtime/agent_runtime.py",
            "backend/tasks/agent_tasks.py",
        ]:
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertNotIn(
                "backend.services.agent_progress_service",
                source,
                f"{relative_path} should not import legacy progress service",
            )

    def test_api_does_not_import_legacy_agent_service(self) -> None:
        source = (ROOT / "backend" / "api" / "agent.py").read_text(encoding="utf-8")

        self.assertNotIn("from backend.services.agent_service import", source)
        self.assertNotIn("import backend.services.agent_service", source)
        self.assertNotIn("agent_service.sync_session(", source)

    def test_compat_agent_service_contains_real_implementation(self) -> None:
        source_path = ROOT / "backend" / "compat" / "agent_service.py"
        self.assertTrue(source_path.is_file(), str(source_path))
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertTrue(
            any(isinstance(node, ast.ClassDef) and node.name == "AgentService" for node in module.body),
            "AgentService must be implemented in backend.compat.agent_service",
        )

    def test_legacy_agent_service_module_is_compat_shim(self) -> None:
        source_path = ROOT / "backend" / "services" / "agent_service.py"
        source = source_path.read_text(encoding="utf-8")
        module = ast.parse(source)

        self.assertIn(
            "from backend.compat.agent_service import AgentService",
            source,
        )
        self.assertFalse(
            any(isinstance(node, ast.ClassDef) and node.name == "AgentService" for node in module.body),
            "backend.services.agent_service must remain a shim",
        )

    def test_backend_test_suite_does_not_import_legacy_agent_service(self) -> None:
        source = (ROOT / "tests" / "test_agent_backend.py").read_text(encoding="utf-8")

        self.assertNotIn("from backend.services.agent_service import", source)

    def test_api_ai_does_not_import_legacy_search_service(self) -> None:
        source = (ROOT / "backend" / "api" / "ai.py").read_text(encoding="utf-8")

        self.assertNotIn("from backend.services.search_service import", source)
        self.assertNotIn("import backend.services.search_service", source)

    def test_api_ai_does_not_import_legacy_gpt_service(self) -> None:
        source = (ROOT / "backend" / "api" / "ai.py").read_text(encoding="utf-8")

        self.assertNotIn("from backend.services.gpt_service import", source)
        self.assertNotIn("import backend.services.gpt_service", source)

    def test_api_ai_does_not_import_legacy_render_service(self) -> None:
        source = (ROOT / "backend" / "api" / "ai.py").read_text(encoding="utf-8")

        self.assertNotIn("from backend.services.render_service import", source)
        self.assertNotIn("import backend.services.render_service", source)
        self.assertIn("from backend.infrastructure.media.render_service import render_video", source)

    def test_application_layer_does_not_import_migrated_service_modules(self) -> None:
        migrated_service_imports = {
            "backend.services.agent_session_service",
            "backend.services.agent_read_service",
            "backend.services.agent_execution_service",
            "backend.services.agent_task_read_service",
            "backend.services.planner_orchestrator",
            "backend.services.planner_graph",
            "backend.services.planner_models",
            "backend.services.planner_projection",
            "backend.services.planner_runtime",
            "backend.services.grounding_service",
            "backend.services.runtime_config_service",
            "backend.services.render_service",
            "backend.services.agent_diagnostic_service",
            "backend.services.agent_run_service",
            "backend.services.agent_step_service",
            "backend.services.agent_step_snapshot_service",
        }
        app_files = [
            path for path in (ROOT / "backend" / "app").rglob("*.py")
            if "__pycache__" not in path.parts
        ]

        for path in app_files:
            source = path.read_text(encoding="utf-8")
            for import_path in migrated_service_imports:
                self.assertNotIn(
                    f"from {import_path} import",
                    source,
                    f"{path} imports migrated service {import_path}",
                )
                self.assertNotIn(
                    f"import {import_path}",
                    source,
                    f"{path} imports migrated service {import_path}",
                )

    def test_task1_targeted_tests_only_keep_allowed_legacy_service_modules(self) -> None:
        target_files = [
            "tests/test_agent_persistence.py",
            "tests/test_agent_planner_phase1.py",
            "tests/test_agent_planner_phase2.py",
            "tests/test_agent_planner_phase3.py",
            "tests/test_agent_planner_phase4.py",
            "tests/test_agent_run_trace_model.py",
            "tests/test_rag_foundation.py",
            "tests/test_planner_models.py",
            "tests/test_mcp_foundation.py",
        ]
        allowed_legacy_modules = {
            "backend.services.planner_runtime_deterministic",
            "backend.services.asset_providers",
            "backend.services.asset_providers.config",
            "backend.services.asset_providers.metadata",
            "backend.services.asset_providers.pexels",
            "backend.services.asset_providers.types",
            "backend.services.asset_providers.youtube",
        }

        for relative_path in target_files:
            source_path = ROOT / relative_path
            source = source_path.read_text(encoding="utf-8")
            module = ast.parse(source)
            legacy_imports: set[str] = set()

            for node in ast.walk(module):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module == "backend.services" or node.module.startswith("backend.services."):
                        legacy_imports.add(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "backend.services" or alias.name.startswith("backend.services."):
                            legacy_imports.add(alias.name)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value == "backend.services" or node.value.startswith("backend.services."):
                        matched_module = next(
                            (
                                allowed_module
                                for allowed_module in sorted(allowed_legacy_modules, key=len, reverse=True)
                                if node.value == allowed_module or node.value.startswith(f"{allowed_module}.")
                            ),
                            None,
                        )
                        legacy_imports.add(matched_module or node.value)

            disallowed_imports = sorted(legacy_imports - allowed_legacy_modules)
            self.assertEqual(
                disallowed_imports,
                [],
                f"{relative_path} still imports retired service aliases: {disallowed_imports}",
            )

    def test_task2_runtime_tests_do_not_import_legacy_deterministic_runtime_aliases(self) -> None:
        target_files = [
            "tests/test_planner_runtime.py",
            "tests/test_planner_graph.py",
        ]
        forbidden_snippets = [
            "from backend.services.planner_runtime_deterministic import",
            "from backend.services.planner_runtime_openai import",
            "from backend.services.planner_runtime import",
            "import backend.services.planner_runtime as",
        ]

        for relative_path in target_files:
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            for snippet in forbidden_snippets:
                self.assertNotIn(
                    snippet,
                    source,
                    f"{relative_path} still imports deterministic runtime alias via {snippet}",
                )

    def test_task7_phase3_test_does_not_import_legacy_deterministic_runtime_alias(self) -> None:
        source = (ROOT / "tests" / "test_agent_planner_phase3.py").read_text(encoding="utf-8")
        self.assertNotIn(
            "from backend.services.planner_runtime_deterministic import",
            source,
        )

    def test_task8_backend_tests_do_not_import_legacy_gpt_or_stream_service_aliases(self) -> None:
        source = (ROOT / "tests" / "test_agent_backend.py").read_text(encoding="utf-8")

        self.assertNotIn(
            "from backend.services.gpt_service import",
            source,
        )
        self.assertNotIn(
            "from backend.services.agent_stream_service import",
            source,
        )

    def test_task2_backend_tests_do_not_import_legacy_asset_provider_config_aliases(self) -> None:
        source = (ROOT / "tests" / "test_agent_backend.py").read_text(encoding="utf-8")

        self.assertNotIn(
            "import backend.services.asset_providers.config as provider_config",
            source,
        )
        self.assertNotIn(
            "from backend.services.asset_providers.config import env_flag",
            source,
        )
        self.assertNotIn(
            "from backend.services.asset_providers.config import get_fixture_config",
            source,
        )

    def test_task1_backend_fixture_provider_tests_do_not_reference_legacy_fixture_shim(self) -> None:
        source = (ROOT / "tests" / "test_agent_backend.py").read_text(encoding="utf-8")
        targeted_tests = [
            "test_fixture_library_loads_default_videos_json",
            "test_fixture_search_returns_normalized_candidates",
            "test_fixture_search_returns_empty_list_when_no_match",
            "test_fixture_search_prefers_probed_media_duration_when_local_file_exists",
            "test_fixture_download_copies_asset_into_backend_downloads",
            "test_fixture_download_raises_clear_error_when_source_file_missing",
        ]

        for function_name in targeted_tests:
            function_source = _get_function_source(source, function_name=function_name)
            _assert_no_legacy_module_references(
                self,
                function_source,
                module_name="backend.services.asset_providers.fixture",
                context=f"tests/test_agent_backend.py::{function_name}",
            )

    def test_task6_fixture_provider_integration_test_does_not_reference_legacy_fixture_shim(self) -> None:
        source = (ROOT / "tests" / "test_agent_backend.py").read_text(encoding="utf-8")
        function_source = _get_function_source(
            source,
            function_name="test_agent_download_can_complete_with_fixture_provider",
        )

        _assert_no_legacy_module_references(
            self,
            function_source,
            module_name="backend.services.asset_providers.fixture",
            context="tests/test_agent_backend.py::test_agent_download_can_complete_with_fixture_provider",
        )

    def test_task8_backend_pexels_provider_tests_do_not_reference_legacy_pexels_shim(self) -> None:
        source = (ROOT / "tests" / "test_agent_backend.py").read_text(encoding="utf-8")
        targeted_tests = [
            "test_pexels_search_maps_api_response_to_candidates",
            "test_pexels_selects_vertical_mp4_with_bounded_resolution",
            "test_pexels_direct_download_writes_mp4",
        ]

        for function_name in targeted_tests:
            function_source = _get_function_source(source, function_name=function_name)
            _assert_no_legacy_module_references(
                self,
                function_source,
                module_name="backend.services.asset_providers.pexels",
                context=f"tests/test_agent_backend.py::{function_name}",
            )

    def test_task7_fixture_shim_is_removed_from_frozen_compat_surface(self) -> None:
        compat_doc = (ROOT / "docs" / "architecture" / "compat-surface.md").read_text(encoding="utf-8")

        self.assertNotIn("backend.services.asset_providers.fixture", FROZEN_COMPAT_MODULES)
        self.assertNotIn("`backend.services.asset_providers.fixture`", compat_doc)

    def test_task9_pexels_shim_is_removed_from_frozen_compat_surface(self) -> None:
        compat_doc = (ROOT / "docs" / "architecture" / "compat-surface.md").read_text(encoding="utf-8")

        self.assertNotIn("backend.services.asset_providers.pexels", FROZEN_COMPAT_MODULES)
        self.assertNotIn("`backend.services.asset_providers.pexels`", compat_doc)

    def test_non_architecture_tests_only_reference_frozen_legacy_modules(self) -> None:
        allowed_legacy_prefixes: set[str] = set()
        offenders: dict[str, list[str]] = {}

        for path in sorted((ROOT / "tests").glob("test_*.py")):
            if path.name == "test_agent_runtime_architecture.py":
                continue

            source = path.read_text(encoding="utf-8")
            module = ast.parse(source)
            legacy_references: set[str] = set()

            for node in ast.walk(module):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("backend.services"):
                    legacy_references.add(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("backend.services"):
                            legacy_references.add(alias.name)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("backend.services"):
                    legacy_references.add(node.value)

            unexpected = sorted(
                ref
                for ref in legacy_references
                if not any(ref == prefix or ref.startswith(f"{prefix}.") for prefix in allowed_legacy_prefixes)
            )
            if unexpected:
                offenders[path.relative_to(ROOT).as_posix()] = unexpected

        self.assertEqual(offenders, {})

    def test_task3_asset_provider_tests_only_keep_patch_heavy_legacy_modules(self) -> None:
        target_files = [
            "tests/test_agent_backend.py",
            "tests/test_agent_jobs.py",
            "tests/test_grounding_service.py",
        ]
        allowed_legacy_prefixes: set[str] = set()

        for relative_path in target_files:
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            module = ast.parse(source)
            legacy_references: set[str] = set()

            for node in ast.walk(module):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("backend.services.asset_providers"):
                        legacy_references.add(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("backend.services.asset_providers"):
                            legacy_references.add(alias.name)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value.startswith("backend.services.asset_providers"):
                        matched_prefix = next(
                            (
                                allowed_prefix
                                for allowed_prefix in sorted(allowed_legacy_prefixes, key=len, reverse=True)
                                if node.value == allowed_prefix or node.value.startswith(f"{allowed_prefix}.")
                            ),
                            None,
                        )
                        legacy_references.add(matched_prefix or node.value)

            disallowed_references = sorted(legacy_references - allowed_legacy_prefixes)
            self.assertEqual(
                disallowed_references,
                [],
                f"{relative_path} still uses simple asset-provider compat modules: {disallowed_references}",
            )

    def test_frozen_compat_surface_is_documented(self) -> None:
        doc_path = ROOT / "docs" / "architecture" / "compat-surface.md"
        self.assertTrue(doc_path.is_file(), str(doc_path))

        doc = doc_path.read_text(encoding="utf-8")
        self.assertIn("# Compat Surface", doc)
        self.assertEqual(FROZEN_COMPAT_MODULES, set())
        self.assertIn("frozen compat surface", doc)
        self.assertIn("已收缩为 0", doc)
        for module_name in sorted(FROZEN_COMPAT_MODULES):
            self.assertIn(module_name, doc)

    def test_runtime_boundaries_are_documented_without_legacy_service_boundary(self) -> None:
        doc_path = ROOT / "docs" / "architecture" / "runtime-boundaries.md"
        self.assertTrue(doc_path.is_file(), str(doc_path))

        doc = doc_path.read_text(encoding="utf-8")
        self.assertIn("# Runtime Boundaries", doc)
        self.assertIn("backend/app", doc)
        self.assertIn("backend/runtime", doc)
        self.assertIn("backend/domain", doc)
        self.assertIn("backend/infrastructure", doc)
        self.assertIn("backend/compat", doc)
        self.assertIn("RAG", doc)
        self.assertIn("Skill", doc)
        self.assertIn("MCP", doc)
        self.assertNotIn("backend.services.", doc)

    def test_task6_targeted_tests_do_not_use_retired_low_risk_service_modules(self) -> None:
        target_files = [
            "tests/test_agent_backend.py",
            "tests/test_agent_jobs.py",
            "tests/test_grounding_service.py",
            "tests/test_grounding_planner_runtime.py",
            "tests/test_planner_runtime.py",
        ]

        for relative_path in target_files:
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            module = ast.parse(source)
            legacy_references: set[str] = set()

            for node in ast.walk(module):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module in TASK6_RETIRED_TEST_SERVICE_MODULES:
                        legacy_references.add(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in TASK6_RETIRED_TEST_SERVICE_MODULES:
                            legacy_references.add(alias.name)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value in TASK6_RETIRED_TEST_SERVICE_MODULES:
                        legacy_references.add(node.value)

            self.assertEqual(
                sorted(legacy_references),
                [],
                f"{relative_path} still uses retired low-risk test service modules: {sorted(legacy_references)}",
            )

    def test_task1_guard_detects_legacy_search_service_module_alias_imports(self) -> None:
        references = _collect_legacy_module_references(
            "import backend.services.search_service as search_service\n",
            module_name="backend.services.search_service",
        )

        self.assertEqual(references, {"backend.services.search_service"})

    def test_task1_guard_detects_legacy_search_service_from_imports(self) -> None:
        references = _collect_legacy_module_references(
            "from backend.services import search_service\n",
            module_name="backend.services.search_service",
        )

        self.assertEqual(references, {"backend.services.search_service"})

    def test_task1_guard_flags_legacy_langchain_runtime_module_alias_imports(self) -> None:
        with self.assertRaises(AssertionError):
            _assert_no_legacy_module_references(
                self,
                "import backend.services.planner_runtime_langchain as legacy\n",
                module_name="backend.services.planner_runtime_langchain",
                context="synthetic planner runtime source still imports legacy langchain runtime alias",
            )

    def test_task1_agent_jobs_test_does_not_use_legacy_search_service_contracts(self) -> None:
        source = (ROOT / "tests" / "test_agent_jobs.py").read_text(encoding="utf-8")
        references = _collect_legacy_module_references(
            source,
            module_name="backend.services.search_service",
        )

        self.assertEqual(
            sorted(references),
            [],
            f"tests/test_agent_jobs.py still uses legacy search service contracts: {sorted(references)}",
        )

    def test_task4_backend_test_does_not_use_legacy_search_service_contracts(self) -> None:
        source = (ROOT / "tests" / "test_agent_backend.py").read_text(encoding="utf-8")
        references = _collect_legacy_module_references(
            source,
            module_name="backend.services.search_service",
        )

        self.assertEqual(
            sorted(references),
            [],
            f"tests/test_agent_backend.py still uses legacy search service contracts: {sorted(references)}",
        )

    def test_infrastructure_layer_does_not_import_migrated_service_modules(self) -> None:
        infrastructure_files = [
            path for path in (ROOT / "backend" / "infrastructure").rglob("*.py")
            if "__pycache__" not in path.parts
        ]
        forbidden = {
            "backend.services.render_service",
            "backend.services.agent_session_service",
            "backend.services.agent_read_service",
            "backend.services.planner_orchestrator",
        }

        for path in infrastructure_files:
            source = path.read_text(encoding="utf-8")
            for import_path in forbidden:
                self.assertNotIn(import_path, source, f"{path} imports migrated service {import_path}")

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

    def test_asset_provider_implementations_live_in_infrastructure_media_boundary(self) -> None:
        expected_modules = {
            "types.py": {"ProviderDiagnostic", "AssetCandidate", "AssetDownload", "ProviderResult"},
            "config.py": {"YoutubeProviderConfig", "PexelsProviderConfig", "FixtureProviderConfig"},
        }

        for filename, expected_classes in expected_modules.items():
            source_path = ROOT / "backend" / "infrastructure" / "media" / "asset_providers" / filename
            self.assertTrue(source_path.is_file(), str(source_path))
            source = source_path.read_text(encoding="utf-8")
            module = ast.parse(source)
            implemented = {
                node.name
                for node in module.body
                if isinstance(node, ast.ClassDef)
            }
            self.assertTrue(
                expected_classes.issubset(implemented),
                f"{source_path.stem} must be implemented in backend.infrastructure.media.asset_providers",
            )
            self.assertNotIn("from backend.services.asset_providers", source)

        expected_functions = {
            "fixture.py": {
                "load_fixture_library",
                "search_fixture_candidates",
                "download_fixture_candidate",
                "probe_fixture_duration",
            },
            "metadata.py": {
                "remember_clip_metadata",
                "pop_clip_metadata",
            },
            "pexels.py": {
                "search_pexels_candidates",
                "select_pexels_video_file",
                "download_pexels_candidate",
            },
            "youtube.py": {
                "build_youtube_search_options",
                "build_youtube_download_options",
                "search_youtube_candidates",
            },
        }

        for filename, required_functions in expected_functions.items():
            source_path = ROOT / "backend" / "infrastructure" / "media" / "asset_providers" / filename
            self.assertTrue(source_path.is_file(), str(source_path))
            source = source_path.read_text(encoding="utf-8")
            module = ast.parse(source)
            implemented = {
                node.name
                for node in module.body
                if isinstance(node, ast.FunctionDef)
            }
            self.assertTrue(
                required_functions.issubset(implemented),
                f"{source_path.stem} must be implemented in backend.infrastructure.media.asset_providers",
            )
            self.assertNotIn("from backend.services.asset_providers", source)

    def test_legacy_asset_provider_service_modules_are_shims(self) -> None:
        shim_expectations = {
            "config.py": {
                "required": "backend.infrastructure.media.asset_providers.config",
                "forbidden": ["from dataclasses import dataclass"],
            },
            "fixture.py": {
                "required": "backend.infrastructure.media.asset_providers.fixture",
                "forbidden": ["import ffmpeg", "import shutil"],
            },
            "metadata.py": {
                "required": "backend.infrastructure.media.asset_providers.metadata",
                "forbidden": ["_CLIP_METADATA_BY_LOCAL_PATH"],
            },
            "pexels.py": {
                "required": "backend.infrastructure.media.asset_providers.pexels",
                "forbidden": ["import urllib.request", "import urllib.error"],
            },
            "types.py": {
                "required": "backend.infrastructure.media.asset_providers.types",
                "forbidden": ["@dataclass"],
            },
            "youtube.py": {
                "required": "backend.infrastructure.media.asset_providers.youtube",
                "forbidden": ["import yt_dlp"],
            },
        }

        for filename, expectation in shim_expectations.items():
            source_path = ROOT / "backend" / "services" / "asset_providers" / filename
            source = source_path.read_text(encoding="utf-8")
            self.assertIn(expectation["required"], source)
            for forbidden_snippet in expectation["forbidden"]:
                self.assertNotIn(forbidden_snippet, source, f"{source_path} must remain a shim")

    def test_legacy_asset_provider_config_shim_depends_on_infrastructure_runtime_config(self) -> None:
        source_path = ROOT / "backend" / "services" / "asset_providers" / "config.py"
        source = source_path.read_text(encoding="utf-8")

        self.assertIn(
            "from backend.infrastructure.config.runtime_config_service import",
            source,
        )
        self.assertNotIn(
            "from backend.services.runtime_config_service import",
            source,
        )

    def test_primary_layers_do_not_import_legacy_asset_provider_modules(self) -> None:
        search_source = (ROOT / "backend" / "infrastructure" / "media" / "search_service.py").read_text(encoding="utf-8")
        grounding_source = (ROOT / "backend" / "app" / "planning" / "grounding_service.py").read_text(encoding="utf-8")

        forbidden_imports = [
            "backend.services.asset_providers.config",
            "backend.services.asset_providers.fixture",
            "backend.services.asset_providers.metadata",
            "backend.services.asset_providers.pexels",
            "backend.services.asset_providers.types",
            "backend.services.asset_providers.youtube",
        ]

        for import_path in forbidden_imports:
            self.assertNotIn(import_path, search_source)
            self.assertNotIn(import_path, grounding_source)

        self.assertIn("backend.infrastructure.media.asset_providers.config", search_source)
        self.assertIn("backend.infrastructure.media.asset_providers.fixture", search_source)
        self.assertIn("backend.infrastructure.media.asset_providers.metadata", search_source)
        self.assertIn("backend.infrastructure.media.asset_providers.pexels", search_source)
        self.assertIn("backend.infrastructure.media.asset_providers.types", search_source)
        self.assertIn("backend.infrastructure.media.asset_providers.youtube", search_source)
        self.assertIn("backend.infrastructure.media.asset_providers.config", grounding_source)
        self.assertIn("backend.infrastructure.media.asset_providers.fixture", grounding_source)
        self.assertIn("backend.infrastructure.media.asset_providers.pexels", grounding_source)
        self.assertIn("backend.infrastructure.media.asset_providers.youtube", grounding_source)

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
            "from backend.app.execution.execution_service import AgentExecutionService",
            source,
        )
        self.assertIn(
            "from backend.app.execution.task_read_service import AgentTaskReadService",
            source,
        )
        self.assertIn(
            "from backend.app.agent.run_service import ActiveOperationConflict",
            source,
        )
        self.assertIn(
            "from backend.app.agent.stream_service import AgentStreamService, format_sse_event",
            source,
        )
        self.assertNotIn("from backend.app.execution.job_use_cases import AgentExecutionService", source)
        self.assertNotIn("from backend.services.agent_execution_service import", source)
        self.assertNotIn("from backend.services.agent_task_read_service import", source)
        self.assertNotIn("from backend.services.agent_run_service import", source)
        self.assertNotIn("from backend.services.agent_session_service import", source)
        self.assertNotIn("from backend.services.agent_stream_service import", source)

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

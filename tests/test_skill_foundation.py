from __future__ import annotations

import unittest


class SkillFoundationDomainTests(unittest.TestCase):
    def test_skill_definition_contract_is_stable(self) -> None:
        from backend.domain.skills.contracts import SkillDefinition

        definition = SkillDefinition(
            id="builtin.product_intro_video",
            version="0.1.0",
            name="Product Intro Video",
            description="Default planning skill for product intro videos.",
            trigger_conditions={"runTypes": ["initial_planning"]},
            prompts={"planner": "planner.md"},
            handler="backend.skills.builtin.product_intro_video.handlers:build_product_intro_planner_request",
            status="active",
        )

        self.assertEqual(definition.id, "builtin.product_intro_video")
        self.assertEqual(definition.version, "0.1.0")
        self.assertEqual(definition.name, "Product Intro Video")
        self.assertEqual(definition.description, "Default planning skill for product intro videos.")
        self.assertEqual(definition.trigger_conditions, {"runTypes": ["initial_planning"]})
        self.assertEqual(definition.input_schema, {})
        self.assertEqual(definition.output_schema, {})
        self.assertEqual(definition.required_context, [])
        self.assertEqual(definition.required_tools, [])
        self.assertEqual(definition.default_role, "planner")
        self.assertEqual(definition.supported_roles, ["planner"])
        self.assertEqual(definition.prompts["planner"], "planner.md")
        self.assertEqual(
            definition.handler,
            "backend.skills.builtin.product_intro_video.handlers:build_product_intro_planner_request",
        )
        self.assertEqual(definition.status, "active")

    def test_planner_request_contract_keeps_strategy_fields(self) -> None:
        from backend.domain.skills.contracts import PlannerRequest

        request = PlannerRequest(
            action="initial_planning",
            system_prompt="You are a shortform planning assistant.",
            messages=[{"role": "user", "content": "做一个产品介绍视频"}],
            context_items=[{"type": "knowledge", "summary": "开头 3 秒需要明确产品和场景"}],
            output_schema={"type": "agent_plan"},
            constraints={"maxScenes": 6},
            retry_strategy_hint="none",
            failed_scene_ids=[],
        )

        self.assertEqual(request.action, "initial_planning")
        self.assertEqual(request.system_prompt, "You are a shortform planning assistant.")
        self.assertEqual(request.messages, [{"role": "user", "content": "做一个产品介绍视频"}])
        self.assertEqual(
            request.context_items,
            [{"type": "knowledge", "summary": "开头 3 秒需要明确产品和场景"}],
        )
        self.assertEqual(request.output_schema, {"type": "agent_plan"})
        self.assertEqual(request.constraints["maxScenes"], 6)
        self.assertEqual(request.failure_context, {})
        self.assertEqual(request.retry_strategy_hint, "none")
        self.assertEqual(request.failed_scene_ids, [])

    def test_skill_selection_contract_defaults_are_explicit(self) -> None:
        from backend.domain.skills.contracts import SkillSelection, SkillSelectionRequest

        selection_request = SkillSelectionRequest(
            session_id="session-123",
            run_id="run-456",
            run_type="initial_planning",
            user_message="做一个产品介绍视频",
        )
        selection = SkillSelection(
            skill_id="builtin.product_intro_video",
            version="0.1.0",
            reason="default skill for initial planning",
        )

        self.assertEqual(selection_request.context, {})
        self.assertEqual(selection_request.failure_context, {})
        self.assertEqual(selection.skill_id, "builtin.product_intro_video")
        self.assertEqual(selection.version, "0.1.0")
        self.assertEqual(selection.reason, "default skill for initial planning")


class BuiltinSkillRegistryTests(unittest.TestCase):
    def test_builtin_registry_lists_two_supported_definitions(self) -> None:
        from backend.app.skills.registry import BuiltinSkillRegistry

        registry = BuiltinSkillRegistry()

        definitions = registry.list_definitions()

        self.assertEqual(
            [definition.id for definition in definitions],
            [
                "builtin.product_intro_video",
                "builtin.execution_feedback_replan",
            ],
        )
        self.assertEqual(
            {definition.id: definition.version for definition in definitions},
            {
                "builtin.execution_feedback_replan": "0.1.0",
                "builtin.product_intro_video": "0.1.0",
            },
        )

    def test_builtin_registry_reads_python_definition_modules(self) -> None:
        from backend.app.skills.registry import BuiltinSkillRegistry

        registry = BuiltinSkillRegistry()

        definition = registry.get_definition("builtin.product_intro_video")

        self.assertEqual(definition.name, "Product Intro Video")
        self.assertEqual(
            definition.prompts,
            {
                "planner": "planner.md",
                "revision": "revision.md",
                "grounding_replan": "grounding_replan.md",
            },
        )
        self.assertEqual(
            definition.handler,
            "backend.skills.builtin.product_intro_video.handlers:build_product_intro_planner_request",
        )


class SkillSelectionServiceTests(unittest.TestCase):
    def test_selection_service_routes_initial_and_revision_runs_to_product_intro_skill(self) -> None:
        from backend.app.skills.registry import BuiltinSkillRegistry
        from backend.app.skills.selection_service import SkillSelectionService
        from backend.domain.skills.contracts import SkillSelectionRequest

        service = SkillSelectionService(registry=BuiltinSkillRegistry())

        initial_selection = service.select_skill(
            SkillSelectionRequest(
                session_id="session-1",
                run_id="run-1",
                run_type="initial_planning",
                user_message="做一个产品介绍视频",
            )
        )
        revision_selection = service.select_skill(
            SkillSelectionRequest(
                session_id="session-1",
                run_id="run-2",
                run_type="user_revision",
                user_message="把节奏调快一点",
            )
        )
        grounding_selection = service.select_skill(
            SkillSelectionRequest(
                session_id="session-1",
                run_id="run-3",
                run_type="grounding_replan",
                user_message="确认这些候选素材",
            )
        )

        self.assertEqual(initial_selection.skill_id, "builtin.product_intro_video")
        self.assertEqual(revision_selection.skill_id, "builtin.product_intro_video")
        self.assertEqual(grounding_selection.skill_id, "builtin.product_intro_video")

    def test_selection_service_routes_execution_feedback_to_repair_skill(self) -> None:
        from backend.app.skills.registry import BuiltinSkillRegistry
        from backend.app.skills.selection_service import SkillSelectionService
        from backend.domain.skills.contracts import SkillSelectionRequest

        service = SkillSelectionService(registry=BuiltinSkillRegistry())

        selection = service.select_skill(
            SkillSelectionRequest(
                session_id="session-1",
                run_id="run-4",
                run_type="execution_feedback_replan",
                user_message="上一轮搜索失败了，帮我重规划",
            )
        )

        self.assertEqual(selection.skill_id, "builtin.execution_feedback_replan")
        self.assertEqual(selection.version, "0.1.0")
        self.assertIn("execution_feedback_replan", selection.reason)

    def test_selection_service_rejects_unknown_run_type(self) -> None:
        from backend.app.skills.registry import BuiltinSkillRegistry
        from backend.app.skills.selection_service import SkillSelectionService
        from backend.domain.skills.contracts import SkillSelectionRequest

        service = SkillSelectionService(registry=BuiltinSkillRegistry())

        with self.assertRaisesRegex(LookupError, "unknown_run_type"):
            service.select_skill(
                SkillSelectionRequest(
                    session_id="session-1",
                    run_id="run-5",
                    run_type="unknown_run_type",
                    user_message="test",
                )
            )


class BuiltinSkillHandlerTests(unittest.TestCase):
    def test_product_intro_handler_builds_planner_request_for_initial_planning(self) -> None:
        from backend.domain.skills.contracts import PlannerRequest, SkillSelectionRequest
        from backend.skills.builtin.product_intro_video.handlers import (
            build_product_intro_planner_request,
        )

        planner_request = build_product_intro_planner_request(
            SkillSelectionRequest(
                session_id="session-1",
                run_id="run-1",
                run_type="initial_planning",
                user_message="做一个 30 秒产品介绍视频",
                context={"briefSummary": "强调产品价值和使用场景"},
            )
        )

        self.assertIsInstance(planner_request, PlannerRequest)
        self.assertEqual(planner_request.action, "initial_planning")
        self.assertIn("product intro", planner_request.system_prompt.lower())
        self.assertEqual(
            planner_request.messages,
            [{"role": "user", "content": "做一个 30 秒产品介绍视频"}],
        )
        self.assertEqual(
            planner_request.context_items,
            [{"type": "briefSummary", "value": "强调产品价值和使用场景"}],
        )
        self.assertEqual(planner_request.retry_strategy_hint, "none")

    def test_product_intro_handler_switches_prompt_by_run_type(self) -> None:
        from backend.domain.skills.contracts import SkillSelectionRequest
        from backend.skills.builtin.product_intro_video.handlers import (
            build_product_intro_planner_request,
        )

        planner_request = build_product_intro_planner_request(
            SkillSelectionRequest(
                session_id="session-1",
                run_id="run-2",
                run_type="user_revision",
                user_message="这些候选素材可以，把节奏调快一点",
            )
        )

        self.assertEqual(planner_request.action, "user_revision")
        self.assertIn("revising", planner_request.system_prompt.lower())

    def test_execution_feedback_handler_builds_repair_request(self) -> None:
        from backend.domain.skills.contracts import PlannerRequest, SkillSelectionRequest
        from backend.skills.builtin.execution_feedback_replan.handlers import (
            build_execution_feedback_replan_request,
        )

        planner_request = build_execution_feedback_replan_request(
            SkillSelectionRequest(
                session_id="session-1",
                run_id="run-3",
                run_type="execution_feedback_replan",
                user_message="搜索结果不够，帮我修一下",
                failure_context={"failedSceneIds": [2, 4], "reason": "asset_shortage"},
            )
        )

        self.assertIsInstance(planner_request, PlannerRequest)
        self.assertEqual(planner_request.action, "execution_feedback_replan")
        self.assertIn("repair", planner_request.system_prompt.lower())
        self.assertEqual(planner_request.failure_context["reason"], "asset_shortage")
        self.assertEqual(planner_request.failed_scene_ids, [2, 4])
        self.assertEqual(planner_request.retry_strategy_hint, "targeted_replan")


class PlannerOrchestratorObservabilityTests(unittest.TestCase):
    def test_skill_request_and_summary_shapes_support_minimal_observability(self) -> None:
        from dataclasses import asdict

        from backend.domain.skills.contracts import PlannerRequest, SkillSelectionRequest

        selection_request = SkillSelectionRequest(
            session_id="session-1",
            run_id="run-1",
            run_type="initial_planning",
            user_message="做一个产品介绍视频",
            context={"briefSummary": "强调价值"},
            failure_context={"reason": "none"},
        )
        planner_request = PlannerRequest(
            action="initial_planning",
            system_prompt="prompt",
            messages=[{"role": "user", "content": "做一个产品介绍视频"}],
            context_items=[{"type": "briefSummary", "value": "强调价值"}],
            output_schema={"type": "agent_plan"},
            constraints={"maxScenes": 6},
            failure_context={"reason": "none"},
            retry_strategy_hint="none",
        )

        selection_payload = asdict(selection_request)
        planner_payload = {
            "action": planner_request.action,
            "messageCount": len(planner_request.messages),
            "contextItemTypes": [item["type"] for item in planner_request.context_items],
            "constraintKeys": sorted(planner_request.constraints.keys()),
            "failureContextKeys": sorted(planner_request.failure_context.keys()),
        }

        self.assertEqual(selection_payload["run_type"], "initial_planning")
        self.assertEqual(selection_payload["context"]["briefSummary"], "强调价值")
        self.assertEqual(planner_payload["action"], "initial_planning")
        self.assertEqual(planner_payload["messageCount"], 1)
        self.assertEqual(planner_payload["contextItemTypes"], ["briefSummary"])
        self.assertEqual(planner_payload["constraintKeys"], ["maxScenes"])
        self.assertEqual(planner_payload["failureContextKeys"], ["reason"])

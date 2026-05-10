import importlib
import sys
import unittest
from unittest.mock import Mock, patch

from backend.services.planner_models import InitialPlanningResult


class _FakeStructuredPlanner:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error

    def invoke(self, _messages):
        if self.error is not None:
            raise self.error
        return self.result


class _FakeChatModel:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.schema = None

    def with_structured_output(self, schema):
        self.schema = schema
        return _FakeStructuredPlanner(result=self.result, error=self.error)


class PlannerRuntimeTests(unittest.TestCase):
    def test_langchain_runtime_builds_initial_plan_from_structured_output(self):
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        fake_llm = _FakeChatModel(
            result=InitialPlanningResult(
                agentPlan={
                    "title": " Notion AI 产品介绍 ",
                    "goal": " 给 Notion AI 做一个视频 ",
                    "summary": " 适合销售演示的开场视频 ",
                    "scenes": [
                        {
                            "id": 1,
                            "purpose": "建立产品认知",
                            "description": "展示 Notion AI 界面",
                            "keywords": [" product ", " interface "],
                            "duration": 6,
                        }
                    ],
                },
                executionPlan={
                    "title": " Notion AI 产品介绍 ",
                    "targetDuration": 12,
                    "style": " 干净商务 ",
                    "scenes": [
                        {
                            "id": 1,
                            "description": "展示 Notion AI 界面",
                            "keywords": ["product", "interface"],
                            "searchQuery": "  product   interface  ",
                            "duration": 6,
                        }
                    ],
                },
            )
        )

        runtime = LangChainPlannerRuntime(model_name="gpt-4o-mini", llm=fake_llm)
        agent_plan, execution_plan = runtime.build_plan_from_brief("给 Notion AI 做一个视频")

        self.assertEqual(agent_plan.title, "Notion AI 产品介绍")
        self.assertEqual(execution_plan.scenes[0].searchQuery, "product interface")

    def test_langchain_runtime_rejects_mismatched_scene_ids(self):
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        fake_llm = _FakeChatModel(
            result=InitialPlanningResult(
                agentPlan={
                    "title": "Notion AI 产品介绍",
                    "goal": "给 Notion AI 做一个视频",
                    "summary": "适合销售演示的开场视频",
                    "scenes": [
                        {
                            "id": 1,
                            "purpose": "建立产品认知",
                            "description": "展示 Notion AI 界面",
                            "keywords": ["product", "interface"],
                            "duration": 6,
                        }
                    ],
                },
                executionPlan={
                    "title": "Notion AI 产品介绍",
                    "targetDuration": 12,
                    "style": "干净商务",
                    "scenes": [
                        {
                            "id": 2,
                            "description": "展示 Notion AI 界面",
                            "keywords": ["product", "interface"],
                            "searchQuery": "product interface",
                            "duration": 6,
                        }
                    ],
                },
            )
        )

        runtime = LangChainPlannerRuntime(model_name="gpt-4o-mini", llm=fake_llm)

        with self.assertRaisesRegex(ValueError, "scene ids"):
            runtime.build_plan_from_brief("给 Notion AI 做一个视频")

    def test_langchain_runtime_rejects_non_positive_agent_scene_duration(self):
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        fake_llm = _FakeChatModel(
            result=InitialPlanningResult(
                agentPlan={
                    "title": "Notion AI 产品介绍",
                    "goal": "给 Notion AI 做一个视频",
                    "summary": "适合销售演示的开场视频",
                    "scenes": [
                        {
                            "id": 1,
                            "purpose": "建立产品认知",
                            "description": "展示 Notion AI 界面",
                            "keywords": ["product", "interface"],
                            "duration": 0,
                        }
                    ],
                },
                executionPlan={
                    "title": "Notion AI 产品介绍",
                    "targetDuration": 12,
                    "style": "干净商务",
                    "scenes": [
                        {
                            "id": 1,
                            "description": "展示 Notion AI 界面",
                            "keywords": ["product", "interface"],
                            "searchQuery": "product interface",
                            "duration": 6,
                        }
                    ],
                },
            )
        )

        runtime = LangChainPlannerRuntime(model_name="gpt-4o-mini", llm=fake_llm)

        with self.assertRaisesRegex(ValueError, "duration"):
            runtime.build_plan_from_brief("给 Notion AI 做一个视频")

    def test_langchain_runtime_bubbles_up_model_failures(self):
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=_FakeChatModel(error=RuntimeError("LangChain planning failed")),
        )

        with self.assertRaisesRegex(RuntimeError, "LangChain planning failed"):
            runtime.build_plan_from_brief("给 Notion AI 做一个视频")

    def test_langchain_runtime_delegates_grounding_replan_to_deterministic_runtime(self):
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        deterministic_delegate = Mock()
        deterministic_delegate.replan_after_grounding.return_value = (
            "agent",
            "execution",
            "summary",
        )

        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=_FakeChatModel(result=None),
            deterministic_delegate=deterministic_delegate,
        )

        result = runtime.replan_after_grounding(
            current_agent=Mock(),
            current_execution=Mock(),
            grounding_feedback=Mock(),
            confirmation_feedback=Mock(),
        )

        self.assertEqual(result, ("agent", "execution", "summary"))
        deterministic_delegate.replan_after_grounding.assert_called_once()

    def test_langchain_runtime_replans_after_user_revision_with_patch_merge(self):
        from backend.services.planner_models import RevisionPlanningResult, UserRevisionFeedback
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )
        fake_llm = _FakeChatModel(
            result=RevisionPlanningResult(
                summary="更偏商务演示与销售沟通的版本",
                audience="销售团队",
                styleHint="商务演示风格",
                style="商务演示风格",
                changeSummary="已根据最新修改意见完成计划重写",
                scenePatches=[
                    {
                        "id": 1,
                        "description": "城市与车流开场，建立商务节奏",
                        "keywords": ["office", "lobby", "team"],
                        "searchQuery": "office lobby team",
                    }
                ],
            )
        )

        runtime = LangChainPlannerRuntime(model_name="gpt-4o-mini", llm=fake_llm)
        next_agent, next_execution, change_summary = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="整体再商务一点，目标受众改成销售团队",
                sceneKeywordUpdates={},
            ),
        )

        self.assertEqual(change_summary, "已根据最新修改意见完成计划重写")
        self.assertEqual(next_agent.summary, "更偏商务演示与销售沟通的版本")
        self.assertEqual(next_agent.understanding.audience, "销售团队")
        self.assertEqual(next_agent.understanding.styleHint, "商务演示风格")
        self.assertEqual(next_execution.style, "商务演示风格")
        self.assertEqual(next_agent.scenes[0].description, "城市与车流开场，建立商务节奏")
        self.assertEqual(next_execution.scenes[0].searchQuery, "office lobby team")
        self.assertEqual(next_execution.scenes[1].searchQuery, current_execution.scenes[1].searchQuery)
        self.assertEqual(next_execution.scenes[0].duration, current_execution.scenes[0].duration)
        self.assertEqual(next_execution.targetDuration, current_execution.targetDuration)
        self.assertEqual(next_agent.replanHistory[-1]["triggerType"], "user_revision")
        self.assertEqual(next_agent.replanHistory[-1]["summary"], "已根据最新修改意见完成计划重写")
        self.assertEqual(next_agent.replanHistory[-1]["runtime"], "langchain")

    def test_langchain_runtime_preserves_explicit_scene_keyword_updates_over_model_patch(self):
        from backend.services.planner_models import RevisionPlanningResult, UserRevisionFeedback
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )
        fake_llm = _FakeChatModel(
            result=RevisionPlanningResult(
                summary="更偏商务演示与销售沟通的版本",
                audience="销售团队",
                styleHint="商务演示风格",
                style="商务演示风格",
                changeSummary="已根据最新修改意见完成计划重写",
                scenePatches=[
                    {
                        "id": 1,
                        "description": "城市与车流开场，建立商务节奏",
                        "keywords": ["office", "lobby", "team"],
                        "searchQuery": "office lobby team",
                    }
                ],
            )
        )

        runtime = LangChainPlannerRuntime(model_name="gpt-4o-mini", llm=fake_llm)
        next_agent, next_execution, _change_summary = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="整体再商务一点，目标受众改成销售团队，场景1：城市 车流 黄昏",
                sceneKeywordUpdates={1: ["城市", "车流", "黄昏"]},
            ),
        )

        self.assertEqual(next_agent.scenes[0].keywords, ["城市", "车流", "黄昏"])
        self.assertEqual(next_execution.scenes[0].keywords, ["城市", "车流", "黄昏"])
        self.assertEqual(next_execution.scenes[0].searchQuery, "城市 车流 黄昏")
        self.assertEqual(next_agent.scenes[0].description, "城市与车流开场，建立商务节奏")

    def test_langchain_runtime_falls_back_to_deterministic_revision_when_patch_targets_unknown_scene(self):
        from backend.services.planner_models import RevisionPlanningResult, UserRevisionFeedback
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        deterministic_delegate = Mock()
        deterministic_delegate.replan_after_user_revision.return_value = (
            "agent-fallback",
            "execution-fallback",
            "fallback summary",
        )
        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )
        fake_llm = _FakeChatModel(
            result=RevisionPlanningResult(
                summary="更偏商务演示与销售沟通的版本",
                audience="销售团队",
                styleHint="商务演示风格",
                style="商务演示风格",
                changeSummary="已根据最新修改意见完成计划重写",
                scenePatches=[
                    {
                        "id": 99,
                        "description": "不存在的场景 patch",
                        "keywords": ["bad"],
                        "searchQuery": "bad",
                    }
                ],
            )
        )

        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=fake_llm,
            deterministic_delegate=deterministic_delegate,
        )
        result = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="整体再商务一点",
                sceneKeywordUpdates={},
            ),
        )

        self.assertEqual(result, ("agent-fallback", "execution-fallback", "fallback summary"))
        deterministic_delegate.replan_after_user_revision.assert_called_once()

    def test_langchain_runtime_falls_back_to_deterministic_revision_when_scene_patch_ids_repeat(self):
        from backend.services.planner_models import RevisionPlanningResult, UserRevisionFeedback
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        deterministic_delegate = Mock()
        deterministic_delegate.replan_after_user_revision.return_value = (
            "agent-fallback",
            "execution-fallback",
            "fallback summary",
        )
        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )
        fake_llm = _FakeChatModel(
            result=RevisionPlanningResult(
                summary="更偏商务演示与销售沟通的版本",
                audience="销售团队",
                styleHint="商务演示风格",
                style="商务演示风格",
                changeSummary="已根据最新修改意见完成计划重写",
                scenePatches=[
                    {
                        "id": 1,
                        "description": "城市与车流开场，建立商务节奏",
                        "keywords": ["office", "lobby", "team"],
                        "searchQuery": "office lobby team",
                    },
                    {
                        "id": 1,
                        "description": "重复 patch",
                        "keywords": ["duplicate"],
                        "searchQuery": "duplicate",
                    },
                ],
            )
        )

        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=fake_llm,
            deterministic_delegate=deterministic_delegate,
        )
        result = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="整体再商务一点",
                sceneKeywordUpdates={},
            ),
        )

        self.assertEqual(result, ("agent-fallback", "execution-fallback", "fallback summary"))
        deterministic_delegate.replan_after_user_revision.assert_called_once()

    def test_langchain_runtime_falls_back_to_deterministic_revision_when_model_raises(self):
        from backend.services.planner_models import UserRevisionFeedback
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        deterministic_delegate = Mock()
        deterministic_delegate.replan_after_user_revision.return_value = (
            "agent-fallback",
            "execution-fallback",
            "fallback summary",
        )
        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=_FakeChatModel(error=RuntimeError("revision planning failed")),
            deterministic_delegate=deterministic_delegate,
        )
        result = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="整体再商务一点",
                sceneKeywordUpdates={},
            ),
        )

        self.assertEqual(result, ("agent-fallback", "execution-fallback", "fallback summary"))
        deterministic_delegate.replan_after_user_revision.assert_called_once()

    def test_langchain_runtime_does_not_swallow_unexpected_revision_merge_errors(self):
        from backend.services.planner_models import RevisionPlanningResult, UserRevisionFeedback
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        deterministic_delegate = Mock()
        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )
        fake_llm = _FakeChatModel(
            result=RevisionPlanningResult(
                summary="更偏商务演示与销售沟通的版本",
                audience="销售团队",
                styleHint="商务演示风格",
                style="商务演示风格",
                changeSummary="已根据最新修改意见完成计划重写",
                scenePatches=[
                    {
                        "id": 1,
                        "description": "城市与车流开场，建立商务节奏",
                        "keywords": ["office", "lobby", "team"],
                        "searchQuery": "office lobby team",
                    }
                ],
            )
        )

        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=fake_llm,
            deterministic_delegate=deterministic_delegate,
        )

        with patch.object(runtime, "_validate_revision_merge", side_effect=TypeError("unexpected merge failure")):
            with self.assertRaisesRegex(TypeError, "unexpected merge failure"):
                runtime.replan_after_user_revision(
                    current_agent=current_agent,
                    current_execution=current_execution,
                    revision_feedback=UserRevisionFeedback(
                        message="整体再商务一点",
                        sceneKeywordUpdates={},
                    ),
                )

        deterministic_delegate.replan_after_user_revision.assert_not_called()

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

    def test_selector_returns_langchain_runtime_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            from backend.config import get_settings
            from backend.services.planner_runtime import get_planner_runtime
            import backend.services.planner_runtime_langchain as planner_runtime_langchain

            class LangChainPlannerRuntime:
                def __init__(self, model_name):
                    self.model_name = model_name

            get_settings.cache_clear()
            with patch.object(
                planner_runtime_langchain,
                "LangChainPlannerRuntime",
                LangChainPlannerRuntime,
            ):
                runtime = get_planner_runtime()
                self.assertEqual(runtime.__class__.__name__, "LangChainPlannerRuntime")
            get_settings.cache_clear()

    def test_selector_returns_deterministic_runtime_when_overridden(self):
        with patch.dict("os.environ", {"CLIPFORGE_PLANNER_MODE": "deterministic"}, clear=True):
            from backend.config import get_settings
            from backend.services.planner_runtime import get_planner_runtime

            get_settings.cache_clear()
            runtime = get_planner_runtime()
            self.assertEqual(runtime.__class__.__name__, "DeterministicPlannerRuntime")
            get_settings.cache_clear()

    def test_selector_reads_current_settings_after_backend_config_reload(self):
        import backend.services.planner_runtime as planner_runtime
        import backend.services.planner_runtime_langchain as planner_runtime_langchain

        class LangChainPlannerRuntime:
            def __init__(self, model_name):
                self.model_name = model_name

        with patch.dict("os.environ", {"CLIPFORGE_PLANNER_MODE": "deterministic"}, clear=True):
            from backend.config import get_settings

            get_settings.cache_clear()
            importlib.reload(planner_runtime)
            self.assertEqual(
                planner_runtime.get_planner_runtime().__class__.__name__,
                "DeterministicPlannerRuntime",
            )

        sys.modules.pop("backend.config", None)
        with patch.dict("os.environ", {}, clear=True):
            reloaded_config = importlib.import_module("backend.config")
            reloaded_config.get_settings.cache_clear()
            with patch.object(
                planner_runtime_langchain,
                "LangChainPlannerRuntime",
                LangChainPlannerRuntime,
            ):
                runtime = planner_runtime.get_planner_runtime()
                self.assertEqual(runtime.__class__.__name__, "LangChainPlannerRuntime")
            reloaded_config.get_settings.cache_clear()

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

    def test_deterministic_runtime_prefers_structured_diagnostics_for_rewrite(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        next_agent, next_execution, _change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[1],
                failureReason="素材检索失败",
                failureCategory="platform_blocked",
                retryStrategyHint="stock_footage_fallback",
                retryable=True,
            ),
        )

        self.assertEqual(
            next_execution.scenes[0].searchQuery,
            "software dashboard laptop",
        )
        self.assertEqual(
            next_execution.scenes[0].keywords,
            ["software", "dashboard", "laptop"],
        )
        self.assertEqual(next_agent.replanHistory[-1]["failureCategory"], "platform_blocked")
        self.assertEqual(next_agent.replanHistory[-1]["rewriteStrategy"], "stock_footage_fallback")

    def test_deterministic_runtime_uses_structured_failure_category_before_text_reason(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        next_agent, next_execution, _change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[1],
                failureReason="素材检索失败",
                failureCategory="no_inventory",
                retryStrategyHint="inventory_broaden",
                retryable=True,
            ),
        )

        self.assertEqual(
            next_execution.scenes[0].searchQuery,
            "product interface generic",
        )
        self.assertEqual(
            next_execution.scenes[0].keywords,
            ["product", "interface", "generic"],
        )
        self.assertEqual(next_agent.replanHistory[-1]["failureCategory"], "no_inventory")
        self.assertEqual(next_agent.replanHistory[-1]["rewriteStrategy"], "inventory_broaden")

    def test_deterministic_runtime_derives_rewrite_from_structured_failure_category_without_hint(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        next_agent, next_execution, _change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[1],
                failureReason="素材检索失败",
                failureCategory="platform_blocked",
                retryable=True,
            ),
        )

        self.assertEqual(
            next_execution.scenes[0].searchQuery,
            "software dashboard laptop",
        )
        self.assertEqual(
            next_execution.scenes[0].keywords,
            ["software", "dashboard", "laptop"],
        )
        self.assertEqual(next_agent.replanHistory[-1]["failureCategory"], "platform_blocked")
        self.assertEqual(next_agent.replanHistory[-1]["rewriteStrategy"], "stock_footage_fallback")

    def test_deterministic_runtime_falls_back_when_structured_values_are_unknown(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        next_agent, next_execution, _change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[1],
                failureReason="没有返回候选素材",
                failureCategory="made_up_category",
                retryStrategyHint="made_up_strategy",
                retryable=True,
            ),
        )

        self.assertEqual(
            next_execution.scenes[0].searchQuery,
            "product interface generic",
        )
        self.assertEqual(
            next_execution.scenes[0].keywords,
            ["product", "interface", "generic"],
        )
        self.assertEqual(next_agent.replanHistory[-1]["failureCategory"], "no_inventory")
        self.assertEqual(next_agent.replanHistory[-1]["rewriteStrategy"], "inventory_broaden")

    def test_deterministic_runtime_rewrites_platform_blocked_scene_to_stock_fallback_query(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        next_agent, next_execution, _change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[1],
                failureReason="YouTube 当前要求 PO Token，公开视频下载被平台策略限制。",
                retryable=True,
            ),
        )

        self.assertEqual(
            next_execution.scenes[0].searchQuery,
            "software dashboard laptop",
        )
        self.assertEqual(
            next_execution.scenes[0].keywords,
            ["software", "dashboard", "laptop"],
        )
        self.assertEqual(next_agent.replanHistory[-1]["failureCategory"], "platform_blocked")
        self.assertEqual(next_agent.replanHistory[-1]["rewriteStrategy"], "stock_footage_fallback")

    def test_deterministic_runtime_platform_blocked_partial_keyword_match_uses_conservative_fallback(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )
        current_agent = current_agent.model_copy(
            update={
                "scenes": [
                    current_agent.scenes[0].model_copy(
                        update={"keywords": ["product", "mobile"]}
                    ),
                    current_agent.scenes[1].model_copy(deep=True),
                ]
            }
        )
        current_execution = current_execution.model_copy(
            update={
                "scenes": [
                    current_execution.scenes[0].model_copy(
                        update={
                            "keywords": ["product", "mobile"],
                            "searchQuery": "product mobile",
                        }
                    ),
                    current_execution.scenes[1].model_copy(deep=True),
                ]
            }
        )

        _next_agent, next_execution, _change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[1],
                failureReason="YouTube 当前要求 PO Token，公开视频下载被平台策略限制。",
                retryable=True,
            ),
        )

        self.assertEqual(next_execution.scenes[0].keywords, ["product", "stock", "footage"])
        self.assertEqual(next_execution.scenes[0].searchQuery, "product stock footage")

    def test_deterministic_runtime_broadens_no_inventory_scene_without_dropping_core_intent(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        next_agent, next_execution, _change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[2],
                failureReason="pexels: 没有可下载候选素材",
                retryable=True,
            ),
        )

        self.assertEqual(
            next_execution.scenes[1].searchQuery,
            "feature workflow generic",
        )
        self.assertEqual(
            next_execution.scenes[1].keywords,
            ["feature", "workflow", "generic"],
        )
        self.assertEqual(next_agent.replanHistory[-1]["failureCategory"], "no_inventory")
        self.assertEqual(next_agent.replanHistory[-1]["rewriteStrategy"], "inventory_broaden")

    def test_deterministic_runtime_only_rewrites_failed_scenes_after_execution_feedback(self):
        from backend.services.planner_models import SearchExecutionFeedback
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        current_agent, current_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        _next_agent, next_execution, _change_summary = runtime.replan_after_execution_feedback(
            current_agent=current_agent,
            current_execution=current_execution,
            execution_feedback=SearchExecutionFeedback(
                failedSceneIds=[1],
                failureReason="YouTube said: Sign in to confirm you're not a bot.",
                retryable=True,
            ),
        )

        self.assertEqual(next_execution.scenes[0].searchQuery, "software dashboard laptop")
        self.assertEqual(next_execution.scenes[1].searchQuery, current_execution.scenes[1].searchQuery)
        self.assertEqual(next_execution.scenes[1].keywords, current_execution.scenes[1].keywords)

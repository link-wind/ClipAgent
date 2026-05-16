import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import openai
import httpx

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
    def __init__(
        self,
        result=None,
        error: Exception | None = None,
        invoke_result: str | None = None,
        invoke_error: Exception | None = None,
    ):
        self.result = result
        self.error = error
        self.schema = None
        self.invoke_result = invoke_result
        self.invoke_error = invoke_error

    def with_structured_output(self, schema, **_kwargs):
        self.schema = schema
        return _FakeStructuredPlanner(result=self.result, error=self.error)

    def invoke(self, _messages):
        if self.invoke_error is not None:
            raise self.invoke_error
        if self.invoke_result is None:
            raise RuntimeError("plain invoke was not configured")
        return SimpleNamespace(content=self.invoke_result)


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

    def test_langchain_runtime_falls_back_to_plain_json_when_structured_output_is_blocked(self):
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        blocked = openai.PermissionDeniedError(
            message="Your request was blocked.",
            response=httpx.Response(
                403,
                request=httpx.Request("POST", "https://example.com/v1/chat/completions"),
                json={"error": {"message": "Your request was blocked.", "type": "forbidden"}},
            ),
            body={"error": {"message": "Your request was blocked.", "type": "forbidden"}},
        )
        fake_llm = _FakeChatModel(
            error=blocked,
            invoke_result="""
            {
              "agentPlan": {
                "title": "足球高光短片",
                "goal": "生成一条踢足球的20秒视频",
                "summary": "以运动张力和射门高潮为主线。",
                "scenes": [
                  {
                    "id": 1,
                    "purpose": "建立比赛氛围",
                    "description": "球员带球推进，观众席有动感反应",
                    "keywords": ["soccer", "dribble", "stadium"],
                    "duration": 8
                  },
                  {
                    "id": 2,
                    "purpose": "突出射门高光",
                    "description": "禁区射门和进球庆祝",
                    "keywords": ["goal", "kick", "celebration"],
                    "duration": 8
                  }
                ]
              },
              "executionPlan": {
                "title": "足球高光短片",
                "targetDuration": 20,
                "style": "运动高光",
                "scenes": [
                  {
                    "id": 1,
                    "description": "球员带球推进，观众席有动感反应",
                    "keywords": ["soccer", "dribble", "stadium"],
                    "searchQuery": "soccer dribble stadium",
                    "duration": 8
                  },
                  {
                    "id": 2,
                    "description": "禁区射门和进球庆祝",
                    "keywords": ["goal", "kick", "celebration"],
                    "searchQuery": "goal kick celebration",
                    "duration": 8
                  }
                ]
              }
            }
            """,
        )

        runtime = LangChainPlannerRuntime(model_name="gpt-5.4", llm=fake_llm)
        agent_plan, execution_plan = runtime.build_plan_from_brief("帮我剪一个踢足球的20秒视频")

        self.assertEqual(agent_plan.title, "足球高光短片")
        self.assertEqual(execution_plan.style, "运动高光")
        self.assertEqual(execution_plan.scenes[0].searchQuery, "soccer dribble stadium")

    def test_langchain_runtime_falls_back_to_compact_initial_plan_when_structured_output_times_out(self):
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        timed_out = openai.APITimeoutError(
            request=httpx.Request("POST", "https://example.com/v1/chat/completions")
        )
        fake_llm = _FakeChatModel(
            error=timed_out,
            invoke_result="""
            {
              "title": "20秒踢足球短视频",
              "goal": "剪辑一支节奏明快、突出足球动作与热血氛围的20秒短视频",
              "summary": "通过带球、射门和庆祝三个片段，快速展现足球运动的张力。",
              "style": "热血动感",
              "targetDuration": 20,
              "scenes": [
                {
                  "id": 1,
                  "purpose": "开场建立运动氛围",
                  "description": "展示球员带球推进。",
                  "keywords": ["soccer", "dribble", "field"],
                  "searchQuery": "soccer dribble field",
                  "duration": 6
                },
                {
                  "id": 2,
                  "purpose": "突出核心动作",
                  "description": "展示射门瞬间。",
                  "keywords": ["soccer", "shot", "goal"],
                  "searchQuery": "soccer shot goal",
                  "duration": 7
                },
                {
                  "id": 3,
                  "purpose": "结尾强化情绪",
                  "description": "展示进球庆祝。",
                  "keywords": ["soccer", "celebration", "team"],
                  "searchQuery": "soccer celebration team",
                  "duration": 7
                }
              ]
            }
            """,
        )

        runtime = LangChainPlannerRuntime(model_name="gpt-5.4", llm=fake_llm)
        agent_plan, execution_plan = runtime.build_plan_from_brief("帮我剪一个踢足球的20秒视频")

        self.assertEqual(agent_plan.title, "20秒踢足球短视频")
        self.assertEqual(agent_plan.scenes[1].purpose, "突出核心动作")
        self.assertEqual(execution_plan.targetDuration, 20)
        self.assertEqual(execution_plan.scenes[2].searchQuery, "soccer celebration team")

    def test_langchain_runtime_falls_back_to_deterministic_initial_plan_when_compact_plan_still_fails(self):
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        timed_out = openai.APITimeoutError(
            request=httpx.Request("POST", "https://example.com/v1/chat/completions")
        )
        deterministic_delegate = Mock()
        deterministic_delegate.build_plan_from_brief.return_value = ("agent-fallback", "execution-fallback")
        fake_llm = _FakeChatModel(
            error=timed_out,
            invoke_error=openai.APIStatusError(
                message="upstream unavailable",
                response=httpx.Response(
                    503,
                    request=httpx.Request("POST", "https://example.com/v1/chat/completions"),
                    json={"error": {"message": "upstream unavailable", "type": "server_error"}},
                ),
                body={"error": {"message": "upstream unavailable", "type": "server_error"}},
            ),
        )

        runtime = LangChainPlannerRuntime(
            model_name="gpt-5.4",
            llm=fake_llm,
            deterministic_delegate=deterministic_delegate,
        )
        result = runtime.build_plan_from_brief("帮我剪一个踢足球的20秒视频")

        self.assertEqual(result, ("agent-fallback", "execution-fallback"))
        deterministic_delegate.build_plan_from_brief.assert_called_once_with("帮我剪一个踢足球的20秒视频")

    def test_langchain_runtime_can_prefer_compact_initial_plan_without_trying_structured_output(self):
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        fake_llm = _FakeChatModel(
            error=RuntimeError("structured output should be skipped"),
            invoke_result="""
            {
              "title": "20秒踢足球短视频",
              "goal": "剪辑一支节奏明快、突出足球动作的20秒短视频",
              "summary": "通过带球、射门和庆祝三个片段形成完整节奏。",
              "style": "热血动感",
              "targetDuration": 20,
              "scenes": [
                {
                  "id": 1,
                  "purpose": "开场建立运动氛围",
                  "description": "展示球员带球推进。",
                  "keywords": ["soccer", "dribble", "field"],
                  "searchQuery": "soccer dribble field",
                  "duration": 6
                },
                {
                  "id": 2,
                  "purpose": "突出核心动作",
                  "description": "展示射门瞬间。",
                  "keywords": ["soccer", "shot", "goal"],
                  "searchQuery": "soccer shot goal",
                  "duration": 7
                },
                {
                  "id": 3,
                  "purpose": "结尾强化情绪",
                  "description": "展示进球庆祝。",
                  "keywords": ["soccer", "celebration", "team"],
                  "searchQuery": "soccer celebration team",
                  "duration": 7
                }
              ]
            }
            """,
        )

        runtime = LangChainPlannerRuntime(
            model_name="gpt-5.4",
            llm=fake_llm,
            prefer_compact_initial_plan=True,
        )
        agent_plan, execution_plan = runtime.build_plan_from_brief("帮我剪一个踢足球的20秒视频")

        self.assertEqual(agent_plan.title, "20秒踢足球短视频")
        self.assertEqual(execution_plan.scenes[0].searchQuery, "soccer dribble field")

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

    def test_langchain_runtime_allows_revision_result_to_clear_open_issues(self):
        from backend.services.planner_models import RevisionPlanningResult, UserRevisionFeedback
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        deterministic_delegate = Mock()
        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )
        current_agent = current_agent.model_copy(
            update={"openIssues": [{"id": "issue-1", "summary": "still open"}]},
            deep=True,
        )
        fake_llm = _FakeChatModel(
            result=RevisionPlanningResult(
                changeSummary="已解决当前待确认问题",
                openIssues=[],
            )
        )

        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=fake_llm,
            deterministic_delegate=deterministic_delegate,
        )
        next_agent, next_execution, change_summary = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="这些待确认问题已经解决",
                sceneKeywordUpdates={},
            ),
        )

        self.assertEqual(change_summary, "已解决当前待确认问题")
        self.assertEqual(next_agent.openIssues, [])
        self.assertEqual(next_execution.scenes[0].searchQuery, current_execution.scenes[0].searchQuery)
        deterministic_delegate.replan_after_user_revision.assert_not_called()

    def test_langchain_runtime_preserves_open_issues_when_revision_result_omits_open_issues(self):
        from backend.services.planner_models import RevisionPlanningResult, UserRevisionFeedback
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        deterministic_delegate = Mock()
        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )
        current_agent = current_agent.model_copy(
            update={"openIssues": [{"id": "issue-1", "summary": "still open"}]},
            deep=True,
        )
        fake_llm = _FakeChatModel(
            result=RevisionPlanningResult(
                changeSummary="保持当前待确认问题不变",
            )
        )

        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=fake_llm,
            deterministic_delegate=deterministic_delegate,
        )
        next_agent, _next_execution, change_summary = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="先不动这些待确认问题",
                sceneKeywordUpdates={},
            ),
        )

        self.assertEqual(change_summary, "保持当前待确认问题不变")
        self.assertEqual(next_agent.openIssues, [{"id": "issue-1", "summary": "still open"}])
        deterministic_delegate.replan_after_user_revision.assert_not_called()

    def test_langchain_runtime_falls_back_when_scene_keyword_override_is_explicitly_empty(self):
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
        result = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="场景1关键词清空",
                sceneKeywordUpdates={1: []},
            ),
        )

        self.assertEqual(result, ("agent-fallback", "execution-fallback", "fallback summary"))
        deterministic_delegate.replan_after_user_revision.assert_called_once()

    def test_langchain_runtime_falls_back_when_scene_keyword_override_targets_unknown_scene(self):
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
        result = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="场景99关键词改成 foo",
                sceneKeywordUpdates={99: ["foo"]},
            ),
        )

        self.assertEqual(result, ("agent-fallback", "execution-fallback", "fallback summary"))
        deterministic_delegate.replan_after_user_revision.assert_called_once()

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

    def test_langchain_runtime_does_not_fall_back_when_revision_runnable_construction_fails(self):
        from backend.services.planner_models import UserRevisionFeedback
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        deterministic_delegate = Mock()
        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=_FakeChatModel(result=None),
            deterministic_delegate=deterministic_delegate,
        )

        with patch.object(runtime, "_revision_runnable", side_effect=TypeError("bad runnable construction")):
            with self.assertRaisesRegex(TypeError, "bad runnable construction"):
                runtime.replan_after_user_revision(
                    current_agent=current_agent,
                    current_execution=current_execution,
                    revision_feedback=UserRevisionFeedback(
                        message="整体再商务一点",
                        sceneKeywordUpdates={},
                    ),
                )

        deterministic_delegate.replan_after_user_revision.assert_not_called()

    def test_langchain_runtime_does_not_fall_back_when_revision_message_construction_fails(self):
        from backend.services.planner_models import UserRevisionFeedback
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime

        deterministic_delegate = Mock()
        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=_FakeChatModel(result=None),
            deterministic_delegate=deterministic_delegate,
        )

        with patch.object(runtime, "_build_revision_messages", side_effect=TypeError("bad message construction")):
            with self.assertRaisesRegex(TypeError, "bad message construction"):
                runtime.replan_after_user_revision(
                    current_agent=current_agent,
                    current_execution=current_execution,
                    revision_feedback=UserRevisionFeedback(
                        message="整体再商务一点",
                        sceneKeywordUpdates={},
                    ),
                )

        deterministic_delegate.replan_after_user_revision.assert_not_called()

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

    def test_deterministic_runtime_uses_brief_keywords_for_coffee_brief(self):
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        _agent_plan, execution_plan = runtime.build_plan_from_brief(
            "给咖啡品牌做一个15秒竖屏短视频，突出 latte art、barista 手冲细节、温暖生活方式镜头。"
        )

        self.assertEqual(execution_plan.scenes[0].keywords, ["coffee", "latte", "art"])
        self.assertEqual(execution_plan.scenes[0].searchQuery, "coffee latte art")
        self.assertEqual(execution_plan.scenes[1].keywords, ["barista", "coffee", "lifestyle"])
        self.assertEqual(execution_plan.scenes[1].searchQuery, "barista coffee lifestyle")

    def test_deterministic_runtime_uses_brief_keywords_for_city_brief(self):
        from backend.services.planner_runtime_deterministic import (
            DeterministicPlannerRuntime,
        )

        runtime = DeterministicPlannerRuntime()
        _agent_plan, execution_plan = runtime.build_plan_from_brief(
            "做一个城市黄昏车流氛围短片，突出夜景和霓虹。"
        )

        self.assertEqual(execution_plan.scenes[0].keywords, ["城市", "黄昏", "车流"])
        self.assertEqual(execution_plan.scenes[0].searchQuery, "城市 黄昏 车流")
        self.assertEqual(execution_plan.scenes[1].keywords, ["夜景", "霓虹", "城市"])
        self.assertEqual(execution_plan.scenes[1].searchQuery, "夜景 霓虹 城市")

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

    def test_langchain_runtime_reads_openai_credentials_from_runtime_settings(self):
        import backend.services.planner_runtime_langchain as planner_runtime_langchain
        from backend.services.runtime_config_service import RuntimeConfigService

        with tempfile.TemporaryDirectory() as temp_dir:
            service = RuntimeConfigService(config_path=Path(temp_dir) / "runtime_config.local.json")
            service.update(
                {
                    "OPENAI_API_KEY": "runtime-openai-key",
                    "OPENAI_BASE_URL": "https://runtime.example/v1",
                }
            )

            captured = {}

            class FakeChatOpenAI:
                def __init__(self, **kwargs):
                    captured.update(kwargs)

            with patch.object(planner_runtime_langchain, "ChatOpenAI", FakeChatOpenAI), patch.object(
                planner_runtime_langchain,
                "runtime_config_service",
                service,
                create=True,
            ):
                planner_runtime_langchain.LangChainPlannerRuntime(model_name="gpt-4o-mini")

            self.assertEqual(captured.get("api_key"), "runtime-openai-key")
            self.assertEqual(captured.get("base_url"), "https://runtime.example/v1")
            self.assertEqual(captured["model"], "gpt-4o-mini")

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

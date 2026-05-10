import unittest


class _FakeStructuredPlanner:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        if self.error is not None:
            raise self.error
        return self.result


class _FakeChatModel:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.schema = None
        self.planner = None

    def with_structured_output(self, schema):
        self.schema = schema
        self.planner = _FakeStructuredPlanner(result=self.result, error=self.error)
        return self.planner


class GroundingPlannerRuntimeContractTests(unittest.TestCase):
    def test_retrieval_query_pack_wraps_queries_and_assumptions(self):
        from backend.services.grounding_planner_models import RetrievalQueryPack

        pack = RetrievalQueryPack(
            productName="Notion AI",
            audience="销售团队",
            styleHint="快节奏社媒短片",
            featureHints=["AI", "知识库"],
            assumptions=["The brief refers to the Notion product, not a generic notion."],
            queries=[
                {
                    "text": "notion ai demo",
                    "intent": "product_demo",
                    "providers": ["youtube"],
                    "priority": 10,
                },
                {
                    "text": "software dashboard laptop",
                    "intent": "stock_fallback",
                    "providers": ["pexels"],
                    "priority": 30,
                },
            ],
        )

        self.assertEqual(pack.productName, "Notion AI")
        self.assertEqual(pack.queries[0].intent, "product_demo")
        self.assertEqual(pack.queries[1].providers, ["pexels"])


class GroundingPlannerRuntimeTests(unittest.TestCase):
    def test_runtime_builds_normalized_query_pack_from_structured_output(self):
        from backend.services.grounding_planner_models import RetrievalQueryPack
        from backend.services.grounding_planner_runtime import GroundingPlannerRuntime

        fake_llm = _FakeChatModel(
            result=RetrievalQueryPack(
                productName=" Notion AI ",
                audience=" 销售团队 ",
                styleHint=" 快节奏社媒短片 ",
                featureHints=[" AI ", " 知识库 "],
                assumptions=[" 这是 SaaS 产品首页演示 "],
                queries=[
                    {
                        "text": " notion ai demo ",
                        "intent": "product_demo",
                        "providers": ["youtube"],
                        "priority": 10,
                    },
                    {
                        "text": " software dashboard laptop ",
                        "intent": "stock_fallback",
                        "providers": ["pexels"],
                        "priority": 30,
                    },
                ],
            )
        )

        runtime = GroundingPlannerRuntime(model_name="gpt-4o-mini", llm=fake_llm)
        pack = runtime.build_query_pack("给 Notion AI 做一个产品介绍视频")

        self.assertEqual(pack.productName, "Notion AI")
        self.assertEqual(pack.audience, "销售团队")
        self.assertEqual(pack.featureHints, ["AI", "知识库"])
        self.assertEqual(pack.queries[0].text, "notion ai demo")

    def test_runtime_rejects_blank_query_text(self):
        from backend.services.grounding_planner_models import RetrievalQueryPack
        from backend.services.grounding_planner_runtime import GroundingPlannerRuntime

        fake_llm = _FakeChatModel(
            result=RetrievalQueryPack(
                productName="Notion AI",
                queries=[
                    {
                        "text": "   ",
                        "intent": "product_demo",
                        "providers": ["youtube"],
                        "priority": 10,
                    },
                    {
                        "text": "notion workspace overview",
                        "intent": "feature_workflow",
                        "providers": ["pexels"],
                        "priority": 20,
                    }
                ],
            )
        )

        runtime = GroundingPlannerRuntime(model_name="gpt-4o-mini", llm=fake_llm)

        with self.assertRaisesRegex(ValueError, "query text"):
            runtime.build_query_pack("给 Notion AI 做一个产品介绍视频")

    def test_runtime_bubbles_up_model_failures(self):
        from backend.services.grounding_planner_runtime import GroundingPlannerRuntime

        runtime = GroundingPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=_FakeChatModel(error=RuntimeError("Grounding planning failed")),
        )

        with self.assertRaisesRegex(RuntimeError, "Grounding planning failed"):
            runtime.build_query_pack("给 Notion AI 做一个产品介绍视频")

    def test_runtime_rejects_query_pack_with_too_few_queries(self):
        from backend.services.grounding_planner_models import RetrievalQueryPack
        from backend.services.grounding_planner_runtime import GroundingPlannerRuntime

        runtime = GroundingPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=_FakeChatModel(
                result=RetrievalQueryPack(
                    productName="Notion AI",
                    queries=[
                        {
                            "text": "notion ai demo",
                            "intent": "product_demo",
                            "providers": ["youtube"],
                            "priority": 10,
                        }
                    ],
                )
            ),
        )

        with self.assertRaisesRegex(ValueError, "2 to 5 queries"):
            runtime.build_query_pack("给 Notion AI 做一个产品介绍视频")

    def test_runtime_uses_structured_schema_and_blank_brief_fallback(self):
        from backend.services.grounding_planner_models import RetrievalQueryPack
        from backend.services.grounding_planner_runtime import (
            GROUNDING_QUERY_PLANNER_SYSTEM_PROMPT,
            GroundingPlannerRuntime,
        )

        fake_llm = _FakeChatModel(
            result=RetrievalQueryPack(
                productName="Notion AI",
                queries=[
                    {
                        "text": "notion ai demo",
                        "intent": "product_demo",
                        "providers": ["youtube"],
                        "priority": 10,
                    },
                    {
                        "text": "software dashboard laptop",
                        "intent": "stock_fallback",
                        "providers": ["pexels"],
                        "priority": 20,
                    },
                ],
            )
        )

        runtime = GroundingPlannerRuntime(model_name="gpt-4o-mini", llm=fake_llm)
        runtime.build_query_pack("   ")

        self.assertIs(fake_llm.schema, RetrievalQueryPack)
        self.assertEqual(len(fake_llm.planner.messages), 2)
        self.assertEqual(
            fake_llm.planner.messages[0].content,
            GROUNDING_QUERY_PLANNER_SYSTEM_PROMPT,
        )
        self.assertEqual(fake_llm.planner.messages[1].content, "product intro video")

import unittest


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

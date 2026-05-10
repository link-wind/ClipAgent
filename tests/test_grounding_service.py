import unittest

from backend.services.asset_providers.types import AssetCandidate
from backend.services.grounding_planner_models import RetrievalQueryPack
from backend.services.grounding_service import GroundingService


class _FakeRuntime:
    def __init__(self, pack=None, error: Exception | None = None):
        self.pack = pack
        self.error = error

    def build_query_pack(self, _brief: str):
        if self.error is not None:
            raise self.error
        return self.pack


class GroundingServiceTests(unittest.TestCase):
    def test_build_grounding_summary_uses_query_plan_and_preserves_flat_search_queries(self):
        calls = []

        def fixture_search(tokens, max_results=3):
            calls.append(("fixture", tuple(tokens), max_results))
            return []

        def youtube_search(tokens, max_results=3):
            calls.append(("youtube", tuple(tokens), max_results))
            return [
                AssetCandidate(
                    provider="youtube",
                    id="yt-1",
                    title="Notion AI demo",
                    source_url="https://youtube.test/watch?v=yt-1",
                    download_url="https://youtube.test/watch?v=yt-1",
                    thumbnail="https://img.test/yt-1.jpg",
                    diagnostics={"score": 5, "query": " ".join(tokens)},
                )
            ]

        service = GroundingService(
            retrieval_runtime=_FakeRuntime(
                pack=RetrievalQueryPack(
                    productName="Notion AI",
                    audience="销售团队",
                    styleHint="快节奏社媒短片",
                    featureHints=["AI", "知识库"],
                    assumptions=["The brief refers to the Notion product."],
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
            ),
            fixture_search=fixture_search,
            pexels_search=lambda tokens, max_results=3: [],
            youtube_search=youtube_search,
        )

        summary = service.build_grounding_summary("给 Notion AI 做一个产品介绍视频")

        self.assertEqual(summary.productName, "Notion AI")
        self.assertEqual(summary.assumptions, ["The brief refers to the Notion product."])
        self.assertEqual(summary.searchQueries, ["notion ai demo", "software dashboard laptop"])
        self.assertEqual(summary.queryPlan[0]["intent"], "product_demo")
        self.assertEqual(summary.candidates[0].id, "youtube:yt-1")
        self.assertIn(("youtube", ("notion", "ai", "demo"), 3), calls)

    def test_search_candidates_for_query_plan_respects_provider_preference_order(self):
        calls = []

        def fixture_search(tokens, max_results=3):
            calls.append(("fixture", tuple(tokens)))
            return []

        def pexels_search(tokens, max_results=3):
            calls.append(("pexels", tuple(tokens)))
            return []

        def youtube_search(tokens, max_results=3):
            calls.append(("youtube", tuple(tokens)))
            return []

        service = GroundingService(
            retrieval_runtime=_FakeRuntime(),
            fixture_search=fixture_search,
            pexels_search=pexels_search,
            youtube_search=youtube_search,
        )

        service.search_candidates_for_query_plan(
            [
                {
                    "text": "team productivity workspace",
                    "intent": "stock_fallback",
                    "providers": ["pexels", "youtube"],
                    "priority": 20,
                }
            ]
        )

        self.assertEqual(
            calls,
            [
                ("fixture", ("team", "productivity", "workspace")),
                ("pexels", ("team", "productivity", "workspace")),
                ("youtube", ("team", "productivity", "workspace")),
            ],
        )

    def test_build_grounding_summary_falls_back_to_deterministic_queries_when_runtime_fails(self):
        service = GroundingService(
            retrieval_runtime=_FakeRuntime(error=RuntimeError("planner unavailable")),
            fixture_search=lambda tokens, max_results=3: [],
            pexels_search=lambda tokens, max_results=3: [],
            youtube_search=lambda tokens, max_results=3: [],
        )

        summary = service.build_grounding_summary("给 Notion AI 做一个 30 秒产品亮点视频")

        self.assertIn("Notion", summary.searchQueries)
        self.assertEqual(summary.queryPlan[0]["intent"], "brand_exact")
        self.assertIn("deterministic fallback", summary.assumptions[-1])

import os
import unittest
from unittest.mock import patch

from backend.models.agent import AgentGroundingSummary
from backend.services.asset_providers.types import AssetCandidate
from backend.services.grounding_planner_models import RetrievalQuery
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

    def test_build_grounding_summary_preserves_existing_context_when_planner_metadata_is_blank(self):
        service = GroundingService(
            retrieval_runtime=_FakeRuntime(
                pack=RetrievalQueryPack(
                    queries=[
                        {
                            "text": "notion ai demo",
                            "intent": "product_demo",
                            "providers": ["youtube"],
                            "priority": 10,
                        }
                    ]
                )
            ),
            fixture_search=lambda tokens, max_results=3: [],
            pexels_search=lambda tokens, max_results=3: [],
            youtube_search=lambda tokens, max_results=3: [
                AssetCandidate(
                    provider="youtube",
                    id="yt-ctx",
                    title="Notion AI demo",
                    source_url="https://youtube.test/watch?v=yt-ctx",
                    download_url="https://youtube.test/watch?v=yt-ctx",
                )
            ],
        )

        summary = service.build_grounding_summary(
            "继续补充这个任务",
            existing=AgentGroundingSummary(
                productName="Notion AI",
                audience="销售团队",
                styleHint="快节奏社媒短片",
                featureHints=["AI", "知识库"],
            ),
        )

        self.assertEqual(summary.productName, "Notion AI")
        self.assertEqual(summary.audience, "销售团队")
        self.assertEqual(summary.styleHint, "快节奏社媒短片")
        self.assertEqual(summary.featureHints, ["AI", "知识库"])

    def test_build_grounding_summary_retries_same_stock_query_with_fallback_provider(self):
        def pexels_search(tokens, max_results=3):
            if tuple(tokens) != ("software", "dashboard", "laptop"):
                return []
            return [
                AssetCandidate(
                    provider="pexels",
                    id="pexels-1",
                    title="Software dashboard laptop",
                    source_url="https://pexels.test/videos/1",
                    download_url="https://pexels.test/videos/1.mp4",
                )
            ]

        service = GroundingService(
            retrieval_runtime=_FakeRuntime(
                pack=RetrievalQueryPack(
                    queries=[
                        {
                            "text": "software dashboard laptop",
                            "intent": "stock_fallback",
                            "providers": ["youtube"],
                            "priority": 10,
                        }
                    ]
                )
            ),
            fixture_search=lambda tokens, max_results=3: [],
            pexels_search=pexels_search,
            youtube_search=lambda tokens, max_results=3: [],
        )

        summary = service.build_grounding_summary("software dashboard laptop")

        self.assertEqual(summary.candidates[0].id, "pexels:pexels-1")
        self.assertIn("pexels", summary.queryPlan[0]["providers"])

    def test_provider_order_respects_fixture_provider_enabled_flag(self):
        service = GroundingService(
            retrieval_runtime=_FakeRuntime(),
            fixture_search=lambda tokens, max_results=3: [],
            pexels_search=lambda tokens, max_results=3: [],
            youtube_search=lambda tokens, max_results=3: [],
        )

        with patch.dict(os.environ, {"FIXTURE_PROVIDER_ENABLED": "0"}, clear=True):
            query = RetrievalQuery(
                text="workspace collaboration",
                intent="stock_fallback",
                providers=["pexels"],
                priority=10,
            )
            self.assertEqual(service._provider_order_for_query(query), ["pexels"])

    def test_build_grounding_summary_preserves_generic_fallback_query_when_existing_queries_fill_limit(self):
        def fixture_search(tokens, max_results=3):
            if tuple(tokens) != ("城市",):
                return []
            return [
                AssetCandidate(
                    provider="fixture",
                    id="city-1",
                    title="City lifestyle",
                    source_url="/fixtures/city-1.mp4",
                    download_url="/fixtures/city-1.mp4",
                )
            ]

        service = GroundingService(
            retrieval_runtime=_FakeRuntime(error=RuntimeError("planner unavailable")),
            fixture_search=fixture_search,
            pexels_search=lambda tokens, max_results=3: [],
            youtube_search=lambda tokens, max_results=3: [],
        )

        summary = service.build_grounding_summary(
            "整体再商务一点，目标受众改成销售团队",
            existing=AgentGroundingSummary(
                productName="Notion",
                audience="销售团队",
                featureHints=["亮点"],
                searchQueries=[
                    "Notion",
                    "销售团队",
                    "亮点",
                    "整体再商务一点 目标受众改成销售团队",
                    "给 Notion AI 做一个",
                ],
            ),
        )

        self.assertEqual(summary.status, "needs_confirmation")
        self.assertIn("城市", summary.searchQueries)
        self.assertEqual(summary.candidates[0].id, "fixture:city-1")

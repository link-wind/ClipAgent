from dataclasses import dataclass, field
import os
import re
from typing import Any, Callable, Iterable

from backend.config import get_settings
from backend.models.agent import AgentGroundingCandidate, AgentGroundingSummary
from backend.services.asset_providers.fixture import search_fixture_candidates
from backend.services.asset_providers.pexels import search_pexels_candidates
from backend.services.asset_providers.youtube import search_youtube_candidates
from backend.services.grounding_planner_models import RetrievalQuery, RetrievalQueryPack
from backend.services.grounding_planner_runtime import GroundingPlannerRuntime


@dataclass(frozen=True)
class ParsedBrief:
    product_name: str = ""
    audience: str = ""
    style_hint: str = ""
    feature_hints: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)


class GroundingService:
    def __init__(
        self,
        *,
        retrieval_runtime=None,
        fixture_search: Callable[..., list[Any]] | None = None,
        pexels_search: Callable[..., list[Any]] | None = None,
        youtube_search: Callable[..., list[Any]] | None = None,
    ) -> None:
        self._retrieval_runtime = retrieval_runtime
        self._fixture_search = fixture_search or search_fixture_candidates
        self._pexels_search = pexels_search or search_pexels_candidates
        self._youtube_search = youtube_search or search_youtube_candidates
        self._fixture_search_injected = fixture_search is not None
        self._pexels_search_injected = pexels_search is not None
        self._youtube_search_injected = youtube_search is not None

    def parse_brief(self, prompt: str) -> ParsedBrief:
        text = (prompt or "").strip()
        if not text:
            return ParsedBrief()

        product_name = self._extract_product_name(text)
        feature_hints = self._extract_feature_hints(text)
        audience = self._extract_audience(text)
        style_hint = self._extract_style_hint(text)
        search_queries = self._build_search_queries(product_name, audience, feature_hints, text)

        return ParsedBrief(
            product_name=product_name,
            audience=audience,
            style_hint=style_hint,
            feature_hints=feature_hints,
            search_queries=search_queries,
        )

    def build_grounding_summary(
        self,
        prompt: str,
        existing: AgentGroundingSummary | dict[str, Any] | None = None,
    ) -> AgentGroundingSummary:
        brief = self._merge_brief(self.parse_brief(prompt), existing, prompt)
        fallback_query_pack = self._fallback_query_pack(brief)
        runtime_error = None
        try:
            query_pack = self._get_retrieval_runtime().build_query_pack(prompt)
        except Exception as exc:
            runtime_error = exc
            query_pack = self._fallback_query_pack(brief, reason=str(exc))

        candidates = self.search_candidates_for_query_plan(query_pack.queries)
        if not candidates:
            supplemental_queries = self._query_diff(query_pack.queries, fallback_query_pack.queries)
            if supplemental_queries:
                query_pack = self._merge_query_pack(query_pack, fallback_query_pack)
                candidates = self.search_candidates_for_query_plan(supplemental_queries)
        return AgentGroundingSummary(
            status="needs_confirmation" if candidates else "pending_search",
            productName=query_pack.productName,
            audience=query_pack.audience,
            styleHint=query_pack.styleHint,
            featureHints=query_pack.featureHints,
            assumptions=query_pack.assumptions,
            searchQueries=[query.text for query in query_pack.queries],
            queryPlan=[query.model_dump(mode="json") for query in query_pack.queries],
            candidates=candidates,
            selectedCandidateIds=[],
        )

    def search_candidates(self, search_queries: list[str]) -> list[AgentGroundingCandidate]:
        query_plan = [
            RetrievalQuery(
                text=query,
                intent="stock_fallback",
                providers=["pexels", "youtube"],
                priority=index * 10,
            )
            for index, query in enumerate(search_queries, start=1)
            if query and query.strip()
        ]
        return self.search_candidates_for_query_plan(query_plan)

    def search_candidates_for_query_plan(
        self,
        query_plan: list[RetrievalQuery] | list[dict[str, Any]],
    ) -> list[AgentGroundingCandidate]:
        normalized_queries = [
            query
            for query in sorted(
                (self._normalize_query(query) for query in query_plan),
                key=lambda item: item.priority,
            )
            if query.text.strip()
        ]
        if not normalized_queries:
            return []

        aggregated: list[AgentGroundingCandidate] = []
        seen_ids: set[str] = set()

        for query in normalized_queries:
            query_tokens = self._split_query(query.text)
            if not query_tokens:
                continue
            for provider in self._provider_order_for_query(query):
                for candidate in self._search_with_provider(provider, query_tokens, max_results=3):
                    grounding_candidate = self._to_grounding_candidate(candidate)
                    if grounding_candidate.id in seen_ids:
                        continue
                    seen_ids.add(grounding_candidate.id)
                    aggregated.append(grounding_candidate)

        return aggregated

    def _normalize_query(self, query: RetrievalQuery | dict[str, Any]) -> RetrievalQuery:
        if isinstance(query, RetrievalQuery):
            return query
        return RetrievalQuery.model_validate(query)

    def _get_retrieval_runtime(self):
        if self._retrieval_runtime is None:
            self._retrieval_runtime = GroundingPlannerRuntime(model_name=get_settings().planner_model)
        return self._retrieval_runtime

    def _provider_order_for_query(self, query: RetrievalQuery) -> list[str]:
        providers: list[str] = []
        if self._fixture_grounding_enabled():
            providers.append("fixture")
        for provider in query.providers:
            if provider not in providers:
                providers.append(provider)
        return providers

    def _search_with_provider(self, provider: str, query_tokens: list[str], max_results: int = 3) -> list[Any]:
        if provider == "fixture":
            if not self._fixture_grounding_enabled():
                return []
            return self._fixture_search(query_tokens, max_results=max_results)
        if provider == "pexels":
            if not (self._pexels_search_injected or self._remote_grounding_enabled()):
                return []
            return self._pexels_search(query_tokens, max_results=max_results)
        if provider == "youtube":
            if not (self._youtube_search_injected or self._youtube_grounding_enabled()):
                return []
            return self._youtube_search(query_tokens, max_results=max_results)
        return []

    def _fallback_query_pack(self, brief: ParsedBrief, reason: str | None = None) -> RetrievalQueryPack:
        queries: list[RetrievalQuery] = []
        priority = 10

        if brief.product_name:
            queries.append(
                RetrievalQuery(
                    text=brief.product_name,
                    intent="brand_exact",
                    providers=["youtube"],
                    priority=priority,
                )
            )
            priority += 10

        fallback_terms = self._merge_unique(brief.search_queries, self._build_fallback_queries(brief))
        for text in fallback_terms:
            if text == brief.product_name:
                continue
            queries.append(
                RetrievalQuery(
                    text=text,
                    intent="stock_fallback",
                    providers=["pexels"],
                    priority=priority,
                )
            )
            priority += 10

        assumptions = []
        if reason:
            assumptions.append(f"Used deterministic fallback query plan because retrieval planner failed: {reason}")

        return RetrievalQueryPack(
            productName=brief.product_name,
            audience=brief.audience,
            styleHint=brief.style_hint,
            featureHints=brief.feature_hints,
            assumptions=assumptions,
            queries=queries[:5],
        )

    def _merge_query_pack(
        self,
        primary: RetrievalQueryPack,
        secondary: RetrievalQueryPack,
    ) -> RetrievalQueryPack:
        merged_queries = self._merge_query_objects(primary.queries, secondary.queries)
        return RetrievalQueryPack(
            productName=primary.productName or secondary.productName,
            audience=primary.audience or secondary.audience,
            styleHint=primary.styleHint or secondary.styleHint,
            featureHints=self._merge_unique(primary.featureHints, secondary.featureHints),
            assumptions=self._merge_unique(primary.assumptions, secondary.assumptions),
            queries=merged_queries,
        )

    def _merge_query_objects(
        self,
        primary: Iterable[RetrievalQuery],
        secondary: Iterable[RetrievalQuery],
    ) -> list[RetrievalQuery]:
        merged: list[RetrievalQuery] = []
        index_by_key: dict[tuple[str, str], int] = {}

        for query in list(primary) + list(secondary):
            key = self._query_key(query)
            if key not in index_by_key:
                index_by_key[key] = len(merged)
                merged.append(query)
                continue

            existing = merged[index_by_key[key]]
            merged[index_by_key[key]] = existing.model_copy(
                update={
                    "providers": self._merge_unique(existing.providers, query.providers),
                    "priority": min(existing.priority, query.priority),
                }
            )

        return sorted(merged, key=lambda item: item.priority)

    def _query_diff(
        self,
        existing_queries: Iterable[RetrievalQuery],
        candidate_queries: Iterable[RetrievalQuery],
    ) -> list[RetrievalQuery]:
        existing_keys = {self._query_key(query) for query in existing_queries}
        return [query for query in candidate_queries if self._query_key(query) not in existing_keys]

    def _query_key(self, query: RetrievalQuery) -> tuple[str, str]:
        return (query.intent, " ".join(query.text.lower().split()))

    def _fixture_grounding_enabled(self) -> bool:
        value = os.environ.get("CLIPFORGE_GROUNDING_ENABLE_FIXTURE", "").strip().lower()
        if not value:
            return True
        return value in {"1", "true", "yes", "on"}

    def _legacy_search_candidates(self, search_queries: list[str]) -> list[AgentGroundingCandidate]:
        normalized_queries = [query.strip() for query in search_queries if query and query.strip()]
        if not normalized_queries:
            return []

        aggregated: list[AgentGroundingCandidate] = []
        seen_ids: set[str] = set()

        for query in normalized_queries:
            query_tokens = self._split_query(query)
            for candidate in self._fixture_search(query_tokens, max_results=3):
                grounding_candidate = self._to_grounding_candidate(candidate)
                if grounding_candidate.id in seen_ids:
                    continue
                seen_ids.add(grounding_candidate.id)
                aggregated.append(grounding_candidate)

            if aggregated:
                continue

            if self._remote_grounding_enabled():
                for candidate in self._pexels_search(query_tokens, max_results=3):
                    grounding_candidate = self._to_grounding_candidate(candidate)
                    if grounding_candidate.id in seen_ids:
                        continue
                    seen_ids.add(grounding_candidate.id)
                    aggregated.append(grounding_candidate)

            if aggregated or not self._youtube_grounding_enabled():
                continue

            for candidate in self._youtube_search(query_tokens, max_results=3):
                grounding_candidate = self._to_grounding_candidate(candidate)
                if grounding_candidate.id in seen_ids:
                    continue
                seen_ids.add(grounding_candidate.id)
                aggregated.append(grounding_candidate)

        return aggregated

    def _to_grounding_candidate(self, candidate) -> AgentGroundingCandidate:
        diagnostics = dict(getattr(candidate, "diagnostics", {}) or {})
        product_name = self._infer_product_name(candidate.title)
        feature_hints = self._infer_feature_hints(candidate.title, diagnostics)
        return AgentGroundingCandidate(
            id=f"{candidate.provider}:{candidate.id}",
            title=candidate.title,
            imageUrl=getattr(candidate, "thumbnail", "") or "",
            sourceUrl=candidate.source_url,
            previewUrl=getattr(candidate, "download_url", "") or getattr(candidate, "thumbnail", "") or "",
            sourceType=candidate.provider,
            provider=candidate.provider,
            providerLabel=candidate.provider,
            isOfficial=candidate.provider == "fixture",
            confidence=self._score_confidence(candidate),
            summary=candidate.title,
            diagnostics=diagnostics,
            productName=product_name,
            audience=diagnostics.get("audience", "") or "",
            styleHint=diagnostics.get("styleHint", "") or "",
            featureHints=feature_hints,
        )

    def _score_confidence(self, candidate) -> float:
        score = getattr(candidate, "diagnostics", {}).get("score", 0) if getattr(candidate, "diagnostics", None) else 0
        try:
            return min(1.0, max(0.0, float(score) / 5.0))
        except (TypeError, ValueError):
            return 0.0

    def _extract_product_name(self, text: str) -> str:
        match = re.search(r"给\s*([^\s，。,；;]+)", text)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_audience(self, text: str) -> str:
        patterns = [
            r"目标受众(?:改成|调整为|设为|为)?([^\s，。,；;]+)",
            r"受众(?:改成|调整为|设为|为)?([^\s，。,；;]+)",
            r"面向([^\s，。,；;]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_style_hint(self, text: str) -> str:
        if "产品亮点" in text:
            return "产品亮点"
        if "发布会" in text:
            return "发布会"
        if "科技" in text:
            return "科技感"
        return ""

    def _extract_feature_hints(self, text: str) -> list[str]:
        hints = []
        for keyword in ("亮点", "功能", "品牌", "演示", "特写", "真实素材"):
            if keyword in text:
                hints.append(keyword)
        return hints

    def _build_search_queries(self, product_name: str, audience: str, feature_hints: list[str], text: str) -> list[str]:
        queries: list[str] = []
        if product_name:
            queries.append(product_name)
        if audience and audience not in queries:
            queries.append(audience)
        for hint in feature_hints:
            if hint not in queries:
                queries.append(hint)
        fallback = self._fallback_search_query(text)
        if fallback and fallback not in queries:
            queries.append(fallback)
        return queries[:5]

    def _fallback_search_query(self, text: str) -> str:
        tokens = self._split_query(text)
        return " ".join(tokens[:4])

    def _build_fallback_queries(self, brief: ParsedBrief) -> list[str]:
        queries = [query for query in [brief.product_name, brief.audience, brief.style_hint] if query]
        queries.extend(brief.feature_hints)
        queries.extend(["城市", "咖啡", "海边"])
        return queries

    def _merge_brief(
        self,
        brief: ParsedBrief,
        existing: AgentGroundingSummary | dict[str, Any] | None,
        prompt: str,
    ) -> ParsedBrief:
        existing_summary = self._normalize_existing(existing)
        merged_product_name = brief.product_name or existing_summary.productName
        merged_audience = brief.audience or existing_summary.audience
        merged_style_hint = brief.style_hint or existing_summary.styleHint
        merged_feature_hints = self._merge_unique(existing_summary.featureHints, brief.feature_hints)
        merged_search_queries = self._merge_unique(
            self._build_search_queries(
                merged_product_name,
                merged_audience,
                merged_feature_hints,
                prompt,
            ),
            existing_summary.searchQueries,
        )[:5]

        return ParsedBrief(
            product_name=merged_product_name,
            audience=merged_audience,
            style_hint=merged_style_hint,
            feature_hints=merged_feature_hints,
            search_queries=merged_search_queries,
        )

    def _split_query(self, query: str) -> list[str]:
        return [part for part in re.split(r"[\s,，、/|:：;；]+", query) if part]

    def _infer_product_name(self, title: str) -> str:
        return title.split(" ")[0] if title else ""

    def _infer_feature_hints(self, title: str, diagnostics: dict) -> list[str]:
        hints = [title] if title else []
        matched = diagnostics.get("matchedKeywords") or []
        for keyword in matched:
            if keyword not in hints:
                hints.append(keyword)
        return hints[:5]

    def _remote_grounding_enabled(self) -> bool:
        return os.environ.get("CLIPFORGE_GROUNDING_ENABLE_REMOTE", "").strip().lower() in {"1", "true", "yes", "on"}

    def _youtube_grounding_enabled(self) -> bool:
        return os.environ.get("CLIPFORGE_GROUNDING_ENABLE_YOUTUBE", "").strip().lower() in {"1", "true", "yes", "on"}

    def _normalize_existing(
        self,
        existing: AgentGroundingSummary | dict[str, Any] | None,
    ) -> AgentGroundingSummary:
        if existing is None:
            return AgentGroundingSummary()
        if isinstance(existing, AgentGroundingSummary):
            return existing
        return AgentGroundingSummary.model_validate(existing)

    def _merge_unique(self, *groups: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for item in group:
                normalized = (item or "").strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                merged.append(normalized)
        return merged


grounding_service = GroundingService()

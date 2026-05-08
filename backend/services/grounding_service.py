from dataclasses import dataclass, field
import os
import re
from typing import Any

from backend.models.agent import AgentGroundingCandidate, AgentGroundingSummary
from backend.services.asset_providers.fixture import search_fixture_candidates
from backend.services.asset_providers.pexels import search_pexels_candidates
from backend.services.asset_providers.youtube import search_youtube_candidates


@dataclass(frozen=True)
class ParsedBrief:
    product_name: str = ""
    audience: str = ""
    style_hint: str = ""
    feature_hints: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)


class GroundingService:
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
        candidates = self.search_candidates(brief.search_queries)
        if not candidates:
            candidates = self.search_candidates(self._build_fallback_queries(brief))
        return AgentGroundingSummary(
            status="needs_confirmation" if candidates else "pending_search",
            productName=brief.product_name,
            audience=brief.audience,
            styleHint=brief.style_hint,
            featureHints=brief.feature_hints,
            searchQueries=brief.search_queries,
            candidates=candidates,
            selectedCandidateIds=[],
        )

    def search_candidates(self, search_queries: list[str]) -> list[AgentGroundingCandidate]:
        normalized_queries = [query.strip() for query in search_queries if query and query.strip()]
        if not normalized_queries:
            return []

        aggregated: list[AgentGroundingCandidate] = []
        seen_ids: set[str] = set()

        for query in normalized_queries:
            query_tokens = self._split_query(query)
            for candidate in search_fixture_candidates(query_tokens, max_results=3):
                grounding_candidate = self._to_grounding_candidate(candidate)
                if grounding_candidate.id in seen_ids:
                    continue
                seen_ids.add(grounding_candidate.id)
                aggregated.append(grounding_candidate)

            if aggregated:
                continue

            if self._remote_grounding_enabled():
                for candidate in search_pexels_candidates(query_tokens, max_results=3):
                    grounding_candidate = self._to_grounding_candidate(candidate)
                    if grounding_candidate.id in seen_ids:
                        continue
                    seen_ids.add(grounding_candidate.id)
                    aggregated.append(grounding_candidate)

            if aggregated or not self._youtube_grounding_enabled():
                continue

            for candidate in search_youtube_candidates(query_tokens, max_results=3):
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

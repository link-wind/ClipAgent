# Brief Retrieval Query Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a LangChain-driven `RetrievalQueryPack` layer that turns a user brief into provider-aware grounding queries, while preserving the current `/workspace` confirmation flow and deterministic fallback behavior.

**Architecture:** Introduce a dedicated retrieval-planning contract and runtime, then refactor `GroundingService` to consume that contract instead of generating flat queries directly. Keep the existing session orchestration and API surface stable by projecting the richer query plan back into `AgentGroundingSummary.searchQueries`, and fall back to the current heuristic path whenever retrieval planning fails or returns nothing useful.

**Tech Stack:** FastAPI, Pydantic v2, LangChain, langchain-openai, SQLAlchemy, unittest

---

## File Structure

- Create: `backend/services/grounding_planner_models.py`
  - Retrieval-planning contract layer: `RetrievalQuery` and `RetrievalQueryPack`
- Create: `backend/services/grounding_planner_runtime.py`
  - LangChain runtime for `build_query_pack(...)`
- Modify: `backend/models/agent.py`
  - Extend `AgentGroundingSummary` with `assumptions` and `queryPlan`
- Modify: `backend/services/grounding_service.py`
  - Use the new runtime lazily, execute provider-aware searches, and preserve deterministic fallback
- Modify: `backend/services/agent_read_service.py`
  - Rehydrate `assumptions` and `queryPlan` into API responses
- Create: `tests/test_grounding_planner_runtime.py`
  - Focused runtime and contract tests for `RetrievalQueryPack`
- Create: `tests/test_grounding_service.py`
  - Focused `GroundingService` integration tests with fake provider search functions
- Modify: `tests/test_agent_persistence.py`
  - Response-contract and session-behavior compatibility checks
- Modify: `tests/test_agent_api_p0.py`
  - API-level regression for the enriched grounding payload

### Task 1: Add the retrieval-planning contract and grounding response fields

**Files:**
- Create: `backend/services/grounding_planner_models.py`
- Modify: `backend/models/agent.py`
- Create: `tests/test_grounding_planner_runtime.py`
- Modify: `tests/test_agent_persistence.py`

- [ ] **Step 1: Write the failing contract tests**

Create `tests/test_grounding_planner_runtime.py` with this initial test:

```python
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
```

Add this test to `tests/test_agent_persistence.py` inside `AgentPersistenceModelTests`:

```python
    def test_grounding_summary_supports_assumptions_and_query_plan_defaults(self):
        from backend.models.agent import AgentGroundingSummary

        summary = AgentGroundingSummary()

        self.assertEqual(summary.assumptions, [])
        self.assertEqual(summary.queryPlan, [])
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_grounding_planner_runtime tests.test_agent_persistence.AgentPersistenceModelTests.test_grounding_summary_supports_assumptions_and_query_plan_defaults -v
```

Expected: FAIL because `backend/services/grounding_planner_models.py` does not exist and `AgentGroundingSummary` does not expose the new fields.

- [ ] **Step 3: Add the new contract file and response fields**

Create `backend/services/grounding_planner_models.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field


ProviderName = Literal["fixture", "youtube", "pexels"]
QueryIntent = Literal[
    "brand_exact",
    "product_demo",
    "feature_workflow",
    "stock_fallback",
]


class RetrievalQuery(BaseModel):
    text: str
    intent: QueryIntent
    providers: list[ProviderName] = Field(default_factory=list)
    priority: int = 100


class RetrievalQueryPack(BaseModel):
    productName: str = ""
    audience: str = ""
    styleHint: str = ""
    featureHints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    queries: list[RetrievalQuery] = Field(default_factory=list)
```

Update `backend/models/agent.py` by extending `AgentGroundingSummary`:

```python
class AgentGroundingSummary(BaseModel):
    status: GroundingStatus = "pending_search"
    productName: str = ""
    audience: str = ""
    styleHint: str = ""
    featureHints: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    searchQueries: List[str] = Field(default_factory=list)
    queryPlan: List[Dict[str, Any]] = Field(default_factory=list)
    candidates: List[AgentGroundingCandidate] = Field(default_factory=list)
    selectedCandidateIds: List[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_grounding_planner_runtime tests.test_agent_persistence.AgentPersistenceModelTests.test_grounding_summary_supports_assumptions_and_query_plan_defaults -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/grounding_planner_models.py backend/models/agent.py tests/test_grounding_planner_runtime.py tests/test_agent_persistence.py
git commit -m "feat: add retrieval query pack contract"
```

### Task 2: Implement the LangChain grounding planner runtime

**Files:**
- Create: `backend/services/grounding_planner_runtime.py`
- Modify: `tests/test_grounding_planner_runtime.py`

- [ ] **Step 1: Expand the runtime tests**

Append these fakes and tests to `tests/test_grounding_planner_runtime.py`:

```python
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
```

```python
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
```

```python
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
                    }
                ],
            )
        )

        runtime = GroundingPlannerRuntime(model_name="gpt-4o-mini", llm=fake_llm)

        with self.assertRaisesRegex(ValueError, "query text"):
            runtime.build_query_pack("给 Notion AI 做一个产品介绍视频")
```

```python
    def test_runtime_bubbles_up_model_failures(self):
        from backend.services.grounding_planner_runtime import GroundingPlannerRuntime

        runtime = GroundingPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=_FakeChatModel(error=RuntimeError("Grounding planning failed")),
        )

        with self.assertRaisesRegex(RuntimeError, "Grounding planning failed"):
            runtime.build_query_pack("给 Notion AI 做一个产品介绍视频")
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_grounding_planner_runtime -v
```

Expected: FAIL because `backend/services/grounding_planner_runtime.py` does not exist yet.

- [ ] **Step 3: Implement the minimal runtime**

Create `backend/services/grounding_planner_runtime.py`:

```python
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.services.grounding_planner_models import RetrievalQueryPack


GROUNDING_QUERY_PLANNER_SYSTEM_PROMPT = """
You are a retrieval planner for product-intro video grounding.
Return a RetrievalQueryPack.
Include 2 to 5 queries.
Use short English retrieval phrases.
Use youtube for brand_exact or product_demo queries.
Use pexels for feature_workflow or stock_fallback queries.
""".strip()


class GroundingPlannerRuntime:
    def __init__(self, model_name: str, *, llm=None):
        self.model_name = model_name
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0)

    def _planner_runnable(self):
        return self.llm.with_structured_output(RetrievalQueryPack)

    def build_query_pack(self, brief: str) -> RetrievalQueryPack:
        result = self._planner_runnable().invoke(
            [
                SystemMessage(content=GROUNDING_QUERY_PLANNER_SYSTEM_PROMPT),
                HumanMessage(content=brief.strip() or "product intro video"),
            ]
        )
        normalized = self._normalize_result(result)
        self._validate_result(normalized)
        return normalized

    def _normalize_result(self, result: RetrievalQueryPack) -> RetrievalQueryPack:
        return result.model_copy(
            update={
                "productName": result.productName.strip(),
                "audience": result.audience.strip(),
                "styleHint": result.styleHint.strip(),
                "featureHints": [item.strip() for item in result.featureHints if item.strip()],
                "assumptions": [item.strip() for item in result.assumptions if item.strip()],
                "queries": [
                    query.model_copy(
                        update={
                            "text": " ".join(query.text.split()),
                            "providers": [provider for provider in query.providers if provider],
                        }
                    )
                    for query in sorted(result.queries, key=lambda item: item.priority)
                ],
            }
        )

    def _validate_result(self, result: RetrievalQueryPack) -> None:
        if not result.queries:
            raise ValueError("retrieval query pack must include at least one query")
        for query in result.queries:
            if not query.text:
                raise ValueError("retrieval query text is required")
            if not query.providers:
                raise ValueError("retrieval query providers are required")
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_grounding_planner_runtime -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/grounding_planner_runtime.py tests/test_grounding_planner_runtime.py
git commit -m "feat: add grounding planner runtime"
```

### Task 3: Refactor `GroundingService` to use provider-aware query plans with deterministic fallback

**Files:**
- Modify: `backend/services/grounding_service.py`
- Create: `tests/test_grounding_service.py`

- [ ] **Step 1: Write the failing service tests**

Create `tests/test_grounding_service.py`:

```python
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
                        }
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
        self.assertEqual(summary.searchQueries, ["notion ai demo"])
        self.assertEqual(summary.queryPlan[0]["intent"], "product_demo")
        self.assertEqual(summary.candidates[0].id, "youtube:yt-1")
        self.assertIn(("youtube", ("notion", "ai", "demo"), 3), calls)
```

```python
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
```

```python
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
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_grounding_service -v
```

Expected: FAIL because `GroundingService` does not yet accept injected runtime/provider functions and does not expose `search_candidates_for_query_plan(...)`.

- [ ] **Step 3: Refactor `GroundingService`**

Update `backend/services/grounding_service.py` to:

```python
from dataclasses import dataclass, field
import os
import re
from typing import Any

from backend.config import get_settings
from backend.models.agent import AgentGroundingCandidate, AgentGroundingSummary
from backend.services.asset_providers.fixture import search_fixture_candidates
from backend.services.asset_providers.pexels import search_pexels_candidates
from backend.services.asset_providers.youtube import search_youtube_candidates
from backend.services.grounding_planner_models import RetrievalQuery, RetrievalQueryPack
from backend.services.grounding_planner_runtime import GroundingPlannerRuntime
```

```python
class GroundingService:
    def __init__(
        self,
        *,
        retrieval_runtime=None,
        fixture_search=search_fixture_candidates,
        pexels_search=search_pexels_candidates,
        youtube_search=search_youtube_candidates,
    ):
        self.retrieval_runtime = retrieval_runtime
        self.fixture_search = fixture_search
        self.pexels_search = pexels_search
        self.youtube_search = youtube_search

    def _get_retrieval_runtime(self):
        if self.retrieval_runtime is not None:
            return self.retrieval_runtime
        settings = get_settings()
        self.retrieval_runtime = GroundingPlannerRuntime(model_name=settings.planner_model)
        return self.retrieval_runtime
```

```python
    def build_grounding_summary(
        self,
        prompt: str,
        existing: AgentGroundingSummary | dict[str, Any] | None = None,
    ) -> AgentGroundingSummary:
        existing_summary = self._normalize_existing(existing)
        try:
            query_pack = self._merge_query_pack(
                self._get_retrieval_runtime().build_query_pack(prompt),
                existing_summary,
                prompt,
            )
        except Exception:
            query_pack = self._fallback_query_pack(prompt, existing_summary)

        candidates = self.search_candidates_for_query_plan(query_pack.queries)
        if not candidates:
            fallback_pack = self._fallback_query_pack(prompt, existing_summary)
            fallback_queries = self._query_diff(query_pack.queries, fallback_pack.queries)
            if fallback_queries:
                query_pack = query_pack.model_copy(
                    update={
                        "assumptions": self._merge_unique(
                            query_pack.assumptions,
                            ["deterministic fallback queries added after sparse retrieval results"],
                        ),
                        "queries": [*query_pack.queries, *fallback_queries],
                    }
                )
                candidates = self.search_candidates_for_query_plan(query_pack.queries)

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
```

```python
    def search_candidates_for_query_plan(
        self,
        query_plan: list[RetrievalQuery] | list[dict[str, Any]],
    ) -> list[AgentGroundingCandidate]:
        normalized_queries = [RetrievalQuery.model_validate(item) for item in query_plan]
        aggregated: list[AgentGroundingCandidate] = []
        seen_ids: set[str] = set()

        for query in sorted(normalized_queries, key=lambda item: item.priority):
            tokens = self._split_query(query.text)
            for provider in self._provider_order_for_query(query):
                for candidate in self._search_with_provider(provider, tokens):
                    grounding_candidate = self._to_grounding_candidate(candidate)
                    if grounding_candidate.id in seen_ids:
                        continue
                    seen_ids.add(grounding_candidate.id)
                    aggregated.append(grounding_candidate)
                if aggregated:
                    break

        return aggregated
```

```python
    def _provider_order_for_query(self, query: RetrievalQuery) -> list[str]:
        ordered: list[str] = []
        if self._fixture_grounding_enabled():
            ordered.append("fixture")
        for provider in query.providers:
            if provider not in ordered:
                ordered.append(provider)
        return ordered

    def _search_with_provider(self, provider: str, tokens: list[str]):
        if provider == "fixture":
            return self.fixture_search(tokens, max_results=3)
        if provider == "pexels" and self._remote_grounding_enabled():
            return self.pexels_search(tokens, max_results=3)
        if provider == "youtube" and self._youtube_grounding_enabled():
            return self.youtube_search(tokens, max_results=3)
        return []
```

```python
    def _fallback_query_pack(
        self,
        prompt: str,
        existing_summary: AgentGroundingSummary,
    ) -> RetrievalQueryPack:
        brief = self._merge_brief(self.parse_brief(prompt), existing_summary, prompt)
        queries: list[RetrievalQuery] = []
        ordered = self._build_search_queries(brief.product_name, brief.audience, brief.feature_hints, prompt)
        for index, text in enumerate(ordered):
            queries.append(
                RetrievalQuery(
                    text=text,
                    intent="brand_exact" if index == 0 else "stock_fallback",
                    providers=["youtube", "pexels"],
                    priority=(index + 1) * 10,
                )
            )
        return RetrievalQueryPack(
            productName=brief.product_name,
            audience=brief.audience,
            styleHint=brief.style_hint,
            featureHints=brief.feature_hints,
            assumptions=["deterministic fallback query pack"],
            queries=queries,
        )
```

```python
    def _merge_query_pack(
        self,
        pack: RetrievalQueryPack,
        existing_summary: AgentGroundingSummary,
        prompt: str,
    ) -> RetrievalQueryPack:
        fallback = self._fallback_query_pack(prompt, existing_summary)
        merged_queries = self._merge_query_objects(pack.queries, existing_summary.queryPlan, fallback.queries)
        return RetrievalQueryPack(
            productName=pack.productName or existing_summary.productName or fallback.productName,
            audience=pack.audience or existing_summary.audience or fallback.audience,
            styleHint=pack.styleHint or existing_summary.styleHint or fallback.styleHint,
            featureHints=self._merge_unique(existing_summary.featureHints, pack.featureHints, fallback.featureHints),
            assumptions=self._merge_unique(existing_summary.assumptions, pack.assumptions),
            queries=merged_queries[:5],
        )
```

Also add:

```python
    def _merge_query_objects(self, *groups):
        merged: list[RetrievalQuery] = []
        seen: set[str] = set()
        for group in groups:
            for item in group:
                query = item if isinstance(item, RetrievalQuery) else RetrievalQuery.model_validate(item)
                normalized = " ".join(query.text.split()).strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                merged.append(query.model_copy(update={"text": normalized}))
        return merged

    def _query_diff(self, current_queries, fallback_queries):
        current = {" ".join(RetrievalQuery.model_validate(item).text.split()) for item in current_queries}
        return [
            RetrievalQuery.model_validate(item)
            for item in fallback_queries
            if " ".join(RetrievalQuery.model_validate(item).text.split()) not in current
        ]

    def _fixture_grounding_enabled(self) -> bool:
        return os.environ.get("FIXTURE_PROVIDER_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_grounding_service -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/grounding_service.py tests/test_grounding_service.py
git commit -m "feat: make grounding queries provider aware"
```

### Task 4: Preserve API compatibility and session behavior with the richer grounding payload

**Files:**
- Modify: `backend/services/agent_read_service.py`
- Modify: `tests/test_agent_api_p0.py`
- Modify: `tests/test_agent_persistence.py`

- [ ] **Step 1: Add the failing compatibility regressions**

Add this test to `tests/test_agent_api_p0.py` inside `AgentApiP0ContractTests`:

```python
    def test_grounding_api_response_includes_query_plan_and_assumptions(self):
        async def _run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                create_response = await client.post("/api/agent/sessions", json={})
                self.assertEqual(create_response.status_code, 200)
                created = create_response.json()

                message_response = await client.post(
                    f"/api/agent/sessions/{created['id']}/messages",
                    json={"message": "给 Notion AI 做一个 30 秒产品亮点视频"},
                )
                self.assertEqual(message_response.status_code, 200)
                awaiting = message_response.json()

                self.assertIn("assumptions", awaiting["grounding"])
                self.assertIn("queryPlan", awaiting["grounding"])
                self.assertTrue(awaiting["grounding"]["searchQueries"])
                self.assertEqual(
                    [item["text"] for item in awaiting["grounding"]["queryPlan"]],
                    awaiting["grounding"]["searchQueries"],
                )

        import asyncio

        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module,
            "read_service",
            self.read_service,
        ):
            asyncio.run(_run())
```

Add this assertion block to `tests/test_agent_persistence.py` inside `test_add_user_message_persists_message_and_merges_grounding_context_until_confirmed`:

```python
        self.assertIsInstance(updated.grounding.assumptions, list)
        self.assertTrue(updated.grounding.queryPlan)
        self.assertEqual(
            [item["text"] for item in updated.grounding.queryPlan],
            updated.grounding.searchQueries,
        )
```

- [ ] **Step 2: Run the focused regressions and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_grounding_api_response_includes_query_plan_and_assumptions tests.test_agent_persistence.SessionServiceBehaviorTests.test_add_user_message_persists_message_and_merges_grounding_context_until_confirmed -v
```

Expected: FAIL because the API response does not yet expose the new grounding fields end to end.

- [ ] **Step 3: Make the compatibility path explicit if needed**

Update `backend/services/agent_read_service.py` inside `_build_grounding_response(...)` so the richer grounding payload survives the read-model projection:

```python
        return AgentGroundingSummary(
            status=session_record.grounding_status or grounding_json.get("status", "pending_search"),
            productName=grounding_json.get("productName", "") or "",
            audience=grounding_json.get("audience", "") or "",
            styleHint=grounding_json.get("styleHint", "") or "",
            featureHints=grounding_json.get("featureHints", []) or [],
            assumptions=grounding_json.get("assumptions", []) or [],
            searchQueries=grounding_json.get("searchQueries", []) or [],
            queryPlan=grounding_json.get("queryPlan", []) or [],
            candidates=[
                AgentGroundingCandidate.model_validate(candidate)
                for candidate in grounding_json.get("candidates", []) or []
            ],
            selectedCandidateIds=session_record.selected_candidate_ids_json or grounding_json.get(
                "selectedCandidateIds",
                [],
            )
            or [],
        )
```

This task should not introduce new production files beyond the ones already listed above. Only tighten the response projection until the tests pass.

- [ ] **Step 4: Run the compatibility regressions and then the full focused backend suite**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_grounding_planner_runtime tests.test_grounding_service tests.test_agent_api_p0 tests.test_agent_persistence tests.test_planner_runtime -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_agent_api_p0.py tests/test_agent_persistence.py
git commit -m "test: cover retrieval query pack grounding flow"
```

## Self-Review

- Spec coverage:
  - LangChain `RetrievalQueryPack` contract: Tasks 1-2
  - provider-aware query execution: Task 3
  - deterministic fallback: Task 3
  - grounding summary `assumptions` and `queryPlan`: Tasks 1, 3, 4
  - API compatibility through `searchQueries`: Tasks 3-4
- Placeholder scan:
  - no `TODO` / `TBD`
  - every task lists concrete files, code, commands, and commit steps
  - the only conditional step is Task 4 Step 3, but it still pins the exact expected payload and forbids scope creep into new files
- Type consistency:
  - `RetrievalQueryPack`, `RetrievalQuery`, `assumptions`, and `queryPlan` are used consistently across the contract, runtime, service, and API tasks

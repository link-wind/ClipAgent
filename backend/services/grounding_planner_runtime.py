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

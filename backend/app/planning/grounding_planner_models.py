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

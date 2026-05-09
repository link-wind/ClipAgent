from typing import Literal

from pydantic import BaseModel, Field


class BriefUnderstanding(BaseModel):
    productName: str = ""
    audience: str = ""
    styleHint: str = ""
    featureHints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class AgentScene(BaseModel):
    id: int
    purpose: str = ""
    description: str
    visualIntent: str = ""
    searchIntent: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    groundingCandidateIds: list[str] = Field(default_factory=list)
    duration: float = 6.0
    fallbackPolicy: str = ""
    status: Literal["draft", "grounded", "blocked", "ready_for_execution"] = "draft"


class AgentPlan(BaseModel):
    title: str
    goal: str
    summary: str
    understanding: BriefUnderstanding = Field(default_factory=BriefUnderstanding)
    constraints: dict = Field(default_factory=dict)
    strategy: dict = Field(default_factory=dict)
    scenes: list[AgentScene] = Field(default_factory=list)
    grounding: dict = Field(default_factory=dict)
    openIssues: list[dict] = Field(default_factory=list)
    replanHistory: list[dict] = Field(default_factory=list)


class ExecutionScene(BaseModel):
    id: int
    description: str
    keywords: list[str] = Field(default_factory=list)
    searchQuery: str
    duration: float
    groundingCandidateIds: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    title: str
    targetDuration: float
    style: str
    scenes: list[ExecutionScene] = Field(default_factory=list)


class AgentObservation(BaseModel):
    id: str
    sessionId: str
    relatedPlanVersion: int | None = None
    observationType: str
    payload: dict = Field(default_factory=dict)
    summary: str = ""
    createdAt: str


class GroundingFeedback(BaseModel):
    productName: str = ""
    audience: str = ""
    styleHint: str = ""
    featureHints: list[str] = Field(default_factory=list)
    selectedCandidateIds: list[str] = Field(default_factory=list)
    candidates: list[dict] = Field(default_factory=list)


class CandidateConfirmationFeedback(BaseModel):
    selectedCandidateIds: list[str] = Field(default_factory=list)
    confirmationSource: Literal["user_select", "api_confirm"] = "api_confirm"

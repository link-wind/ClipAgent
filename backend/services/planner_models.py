from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


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


class UserRevisionFeedback(BaseModel):
    message: str
    sceneKeywordUpdates: dict[int, list[str]] = Field(default_factory=dict)
    revisionSource: Literal["user_message", "api_message"] = "user_message"


class SearchExecutionFeedback(BaseModel):
    failedSceneIds: list[int] = Field(default_factory=list)
    failureReason: str = ""
    failureCategory: str = ""
    primaryProvider: str = ""
    providerDiagnostics: list[dict[str, Any]] = Field(default_factory=list)
    sceneDiagnostics: list[dict[str, Any]] = Field(default_factory=list)
    retryStrategyHint: str = ""
    retryable: bool = True
    feedbackSource: Literal["worker_failure", "api_retry"] = "worker_failure"

    @model_validator(mode="after")
    def hydrate_failure_reason_from_structured_diagnostics(self) -> "SearchExecutionFeedback":
        if self.failureCategory != "platform_blocked":
            return self

        provider_messages = [
            str(diagnostic.get("message", "")).strip()
            for diagnostic in self.providerDiagnostics
            if isinstance(diagnostic, dict)
        ]
        provider_messages = [message for message in provider_messages if message]
        if provider_messages:
            self.failureReason = "\n".join(provider_messages)

        return self


class RenderReadinessFeedback(BaseModel):
    missingSceneIds: list[int] = Field(default_factory=list)
    summary: str = ""
    retryable: bool = True

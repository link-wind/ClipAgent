from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    IDLE = "idle"
    QUEUED = "queued"
    PLANNING = "planning"
    PLAN_READY = "plan_ready"
    SEARCHING = "searching"
    DOWNLOADING = "downloading"
    RENDERING = "rendering"
    DONE = "done"
    FAILED = "failed"


class AgentMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    createdAt: str


class PlanScene(BaseModel):
    id: int
    description: str
    keywords: List[str] = Field(default_factory=list)
    duration: float = 6.0
    searchQuery: str


class EditPlan(BaseModel):
    title: str
    targetDuration: float = 30.0
    style: str = "cinematic"
    scenes: List[PlanScene]


class ClipInfo(BaseModel):
    sceneId: int
    sourceUrl: str
    localPath: str
    publicUrl: str
    caption: str = ""
    startTime: float = 0.0
    duration: float = 6.0
    sourceDuration: float = 0.0
    trimStart: float = 0.0
    trimDuration: float = 6.0


class AgentError(BaseModel):
    message: str
    retryableStep: Optional[str] = None


AgentStepId = Literal[
    "understand_request",
    "extract_requirements",
    "generate_options",
    "finalize_plan",
    "create_task",
    "search_assets",
    "prepare_assets",
    "render_video",
]

AgentStepStatus = Literal["pending", "running", "succeeded", "failed", "skipped"]
GroundingStatus = Literal["pending_search", "needs_confirmation", "confirmed"]
AgentDiagnosticSeverity = Literal["info", "warning", "error"]
AgentDiagnosticPhase = Literal["planning", "search_assets", "prepare_assets", "render_video", "unknown"]
AgentDiagnosticCategory = Literal[
    "no_inventory",
    "provider_blocked",
    "download_failed",
    "render_failed",
    "planning_failed",
    "unknown",
]


class AgentStepError(BaseModel):
    message: str
    retryable: bool = False
    retryableStep: Optional[AgentStepId] = None


class AgentStep(BaseModel):
    id: AgentStepId
    title: str
    description: str
    status: AgentStepStatus = "pending"
    progress: float = 0.0
    summary: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[AgentStepError] = None
    startedAt: Optional[str] = None
    finishedAt: Optional[str] = None


class AgentEvent(BaseModel):
    id: str
    eventType: str
    step: Optional[str] = None
    progress: Optional[float] = None
    message: Optional[str] = None
    payload: dict = Field(default_factory=dict)
    createdAt: str


class AgentDiagnostic(BaseModel):
    phase: AgentDiagnosticPhase
    category: AgentDiagnosticCategory
    title: str
    message: str
    primaryProvider: Optional[str] = None
    failedSceneIds: List[int] = Field(default_factory=list)
    providerDiagnostics: List[Dict[str, Any]] = Field(default_factory=list)
    sceneDiagnostics: List[Dict[str, Any]] = Field(default_factory=list)
    retryStrategyHint: Optional[str] = None
    repairPrompt: str = ""
    severity: AgentDiagnosticSeverity = "error"


class AgentGroundingCandidate(BaseModel):
    id: str
    title: str
    imageUrl: str
    sourceUrl: str
    previewUrl: str = ""
    sourceType: str
    provider: str
    providerLabel: str
    isOfficial: bool = False
    confidence: float = 0.0
    summary: str = ""
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    productName: str
    audience: str
    styleHint: str
    featureHints: List[str] = Field(default_factory=list)


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


class AgentSession(BaseModel):
    id: str
    status: AgentStatus = AgentStatus.IDLE
    messages: List[AgentMessage] = Field(default_factory=list)
    plan: Optional[EditPlan] = None
    currentPlanVersion: int | None = None
    clips: List[ClipInfo] = Field(default_factory=list)
    events: List[AgentEvent] = Field(default_factory=list)
    steps: List[AgentStep] = Field(default_factory=list)
    videoUrl: Optional[str] = None
    activeJobId: Optional[str] = None
    grounding: Optional[AgentGroundingSummary] = None
    diagnostic: Optional[AgentDiagnostic] = None
    plannerTrace: Dict[str, Any] | None = None
    error: Optional[AgentError] = None
    progress: float = 0.0
    currentStep: str = ""


class AgentTaskSummary(BaseModel):
    id: str
    sessionId: str
    title: str
    status: str
    progress: float = 0.0
    currentStep: str = ""
    currentStepId: Optional[AgentStepId] = None
    createdAt: str
    updatedAt: str


class AgentTaskDetail(AgentTaskSummary):
    events: List[AgentEvent] = Field(default_factory=list)
    clips: List[ClipInfo] = Field(default_factory=list)
    steps: List[AgentStep] = Field(default_factory=list)
    error: Optional[AgentError] = None
    videoUrl: Optional[str] = None
    diagnostic: Optional[AgentDiagnostic] = None


class AgentDashboardSummary(BaseModel):
    totalSessions: int = 0
    activeTasks: int = 0
    completedTasks: int = 0
    failedTasks: int = 0
    recentTasks: List[AgentTaskSummary] = Field(default_factory=list)

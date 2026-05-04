from enum import Enum
from typing import List, Literal, Optional

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


class AgentTaskStatus(str, Enum):
    QUEUED = "queued"
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


LEGACY_AGENT_TASK_STATUS_MAP: dict[str, AgentTaskStatus] = {
    "done": AgentTaskStatus.SUCCEEDED,
}


def normalize_agent_task_status(status: str) -> AgentTaskStatus:
    normalized = status.strip().lower()
    legacy_status = LEGACY_AGENT_TASK_STATUS_MAP.get(normalized)
    if legacy_status is not None:
        return legacy_status

    try:
        return AgentTaskStatus(normalized)
    except ValueError:
        return AgentTaskStatus.FAILED


class AgentEvent(BaseModel):
    id: str
    eventType: str
    step: Optional[str] = None
    progress: Optional[float] = None
    message: Optional[str] = None
    payload: dict = Field(default_factory=dict)
    createdAt: str


class AgentSession(BaseModel):
    id: str
    status: AgentStatus = AgentStatus.IDLE
    messages: List[AgentMessage] = Field(default_factory=list)
    plan: Optional[EditPlan] = None
    clips: List[ClipInfo] = Field(default_factory=list)
    events: List[AgentEvent] = Field(default_factory=list)
    videoUrl: Optional[str] = None
    activeJobId: Optional[str] = None
    error: Optional[AgentError] = None
    progress: float = 0.0
    currentStep: str = ""


class AgentTaskSummary(BaseModel):
    id: str
    sessionId: str
    title: str
    status: AgentTaskStatus
    progress: float = 0.0
    currentStep: str = ""
    createdAt: str
    updatedAt: str


class AgentTaskDetail(AgentTaskSummary):
    events: List[AgentEvent] = Field(default_factory=list)
    clips: List[ClipInfo] = Field(default_factory=list)
    error: Optional[AgentError] = None
    videoUrl: Optional[str] = None


class AgentDashboardSummary(BaseModel):
    totalSessions: int = 0
    activeTasks: int = 0
    completedTasks: int = 0
    failedTasks: int = 0
    recentTasks: List[AgentTaskSummary] = Field(default_factory=list)

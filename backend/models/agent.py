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
    startTime: float = 0.0
    duration: float = 6.0
    sourceDuration: float = 0.0
    trimStart: float = 0.0
    trimDuration: float = 6.0


class AgentError(BaseModel):
    message: str
    retryableStep: Optional[str] = None


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

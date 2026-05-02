from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel


class TaskStatus(str, Enum):
    IDLE = "idle"
    ANALYZING = "analyzing"
    SCENES_READY = "scenes_ready"
    SEARCHING = "searching"
    RENDERING = "rendering"
    DONE = "done"
    FAILED = "failed"


class Scene(BaseModel):
    id: int
    description: str
    keywords: List[str]


class AnalyzeRequest(BaseModel):
    script: str


class AnalyzeResponse(BaseModel):
    scenes: List[Scene]


class SearchRequest(BaseModel):
    scenes: List[Scene]


class SearchResponse(BaseModel):
    taskId: str
    status: TaskStatus


class ClipInfo(BaseModel):
    sceneId: int
    videoUrl: str
    startTime: float
    duration: float


class RenderRequest(BaseModel):
    taskId: str
    clips: List[ClipInfo]


class RenderResponse(BaseModel):
    taskId: str
    status: TaskStatus


class TaskStatusResponse(BaseModel):
    status: TaskStatus
    progress: float
    currentStep: str
    videoUrl: Optional[str] = None


class TaskResultResponse(BaseModel):
    taskId: str
    clips: List[Dict]

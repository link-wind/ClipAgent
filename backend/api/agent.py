import openai
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.agent.session_use_cases import AgentReadService, AgentSessionService
from backend.app.execution.job_use_cases import AgentExecutionService, AgentTaskReadService
from backend.db import SessionLocal
from backend.models.agent import AgentDashboardSummary, AgentEvent, AgentSession, AgentTaskDetail, AgentTaskSummary
from backend.services.agent_service import agent_service


router = APIRouter()
session_service = AgentSessionService(session_factory=SessionLocal)
read_service = AgentReadService(session_factory=SessionLocal)
execution_service = AgentExecutionService(session_factory=SessionLocal)
task_read_service = AgentTaskReadService(session_factory=SessionLocal)


def _translate_planner_error(exc: Exception) -> HTTPException:
    if isinstance(exc, openai.AuthenticationError):
        return HTTPException(status_code=401, detail="OpenAI 兼容服务鉴权失败，请检查 API Key 或 Base URL。")
    if isinstance(exc, openai.RateLimitError):
        return HTTPException(status_code=429, detail="OpenAI 兼容服务限流，请稍后重试。")
    if isinstance(exc, openai.APITimeoutError):
        return HTTPException(status_code=504, detail="OpenAI 兼容服务响应超时，请稍后重试。")
    if isinstance(exc, openai.APIConnectionError):
        return HTTPException(status_code=502, detail="无法连接到 OpenAI 兼容服务，请检查网络或 Base URL。")
    if isinstance(exc, openai.APIStatusError):
        status_code = getattr(exc, "status_code", None) or 502
        if status_code >= 500:
            return HTTPException(status_code=503, detail="OpenAI 兼容服务暂时不可用，请稍后重试。")
        if status_code == 400:
            return HTTPException(status_code=400, detail="OpenAI 兼容服务请求参数无效，请检查模型或输入配置。")
        return HTTPException(status_code=status_code, detail="OpenAI 兼容服务请求失败，请检查当前配置。")
    raise exc


class SessionCreateRequest(BaseModel):
    message: str | None = None


class MessageRequest(BaseModel):
    message: str


class GroundingConfirmRequest(BaseModel):
    candidateIds: list[str]


@router.post("/sessions", response_model=AgentSession)
async def create_session(request: SessionCreateRequest):
    try:
        session = session_service.create_session(request.message)
        return agent_service.sync_session(session)
    except HTTPException:
        raise
    except Exception as exc:
        raise _translate_planner_error(exc)


@router.get("/sessions/{session_id}", response_model=AgentSession)
async def get_session(session_id: str):
    try:
        session = session_service.get_session(session_id)
        return agent_service.sync_session(session)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions/{session_id}/messages", response_model=AgentSession)
async def add_message(session_id: str, request: MessageRequest):
    try:
        session = session_service.add_user_message(session_id, request.message)
        return agent_service.sync_session(session)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise _translate_planner_error(exc)


@router.post("/sessions/{session_id}/grounding/confirm", response_model=AgentSession)
async def confirm_grounding_candidates(session_id: str, request: GroundingConfirmRequest):
    try:
        session = session_service.confirm_grounding_candidates(session_id, request.candidateIds)
        return agent_service.sync_session(session)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise _translate_planner_error(exc)


@router.post("/sessions/{session_id}/confirm", response_model=AgentSession)
async def confirm_session(session_id: str):
    try:
        session = execution_service.confirm_session(session_id)
        return agent_service.sync_session(session)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/sessions/{session_id}/events", response_model=list[AgentEvent])
async def get_session_events(session_id: str):
    try:
        return read_service.read_events(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/dashboard", response_model=AgentDashboardSummary)
async def get_dashboard():
    return task_read_service.read_dashboard()


@router.get("/tasks", response_model=list[AgentTaskSummary])
async def list_tasks():
    return task_read_service.list_tasks()


@router.get("/tasks/{job_id}", response_model=AgentTaskDetail)
async def get_task(job_id: str):
    try:
        return task_read_service.read_task(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db import SessionLocal
from backend.models.agent import AgentEvent, AgentSession
from backend.services.agent_execution_service import AgentExecutionService
from backend.services.agent_read_service import AgentReadService
from backend.services.agent_service import agent_service
from backend.services.agent_session_service import AgentSessionService


router = APIRouter()
session_service = AgentSessionService(session_factory=SessionLocal)
read_service = AgentReadService(session_factory=SessionLocal)
execution_service = AgentExecutionService(session_factory=SessionLocal)


class SessionCreateRequest(BaseModel):
    message: str | None = None


class MessageRequest(BaseModel):
    message: str


@router.post("/sessions", response_model=AgentSession)
async def create_session(request: SessionCreateRequest):
    session = session_service.create_session(request.message)
    return agent_service.sync_session(session)


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

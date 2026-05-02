import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.models.agent import AgentSession
from backend.services.agent_service import agent_service


router = APIRouter()


class SessionCreateRequest(BaseModel):
    message: str | None = None


class MessageRequest(BaseModel):
    message: str


@router.post("/sessions", response_model=AgentSession)
async def create_session(request: SessionCreateRequest):
    return agent_service.create_session(request.message)


@router.get("/sessions/{session_id}", response_model=AgentSession)
async def get_session(session_id: str):
    try:
        return agent_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions/{session_id}/messages", response_model=AgentSession)
async def add_message(session_id: str, request: MessageRequest):
    try:
        return agent_service.add_user_message(session_id, request.message)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/sessions/{session_id}/confirm", response_model=AgentSession)
async def confirm_session(session_id: str):
    try:
        session = agent_service.confirm_session(session_id)
        asyncio.create_task(agent_service.run_confirmed_session(session_id))
        return session
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

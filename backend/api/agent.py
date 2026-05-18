import asyncio

import openai
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.app.agent.session_use_cases import AgentReadService, AgentSessionService
from backend.app.agent.stream_service import AgentStreamService, format_sse_event
from backend.app.execution.job_use_cases import AgentExecutionService, AgentTaskReadService
from backend.db import SessionLocal
from backend.db.repositories import AgentRunRepository, AgentSessionRepository, AgentTraceEventRepository
from backend.models.agent import (
    AgentDashboardSummary,
    AgentEvent,
    AgentRunSummary,
    AgentSession,
    AgentTaskDetail,
    AgentTaskSummary,
    AgentTraceEvent,
)
from backend.runtime.agent_runtime import build_agent_runtime
from backend.services.agent_service import agent_service
from backend.services.agent_run_service import ActiveOperationConflict


router = APIRouter()
session_service = AgentSessionService(session_factory=SessionLocal)
read_service = AgentReadService(session_factory=SessionLocal)
execution_service = AgentExecutionService(session_factory=SessionLocal)
task_read_service = AgentTaskReadService(session_factory=SessionLocal)
STREAM_BATCH_LIMIT = 50
STREAM_POLL_INTERVAL_SECONDS = 0.5
STREAM_HEARTBEAT_INTERVAL_SECONDS = 10.0


def _runtime():
    return build_agent_runtime(
        session_service=session_service,
        execution_service=execution_service,
    )


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


def _active_operation_conflict(exc: ActiveOperationConflict) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "message": "Session has an active operation",
            "activeOperation": {
                "type": exc.operation_type,
                "id": exc.operation_id,
            },
        },
    )


def _parse_last_sequence(after_sequence: int | None, last_event_id: str | None) -> int:
    if last_event_id:
        try:
            return max(0, int(last_event_id))
        except ValueError:
            return 0
    return max(0, after_sequence or 0)


def _trace_event_payload(event: AgentTraceEvent) -> dict:
    if hasattr(event, "model_dump"):
        return event.model_dump()
    return event.dict()


class SessionCreateRequest(BaseModel):
    message: str | None = None


class MessageRequest(BaseModel):
    message: str


class GroundingConfirmRequest(BaseModel):
    candidateIds: list[str]


@router.post("/sessions", response_model=AgentSession)
async def create_session(request: SessionCreateRequest):
    try:
        runtime = _runtime()
        session = await run_in_threadpool(runtime.create_session, request.message)
        return agent_service.sync_session(session)
    except HTTPException:
        raise
    except Exception as exc:
        raise _translate_planner_error(exc)


@router.get("/sessions/{session_id}", response_model=AgentSession)
async def get_session(session_id: str):
    try:
        session = await run_in_threadpool(session_service.get_session, session_id)
        return agent_service.sync_session(session)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions/{session_id}/messages", response_model=AgentSession)
async def add_message(session_id: str, request: MessageRequest):
    try:
        runtime = _runtime()
        session = await run_in_threadpool(runtime.submit_message, session_id, request.message)
        return agent_service.sync_session(session)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ActiveOperationConflict as exc:
        raise _active_operation_conflict(exc)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise _translate_planner_error(exc)


@router.post("/sessions/{session_id}/grounding/confirm", response_model=AgentSession)
async def confirm_grounding_candidates(session_id: str, request: GroundingConfirmRequest):
    try:
        runtime = _runtime()
        session = await run_in_threadpool(
            runtime.confirm_grounding,
            session_id,
            request.candidateIds,
        )
        return agent_service.sync_session(session)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ActiveOperationConflict as exc:
        raise _active_operation_conflict(exc)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise _translate_planner_error(exc)


@router.post("/sessions/{session_id}/confirm", response_model=AgentSession)
async def confirm_session(session_id: str):
    try:
        runtime = _runtime()
        session = await run_in_threadpool(runtime.confirm_plan, session_id)
        return agent_service.sync_session(session)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ActiveOperationConflict as exc:
        raise _active_operation_conflict(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/sessions/{session_id}/events", response_model=list[AgentEvent])
async def get_session_events(session_id: str):
    try:
        return await run_in_threadpool(read_service.read_events, session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/sessions/{session_id}/runs", response_model=list[AgentRunSummary])
async def list_session_runs(session_id: str):
    def read_runs():
        with SessionLocal() as db:
            session_record = AgentSessionRepository(db).get(session_id)
            if session_record is None:
                raise KeyError(session_id)
            return [
                AgentRunSummary(
                    id=row.id,
                    sessionId=row.session_id,
                    triggerType=row.trigger_type,
                    status=row.status,
                    summary=row.summary or "",
                    startedAt=row.started_at.isoformat() if row.started_at else None,
                    finishedAt=row.finished_at.isoformat() if row.finished_at else None,
                    createdAt=row.created_at.isoformat(),
                )
                for row in AgentRunRepository(db).list_for_session(session_id)
            ]

    try:
        return await run_in_threadpool(read_runs)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/sessions/{session_id}/runs/{run_id}/trace", response_model=list[AgentTraceEvent])
async def list_run_trace(session_id: str, run_id: str):
    def read_trace():
        with SessionLocal() as db:
            session_record = AgentSessionRepository(db).get(session_id)
            run_record = AgentRunRepository(db).get(run_id)
            if session_record is None or run_record is None or run_record.session_id != session_id:
                raise KeyError(run_id)
            return [
                AgentTraceEvent(
                    id=row.id,
                    sessionId=row.session_id,
                    runId=row.run_id,
                    stepId=row.step_id,
                    jobId=row.job_id,
                    eventType=row.event_type,
                    level=row.level,
                    message=row.message,
                    payload=row.payload_json or {},
                    sequence=row.sequence,
                    actorRole=row.actor_role,
                    createdAt=row.created_at.isoformat(),
                )
                for row in AgentTraceEventRepository(db).list_for_run(run_id)
            ]

    try:
        return await run_in_threadpool(read_trace)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found")


@router.get("/sessions/{session_id}/trace", response_model=list[AgentTraceEvent])
async def list_session_trace(session_id: str, afterSequence: int | None = None, limit: int = 100):
    def read_trace():
        with SessionLocal() as db:
            session_record = AgentSessionRepository(db).get(session_id)
            if session_record is None:
                raise KeyError(session_id)
            bounded_limit = max(1, min(limit, 500))
            return [
                AgentTraceEvent(
                    id=row.id,
                    sessionId=row.session_id,
                    runId=row.run_id,
                    stepId=row.step_id,
                    jobId=row.job_id,
                    eventType=row.event_type,
                    level=row.level,
                    message=row.message,
                    payload=row.payload_json or {},
                    sequence=row.sequence,
                    actorRole=row.actor_role,
                    createdAt=row.created_at.isoformat(),
                )
                for row in AgentTraceEventRepository(db).list_for_session(
                    session_id,
                    after_sequence=afterSequence,
                    limit=bounded_limit,
                )
            ]

    try:
        return await run_in_threadpool(read_trace)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/sessions/{session_id}/stream")
async def stream_session_trace(
    session_id: str,
    request: Request,
    afterSequence: int | None = None,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    last_sequence = _parse_last_sequence(afterSequence, last_event_id)

    def ensure_session_exists():
        with SessionLocal() as db:
            AgentStreamService(db).require_session(session_id)

    try:
        await run_in_threadpool(ensure_session_exists)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        nonlocal last_sequence
        last_heartbeat_at = asyncio.get_running_loop().time()

        while True:
            if await request.is_disconnected():
                break

            def read_batch():
                with SessionLocal() as db:
                    service = AgentStreamService(db)
                    batch = service.read_trace_batch(
                        session_id,
                        after_sequence=last_sequence,
                        limit=STREAM_BATCH_LIMIT,
                    )
                    should_close = service.should_close_stream(session_id)
                    return batch, should_close

            try:
                batch, should_close = await run_in_threadpool(read_batch)
            except Exception:
                yield format_sse_event(
                    "stream_error",
                    {"sessionId": session_id, "lastSequence": last_sequence},
                )
                break

            for event in batch.events:
                last_sequence = event.sequence
                yield format_sse_event(
                    event.eventType,
                    _trace_event_payload(event),
                    event_id=event.sequence,
                )

            if should_close:
                yield format_sse_event(
                    "stream_closed",
                    {
                        "sessionId": session_id,
                        "lastSequence": last_sequence,
                        "reason": "session_terminal",
                    },
                )
                break

            now = asyncio.get_running_loop().time()
            if now - last_heartbeat_at >= STREAM_HEARTBEAT_INTERVAL_SECONDS:
                yield format_sse_event(
                    "heartbeat",
                    {"sessionId": session_id, "lastSequence": last_sequence},
                )
                last_heartbeat_at = now

            await asyncio.sleep(STREAM_POLL_INTERVAL_SECONDS)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/dashboard", response_model=AgentDashboardSummary)
async def get_dashboard():
    return await run_in_threadpool(task_read_service.read_dashboard)


@router.get("/tasks", response_model=list[AgentTaskSummary])
async def list_tasks():
    return await run_in_threadpool(task_read_service.list_tasks)


@router.get("/tasks/{job_id}", response_model=AgentTaskDetail)
async def get_task(job_id: str):
    try:
        return await run_in_threadpool(task_read_service.read_task, job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")

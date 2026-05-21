from __future__ import annotations

from uuid import uuid4

from backend.db.repositories import AgentStepRepository, ToolCallRepository
from backend.domain.tools.contracts import ToolCallRequest, ToolCallResult, ToolCallSummary
from backend.runtime.trace_recorder import TraceEvent, TraceRecorder
from backend.utils.time import utc_now_naive


class ToolCallService:
    def __init__(self, db_session=None, tool_call_repository: ToolCallRepository | None = None, trace_recorder: TraceRecorder | None = None) -> None:
        self.db = db_session
        self.tool_call_repository = tool_call_repository
        self.trace_recorder = trace_recorder or TraceRecorder()

    def record_tool_call(
        self,
        request: ToolCallRequest,
        result: ToolCallResult,
    ) -> ToolCallSummary:
        now = utc_now_naive()
        summary = ToolCallSummary(
            tool_id=request.tool_id,
            status=result.status,
            result_summary=result.result_summary,
            result_ref=result.result_ref,
            error_message=result.error_message,
        )

        if self.tool_call_repository is not None:
            self.tool_call_repository.create_tool_call(
                id=str(uuid4()),
                run_id=request.run_id,
                step_id=request.step_id,
                tool_id=request.tool_id,
                status=result.status,
                arguments_json=request.arguments,
                result_summary=result.result_summary,
                result_ref=result.result_ref,
                error_message=result.error_message,
                actor=request.actor,
                actor_role=request.actor_role,
                started_at=now,
                finished_at=now,
            )

        if self.trace_recorder is not None:
            step_record_id = request.step_id
            if self.db is not None:
                step_record = AgentStepRepository(self.db).get(request.step_id)
                if step_record is not None:
                    step_record_id = step_record.id
            self.trace_recorder.record(
                TraceEvent(
                    session_id=request.session_id,
                    run_id=request.run_id,
                    step_id=step_record_id,
                    event_type="tool_call_recorded",
                    payload={
                        "toolId": request.tool_id,
                        "status": result.status,
                        "resultSummary": result.result_summary,
                        "resultRef": result.result_ref,
                        "errorMessage": result.error_message,
                        "arguments": request.arguments,
                    },
                    message=result.result_summary or result.error_message or None,
                    actor_role=request.actor_role,
                    actor_id=request.actor,
                )
            )

        return summary

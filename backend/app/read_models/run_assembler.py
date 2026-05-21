from backend.app.agent.step_snapshot_service import AgentStepSnapshotService
from backend.app.read_models.trace_assembler import TraceReadModelAssembler
from backend.models.agent import (
    AgentRunDetail,
    AgentRunSummary,
    AgentSkillActivity,
    AgentToolCallSummary,
)


class RunReadModelAssembler:
    def __init__(
        self,
        step_snapshot_service: AgentStepSnapshotService | None = None,
        trace_assembler: TraceReadModelAssembler | None = None,
    ) -> None:
        self.step_snapshot_service = step_snapshot_service or AgentStepSnapshotService()
        self.trace_assembler = trace_assembler or TraceReadModelAssembler()

    def build_run_summary(self, run_row) -> AgentRunSummary:
        return AgentRunSummary(
            id=run_row.id,
            sessionId=run_row.session_id,
            triggerType=run_row.trigger_type,
            status=run_row.status,
            summary=run_row.summary or "",
            startedAt=run_row.started_at.isoformat() if getattr(run_row, "started_at", None) else None,
            finishedAt=run_row.finished_at.isoformat() if getattr(run_row, "finished_at", None) else None,
            createdAt=run_row.created_at.isoformat(),
        )

    def build_run_detail(self, run_row, step_rows, trace_rows, tool_call_rows) -> AgentRunDetail:
        summary = self.build_run_summary(run_row)
        persisted_steps = self.step_snapshot_service.build_persisted_steps(step_rows or [])
        trace_events = self.trace_assembler.build_trace_events(trace_rows or [])
        tool_calls = [self._build_tool_call_summary(row) for row in tool_call_rows or []]
        return AgentRunDetail(
            **summary.model_dump(),
            trace=trace_events,
            toolCalls=tool_calls,
            skillActivity=self._build_skill_activity(trace_rows or []),
            steps=persisted_steps,
        )

    def _build_tool_call_summary(self, row) -> AgentToolCallSummary:
        return AgentToolCallSummary(
            id=row.id,
            toolId=row.tool_id,
            status=row.status,
            actor=getattr(row, "actor", "") or "",
            actorRole=getattr(row, "actor_role", "planner") or "planner",
            stepId=row.step_id or "",
            resultSummary=row.result_summary or "",
            resultRef=row.result_ref or "",
            errorMessage=row.error_message or "",
            startedAt=row.started_at.isoformat() if getattr(row, "started_at", None) else None,
            finishedAt=row.finished_at.isoformat() if getattr(row, "finished_at", None) else None,
        )

    def _build_skill_activity(self, trace_rows) -> AgentSkillActivity | None:
        selected_payload = {}
        summary_payload = {}

        for row in trace_rows:
            payload = getattr(row, "payload_json", None) or {}
            skill_summary = payload.get("skillRunSummary")

            if row.event_type == "skill_selected":
                selected_payload = {
                    "skillId": payload.get("skillId", ""),
                    "skillVersion": payload.get("skillVersion", ""),
                    "reason": payload.get("reason", ""),
                    "runType": payload.get("runType", ""),
                }
                continue

            if row.event_type in {"skill_run_succeeded", "skill_run_failed"} and isinstance(skill_summary, dict):
                summary_payload = {
                    "skillId": skill_summary.get("skillId", ""),
                    "skillVersion": skill_summary.get("skillVersion", ""),
                    "status": skill_summary.get("status") or self._status_from_event(row.event_type),
                    "inputSummary": skill_summary.get("inputSummary", ""),
                    "outputSummary": skill_summary.get("outputSummary", ""),
                    "errorMessage": skill_summary.get("errorMessage", ""),
                }

        skill_id = summary_payload.get("skillId") or selected_payload.get("skillId") or ""
        if not skill_id:
            return None

        return AgentSkillActivity(
            skillId=skill_id,
            skillVersion=summary_payload.get("skillVersion") or selected_payload.get("skillVersion") or "",
            status=summary_payload.get("status") or self._status_from_traces(trace_rows),
            reason=selected_payload.get("reason", ""),
            inputSummary=summary_payload.get("inputSummary", ""),
            outputSummary=summary_payload.get("outputSummary", ""),
            errorMessage=summary_payload.get("errorMessage", ""),
            runType=selected_payload.get("runType", ""),
        )

    def _status_from_event(self, event_type: str) -> str:
        if event_type in {"skill_run_succeeded", "succeeded"}:
            return "succeeded"
        if event_type in {"skill_run_failed", "failed"}:
            return "failed"
        return ""

    def _status_from_traces(self, trace_rows) -> str:
        for row in reversed(trace_rows):
            status = self._status_from_event(getattr(row, "event_type", ""))
            if status:
                return status
            payload = getattr(row, "payload_json", None) or {}
            skill_summary = payload.get("skillRunSummary")
            if isinstance(skill_summary, dict) and skill_summary.get("status"):
                return skill_summary["status"]
        return ""

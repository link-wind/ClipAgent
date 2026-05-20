from backend.models.agent import AgentTraceEvent


class TraceReadModelAssembler:
    def build_trace_events(self, records):
        return [
            AgentTraceEvent(
                id=record.id,
                sessionId=record.session_id,
                runId=record.run_id,
                stepId=record.step_id,
                jobId=record.job_id,
                eventType=record.event_type,
                level=record.level,
                message=record.message,
                payload=record.payload_json or {},
                sequence=record.sequence,
                actorRole=record.actor_role,
                createdAt=record.created_at.isoformat(),
            )
            for record in records
        ]

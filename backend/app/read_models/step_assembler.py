from datetime import datetime

from backend.app.agent.step_snapshot_service import AgentStepSnapshotService


VISIBLE_SESSION_STEP_KEYS = (
    "understand_request",
    "extract_requirements",
    "generate_options",
    "finalize_plan",
    "create_task",
    "search_assets",
    "prepare_assets",
    "render_video",
)


class StepReadModelAssembler:
    def __init__(self, step_snapshot_service: AgentStepSnapshotService | None = None):
        self.step_snapshot_service = step_snapshot_service or AgentStepSnapshotService()

    def build_session_steps(
        self,
        *,
        session_record,
        message_rows,
        plan_row,
        event_rows,
        persisted_step_rows=None,
    ):
        steps = self.step_snapshot_service.build_session_steps(
            session_record=session_record,
            message_rows=message_rows,
            plan_row=plan_row,
            event_rows=event_rows,
        )
        visible_persisted_step_rows = self.filter_visible_persisted_steps(persisted_step_rows or [])
        if not visible_persisted_step_rows:
            return steps

        steps_by_id = {step.id: step for step in steps}
        for step in self.step_snapshot_service.build_persisted_steps(visible_persisted_step_rows):
            base_step = steps_by_id.get(step.id)
            if base_step is None:
                continue
            steps_by_id[step.id] = base_step.model_copy(
                update={
                    "status": step.status,
                    "progress": step.progress,
                    "summary": step.summary,
                    "result": step.result,
                    "error": step.error,
                    "startedAt": step.startedAt,
                    "finishedAt": step.finishedAt,
                }
            )
        return [steps_by_id.get(step.id, step) for step in steps]

    def build_task_steps(self, *, session_record, job_record, plan_row, artifact_rows, event_rows):
        steps = self.step_snapshot_service.build_task_steps(
            session_record=session_record,
            job_record=job_record,
            plan_row=plan_row,
            artifact_rows=artifact_rows,
            event_rows=event_rows,
        )
        return steps

    def filter_visible_persisted_steps(self, persisted_step_rows):
        latest_rows_by_key = {}
        for row in persisted_step_rows:
            if row.step_key not in VISIBLE_SESSION_STEP_KEYS:
                continue
            current = latest_rows_by_key.get(row.step_key)
            if current is None or self._step_row_version_key(row) > self._step_row_version_key(current):
                latest_rows_by_key[row.step_key] = row
        return [
            latest_rows_by_key[step_key]
            for step_key in VISIBLE_SESSION_STEP_KEYS
            if step_key in latest_rows_by_key
        ]

    @staticmethod
    def _step_row_version_key(step_row):
        created_at = getattr(step_row, "created_at", None) or datetime.min
        updated_at = getattr(step_row, "updated_at", None) or created_at
        return (updated_at, created_at, getattr(step_row, "id", ""))

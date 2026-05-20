from backend.app.agent.step_snapshot_service import AgentStepSnapshotService
from backend.app.read_models.step_assembler import StepReadModelAssembler


class StepProjectionService:
    def __init__(
        self,
        assembler: StepReadModelAssembler | None = None,
        step_snapshot_service: AgentStepSnapshotService | None = None,
    ):
        self.assembler = assembler or StepReadModelAssembler(
            step_snapshot_service=step_snapshot_service,
        )

    def build_session_steps(
        self,
        *,
        session_record,
        message_rows,
        plan_row,
        event_rows,
        persisted_step_rows=None,
    ):
        return self.assembler.build_session_steps(
            session_record=session_record,
            message_rows=message_rows,
            plan_row=plan_row,
            event_rows=event_rows,
            persisted_step_rows=persisted_step_rows,
        )

    def build_task_steps(
        self,
        *,
        session_record,
        job_record,
        plan_row,
        artifact_rows,
        event_rows,
    ):
        return self.assembler.build_task_steps(
            session_record=session_record,
            job_record=job_record,
            plan_row=plan_row,
            artifact_rows=artifact_rows,
            event_rows=event_rows,
        )

    def filter_visible_persisted_steps(self, persisted_step_rows):
        return self.assembler.filter_visible_persisted_steps(persisted_step_rows)

    @staticmethod
    def _step_row_version_key(step_row):
        return StepReadModelAssembler._step_row_version_key(step_row)

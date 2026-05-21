from backend.db.repositories import (
    AgentRunRepository,
    AgentSessionRepository,
    AgentStepRepository,
    AgentTraceEventRepository,
    ToolCallRepository,
)
from backend.app.read_models.run_assembler import RunReadModelAssembler


class AgentRunReadService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.run_assembler = RunReadModelAssembler()

    def read_run(self, session_id: str, run_id: str):
        with self.session_factory() as db:
            session_record = AgentSessionRepository(db).get(session_id)
            run_record = AgentRunRepository(db).get(run_id)
            if session_record is None or run_record is None or run_record.session_id != session_id:
                raise KeyError(run_id)

            return self.run_assembler.build_run_detail(
                run_record,
                AgentStepRepository(db).list_for_run(run_id),
                AgentTraceEventRepository(db).list_for_run(run_id),
                ToolCallRepository(db).list_for_run(run_id),
            )

from backend.app.read_models.run_assembler import RunReadModelAssembler


class AgentRunReadService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.run_assembler = RunReadModelAssembler()

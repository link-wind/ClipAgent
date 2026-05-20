class StepReadModelAssembler:
    def build_session_steps(self, **kwargs):
        raise NotImplementedError

    def build_task_steps(self, **kwargs):
        raise NotImplementedError

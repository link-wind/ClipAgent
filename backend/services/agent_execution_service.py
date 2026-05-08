from collections.abc import Callable

from backend.db.repositories import (
    AgentEventRepository,
    AgentJobRepository,
    AgentPlanRepository,
    AgentSessionRepository,
)
from backend.models.agent import AgentSession
from backend.services.agent_read_service import AgentReadService
from backend.tasks.agent_tasks import run_agent_job


class AgentExecutionService:
    def __init__(self, session_factory, enqueue_job: Callable[[str], None] | None = None):
        self.session_factory = session_factory
        self.read_service = AgentReadService(session_factory=session_factory)
        self.enqueue_job = enqueue_job or self._enqueue_with_celery

    def confirm_session(self, session_id: str) -> AgentSession:
        # 创建任务、记录入队事件，并返回最新会话
        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            plan_repo = AgentPlanRepository(db)
            job_repo = AgentJobRepository(db)
            event_repo = AgentEventRepository(db)

            try:
                session_record = session_repo.get(session_id)
                if session_record is None:
                    raise KeyError(session_id)

                if session_record.status not in {"idle", "plan_ready"}:
                    raise RuntimeError(f"Session cannot be confirmed while {session_record.status}")
                if self._requires_grounding_confirmation(session_record) and session_record.grounding_status != "confirmed":
                    raise RuntimeError("Session cannot be confirmed before grounding candidates are selected")

                plan_record = plan_repo.get_latest_for_session(session_id)
                if plan_record is None:
                    session_record.status = "failed"
                    session_record.progress = 0
                    session_record.current_step = "没有可执行的剪辑方案"
                    session_record.error_message = "没有可执行的剪辑方案"
                    session_record.error_retryable_step = "planning"
                    db.commit()
                    return self.read_service.read_session(session_id)

                job_record = job_repo.create(
                    session_id=session_id,
                    plan_id=plan_record.id,
                    job_type="generate_video",
                    status="queued",
                    progress=0,
                    current_step="任务已入队",
                    max_attempts=3,
                )
                job_id = job_record.id
                session_record.status = "queued"
                session_record.progress = 25
                session_record.current_step = "任务已入队"
                session_record.active_job_id = job_id
                session_record.error_message = None
                session_record.error_retryable_step = None
                event_repo.create(
                    session_id=session_id,
                    job_id=job_id,
                    event_type="job_queued",
                    step="queued",
                    progress=25,
                    message="任务已入队，等待执行",
                    payload_json={"jobId": job_id},
                )
                db.commit()
            except Exception:
                db.rollback()
                raise

        self.enqueue_job(job_id)
        return self.read_service.read_session(session_id)

    @staticmethod
    def _requires_grounding_confirmation(session_record) -> bool:
        grounding_summary = getattr(session_record, "grounding_summary_json", None) or {}
        if getattr(session_record, "selected_candidate_ids_json", None):
            return True
        if getattr(session_record, "grounding_status", None) in {"needs_confirmation", "confirmed"}:
            return True
        return any(
            grounding_summary.get(key)
            for key in (
                "productName",
                "audience",
                "styleHint",
                "featureHints",
                "searchQueries",
                "candidates",
                "selectedCandidateIds",
            )
        )

    @staticmethod
    def _enqueue_with_celery(job_id: str) -> None:
        # 通过 Celery 正式投递任务
        run_agent_job.delay(job_id)

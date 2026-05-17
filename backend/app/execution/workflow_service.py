from backend.db.repositories import AgentJobRepository, AgentPlanRepository
from backend.models.agent import EditPlan
from backend.services.agent_progress_service import AgentProgressService
from backend.services.planner_projection import execution_plan_to_edit_plan

from backend.app.execution.asset_execution_service import AssetExecutionService
from backend.app.execution.execution_replan_service import (
    ExecutionReplanService,
    build_worker_failure_payload,
)
from backend.app.execution.job_claim_service import JobClaimService
from backend.app.execution.render_execution_service import RenderExecutionService


class ExecutionWorkflowService:
    def __init__(
        self,
        *,
        session_factory,
        asset_executor=None,
        claim_service=None,
        render_executor=None,
        replan_service=None,
        dispatch_job=None,
    ):
        self.session_factory = session_factory
        self.asset_executor = asset_executor or AssetExecutionService()
        self.claim_service = claim_service or JobClaimService()
        self.render_executor = render_executor or RenderExecutionService()
        self.replan_service = replan_service or ExecutionReplanService()
        self.dispatch_job = dispatch_job

    def run_job(self, job_id: str) -> None:
        with self.session_factory() as db:
            plan_repo = AgentPlanRepository(db)
            progress_service = AgentProgressService(db)

            try:
                job_record = self.claim_service.try_claim_job(db, job_id)
                if job_record is None:
                    db.rollback()
                    return
                if not job_record.session_id:
                    raise RuntimeError("任务缺少 session_id")
                if not job_record.plan_id:
                    raise RuntimeError("任务缺少 plan_id")

                session_id = job_record.session_id
                plan_record = plan_repo.get(job_record.plan_id)
                if plan_record is None:
                    raise RuntimeError("任务缺少可执行计划")

                plan = self._build_plan(plan_record)
                progress_service.mark_job_running(session_id, job_id)
                db.commit()

                clips = self.asset_executor.execute(
                    progress_service=progress_service,
                    session_id=session_id,
                    job_id=job_id,
                    plan=plan,
                )
                db.commit()

                video_url = self.render_executor.execute(
                    progress_service=progress_service,
                    session_id=session_id,
                    job_id=job_id,
                    clips=clips,
                )
                progress_service.mark_job_succeeded(session_id, job_id, video_url)
                db.commit()
            except Exception as exc:
                db.rollback()
                self._handle_failure(db, job_id, exc)

    def _handle_failure(self, db, job_id: str, exc: Exception) -> None:
        job_repo = AgentJobRepository(db)
        job_record = job_repo.get(job_id)
        if job_record is None or not job_record.session_id:
            raise exc

        progress_service = AgentProgressService(db)
        retryable_step = "rendering" if job_record.progress >= 80 else "searching"
        progress_service.mark_job_failed(
            session_id=job_record.session_id,
            job_id=job_id,
            message=str(exc),
            retryable_step=retryable_step,
        )
        self._replace_latest_failed_event_payload(progress_service, job_id, exc, retryable_step)

        replacement_job_id = None
        try:
            replacement_job_id = self.replan_service.attempt_replan(
                db=db,
                progress_service=progress_service,
                job_record=job_record,
                exc=exc,
                retryable_step=retryable_step,
            )
        except Exception:
            db.rollback()
            job_record = job_repo.get(job_id)
            if job_record is None or not job_record.session_id:
                raise
            progress_service = AgentProgressService(db)
            if job_record.status != "failed":
                progress_service.mark_job_failed(
                    session_id=job_record.session_id,
                    job_id=job_id,
                    message=str(exc),
                    retryable_step=retryable_step,
                )
                self._replace_latest_failed_event_payload(progress_service, job_id, exc, retryable_step)

        db.commit()
        if replacement_job_id and self.dispatch_job is not None:
            self.dispatch_job(replacement_job_id)

    @staticmethod
    def _replace_latest_failed_event_payload(progress_service, job_id: str, exc: Exception, retryable_step: str) -> None:
        latest_events = progress_service.event_repo.list_for_job(job_id)
        if not latest_events:
            return
        latest_event = latest_events[-1]
        if latest_event.event_type == "job_failed":
            latest_event.payload_json = build_worker_failure_payload(exc, retryable_step)

    @staticmethod
    def _build_plan(plan_record) -> EditPlan:
        execution_plan_json = getattr(plan_record, "execution_plan_json", None) or {}
        if execution_plan_json.get("scenes"):
            return execution_plan_to_edit_plan(execution_plan_json)
        return EditPlan.model_validate(plan_record.plan_json)

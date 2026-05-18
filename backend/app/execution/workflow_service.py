from backend.app.execution.artifact_service import ExecutionArtifactService
from backend.app.execution.asset_execution_service import AssetExecutionService
from backend.app.execution.event_service import ExecutionEventService
from backend.app.execution.execution_replan_service import (
    ExecutionReplanService,
    build_worker_failure_payload,
)
from backend.app.execution.job_claim_service import JobClaimService
from backend.app.execution.job_state_service import JobStateService
from backend.app.execution.render_execution_service import RenderExecutionService
from backend.app.execution.step_lifecycle import StepLifecycleService
from backend.app.planning.projection import execution_plan_to_edit_plan
from backend.db.repositories import AgentJobRepository, AgentPlanRepository
from backend.models.agent import EditPlan

STEP_DEFINITIONS = {
    "search_assets": ("搜索素材", "根据最终方案搜索候选素材并记录搜索结果。", 6),
    "prepare_assets": ("准备素材", "下载、裁剪、整理素材，形成渲染输入。", 7),
    "render_video": ("渲染视频", "调用渲染流程，生成视频产物或失败原因。", 8),
}

RETRYABLE_STEP_TO_STEP_KEY = {
    "searching": "search_assets",
    "downloading": "prepare_assets",
    "rendering": "render_video",
}


def _ensure_execution_step(step_lifecycle: StepLifecycleService, *, session_id: str, job_id: str, step_key: str):
    title, description, sequence = STEP_DEFINITIONS.get(
        step_key,
        ("渲染视频", "调用渲染流程，生成视频产物或失败原因。", 8),
    )
    return step_lifecycle.ensure_step(
        session_id=session_id,
        job_id=job_id,
        step_key=step_key,
        title=title,
        description=description,
        sequence=sequence,
    )


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
            job_state_service = JobStateService(db)
            event_service = ExecutionEventService(db)
            artifact_service = ExecutionArtifactService(db)
            step_lifecycle = StepLifecycleService(db)

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
                job_state_service.mark_job_running(session_id=session_id, job_id=job_id)
                event_service.record_event(
                    session_id=session_id,
                    job_id=job_id,
                    event_type="job_started",
                    step="searching",
                    message="任务开始执行",
                    progress=35,
                )
                _ensure_execution_step(
                    step_lifecycle,
                    session_id=session_id,
                    job_id=job_id,
                    step_key="search_assets",
                )
                db.commit()

                clips = self.asset_executor.execute(
                    job_state_service=job_state_service,
                    artifact_service=artifact_service,
                    step_lifecycle=step_lifecycle,
                    session_id=session_id,
                    job_id=job_id,
                    plan=plan,
                )
                event_service.record_event(
                    session_id=session_id,
                    job_id=job_id,
                    event_type="clips_ready",
                    step="downloading",
                    message=f"素材已准备完成，共 {len(clips)} 段",
                    progress=60,
                    payload={"clipCount": len(clips)},
                )
                db.commit()

                video_url = self.render_executor.execute(
                    commit=db.commit,
                    job_state_service=job_state_service,
                    event_service=event_service,
                    artifact_service=artifact_service,
                    step_lifecycle=step_lifecycle,
                    session_id=session_id,
                    job_id=job_id,
                    clips=clips,
                )
                job_state_service.mark_job_succeeded(
                    session_id=session_id,
                    job_id=job_id,
                    video_url=video_url,
                )
                event_service.record_event(
                    session_id=session_id,
                    job_id=job_id,
                    event_type="job_succeeded",
                    step="done",
                    message="视频已经生成，可以预览或下载。",
                    progress=100,
                    payload={"videoUrl": video_url},
                )
                render_step = _ensure_execution_step(
                    step_lifecycle,
                    session_id=session_id,
                    job_id=job_id,
                    step_key="render_video",
                )
                if render_step.status != "succeeded":
                    step_lifecycle.step_service.succeed_step(
                        render_step.id,
                        summary="视频已经生成",
                        result={"videoUrl": video_url},
                    )
                db.commit()
            except Exception as exc:
                db.rollback()
                self._handle_failure(db, job_id, exc)

    def _handle_failure(self, db, job_id: str, exc: Exception) -> None:
        job_repo = AgentJobRepository(db)
        job_record = job_repo.get(job_id)
        if job_record is None or not job_record.session_id:
            raise exc

        job_state_service = JobStateService(db)
        event_service = ExecutionEventService(db)
        step_lifecycle = StepLifecycleService(db)
        retryable_step = "rendering" if job_record.progress >= 80 else "searching"
        job_state_service.mark_job_failed(
            session_id=job_record.session_id,
            job_id=job_id,
            message=str(exc),
            retryable_step=retryable_step,
        )
        event_service.record_event(
            session_id=job_record.session_id,
            job_id=job_id,
            event_type="job_failed",
            step="failed",
            message=str(exc),
            progress=job_record.progress,
            payload={"retryableStep": retryable_step},
        )
        step_key = RETRYABLE_STEP_TO_STEP_KEY.get(retryable_step, "render_video")
        failed_step = _ensure_execution_step(
            step_lifecycle,
            session_id=job_record.session_id,
            job_id=job_id,
            step_key=step_key,
        )
        step_lifecycle.step_service.fail_step(
            failed_step.id,
            message=str(exc),
            retryable=True,
            retryable_step=step_key,
        )
        self._replace_latest_failed_event_payload(event_service, job_id, exc, retryable_step)

        replacement_job_id = None
        try:
            replacement_job_id = self.replan_service.attempt_replan(
                db=db,
                job_state_service=job_state_service,
                event_service=event_service,
                job_record=job_record,
                exc=exc,
                retryable_step=retryable_step,
            )
        except Exception:
            db.rollback()
            job_record = job_repo.get(job_id)
            if job_record is None or not job_record.session_id:
                raise
            job_state_service = JobStateService(db)
            event_service = ExecutionEventService(db)
            step_lifecycle = StepLifecycleService(db)
            if job_record.status != "failed":
                job_state_service.mark_job_failed(
                    session_id=job_record.session_id,
                    job_id=job_id,
                    message=str(exc),
                    retryable_step=retryable_step,
                )
                event_service.record_event(
                    session_id=job_record.session_id,
                    job_id=job_id,
                    event_type="job_failed",
                    step="failed",
                    message=str(exc),
                    progress=job_record.progress,
                    payload={"retryableStep": retryable_step},
                )
                step_key = RETRYABLE_STEP_TO_STEP_KEY.get(retryable_step, "render_video")
                failed_step = _ensure_execution_step(
                    step_lifecycle,
                    session_id=job_record.session_id,
                    job_id=job_id,
                    step_key=step_key,
                )
                step_lifecycle.step_service.fail_step(
                    failed_step.id,
                    message=str(exc),
                    retryable=True,
                    retryable_step=step_key,
                )
                self._replace_latest_failed_event_payload(event_service, job_id, exc, retryable_step)

        db.commit()
        if replacement_job_id and self.dispatch_job is not None:
            self.dispatch_job(replacement_job_id)

    @staticmethod
    def _replace_latest_failed_event_payload(event_service, job_id: str, exc: Exception, retryable_step: str) -> None:
        latest_events = event_service.event_repo.list_for_job(job_id)
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

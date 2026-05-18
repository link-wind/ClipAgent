from datetime import datetime

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
from backend.db.repositories import AgentJobRepository, AgentPlanRepository
from backend.models.agent import EditPlan
from backend.services.planner_projection import execution_plan_to_edit_plan

MAX_CURRENT_STEP_LENGTH = 128
FAILED_STEP_PREFIX = "处理失败："


def _format_failed_current_step(message: str) -> str:
    current_step = f"{FAILED_STEP_PREFIX}{message}"
    if len(current_step) <= MAX_CURRENT_STEP_LENGTH:
        return current_step

    ellipsis = "..."
    available_length = MAX_CURRENT_STEP_LENGTH - len(FAILED_STEP_PREFIX) - len(ellipsis)
    if available_length <= 0:
        return FAILED_STEP_PREFIX[:MAX_CURRENT_STEP_LENGTH]
    return f"{FAILED_STEP_PREFIX}{message[:available_length]}{ellipsis}"


class _WorkflowJobStateAdapter:
    def __init__(self, db_session):
        self.db = db_session
        self.job_state_service = JobStateService(db_session)
        self.job_repo = self.job_state_service.job_repo
        self.session_repo = self.job_state_service.session_repo
        self.event_service = ExecutionEventService(db_session)
        self.artifact_service = ExecutionArtifactService(db_session)
        self.step_lifecycle = StepLifecycleService(db_session)

    def mark_job_running(self, session_id: str, job_id: str) -> None:
        self.job_state_service.mark_job_running(session_id=session_id, job_id=job_id)
        self.event_service.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="job_started",
            step="searching",
            message="任务开始执行",
            progress=35,
        )
        self.step_lifecycle.ensure_step(
            session_id=session_id,
            job_id=job_id,
            step_key="search_assets",
            title="搜索素材",
            description="根据最终方案搜索候选素材并记录搜索结果。",
            sequence=6,
        )

    def mark_clips_ready(self, session_id: str, job_id: str, clip_count: int) -> None:
        self.job_repo.update_status(
            job_id,
            progress=60,
            current_step="素材已下载，准备渲染",
        )
        session_record = self.session_repo.get(session_id)
        session_record.status = "downloading"
        session_record.progress = 60
        session_record.current_step = "素材已下载，准备渲染"
        self.event_service.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="clips_ready",
            step="downloading",
            message=f"素材已准备完成，共 {clip_count} 段",
            progress=60,
            payload={"clipCount": clip_count},
        )
        search_step = self.step_lifecycle.ensure_step(
            session_id=session_id,
            job_id=job_id,
            step_key="search_assets",
            title="搜索素材",
            description="根据最终方案搜索候选素材并记录搜索结果。",
            sequence=6,
        )
        if search_step.status != "succeeded":
            self.step_lifecycle.step_service.succeed_step(
                search_step.id,
                summary=f"已找到 {clip_count} 段素材",
                result={"selectedCount": clip_count},
            )

        prepare_step = self.step_lifecycle.ensure_step(
            session_id=session_id,
            job_id=job_id,
            step_key="prepare_assets",
            title="准备素材",
            description="下载、裁剪、整理素材，形成渲染输入。",
            sequence=7,
        )
        self.step_lifecycle.step_service.succeed_step(
            prepare_step.id,
            summary=f"素材已准备完成，共 {clip_count} 段",
            result={"clipCount": clip_count},
        )

    def mark_render_started(self, session_id: str, job_id: str) -> None:
        self.job_repo.update_status(
            job_id,
            progress=80,
            current_step="正在合成视频",
        )
        session_record = self.session_repo.get(session_id)
        session_record.status = "rendering"
        session_record.progress = 80
        session_record.current_step = "正在合成视频"
        self.event_service.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="render_started",
            step="rendering",
            message="开始合成视频",
            progress=80,
        )
        self.step_lifecycle.ensure_step(
            session_id=session_id,
            job_id=job_id,
            step_key="render_video",
            title="渲染视频",
            description="调用渲染流程，生成视频产物或失败原因。",
            sequence=8,
        )

    def mark_job_succeeded(self, session_id: str, job_id: str, video_url: str) -> None:
        self.job_repo.update_status(
            job_id,
            status="succeeded",
            progress=100,
            current_step="完成",
            finished_at=datetime.utcnow(),
            error_message=None,
        )
        session_record = self.session_repo.get(session_id)
        session_record.status = "done"
        session_record.progress = 100
        session_record.current_step = "完成"
        session_record.video_url = video_url
        session_record.error_message = None
        session_record.error_retryable_step = None
        self.event_service.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="job_succeeded",
            step="done",
            message="视频已经生成，可以预览或下载。",
            progress=100,
            payload={"videoUrl": video_url},
        )
        render_step = self.step_lifecycle.ensure_step(
            session_id=session_id,
            job_id=job_id,
            step_key="render_video",
            title="渲染视频",
            description="调用渲染流程，生成视频产物或失败原因。",
            sequence=8,
        )
        if render_step.status != "succeeded":
            self.step_lifecycle.step_service.succeed_step(
                render_step.id,
                summary="视频已经生成",
                result={"videoUrl": video_url},
            )
        self.session_repo.finish_operation(session_id, "job", job_id)

    def mark_job_failed(self, session_id: str, job_id: str, message: str, retryable_step: str) -> None:
        current_step = _format_failed_current_step(message)
        self.job_repo.update_status(
            job_id,
            status="failed",
            current_step=current_step,
            finished_at=datetime.utcnow(),
            error_message=message,
        )
        session_record = self.session_repo.get(session_id)
        session_record.status = "failed"
        session_record.current_step = current_step
        session_record.error_message = message
        session_record.error_retryable_step = retryable_step
        self.event_service.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="job_failed",
            step="failed",
            message=message,
            progress=session_record.progress,
            payload={"retryableStep": retryable_step},
        )
        step_key = {
            "searching": "search_assets",
            "downloading": "prepare_assets",
            "rendering": "render_video",
        }.get(retryable_step, "render_video")
        failed_step = self.step_lifecycle.ensure_step(
            session_id=session_id,
            job_id=job_id,
            step_key=step_key,
            title={
                "search_assets": "搜索素材",
                "prepare_assets": "准备素材",
                "render_video": "渲染视频",
            }.get(step_key, "渲染视频"),
            description={
                "search_assets": "根据最终方案搜索候选素材并记录搜索结果。",
                "prepare_assets": "下载、裁剪、整理素材，形成渲染输入。",
                "render_video": "调用渲染流程，生成视频产物或失败原因。",
            }.get(step_key, "调用渲染流程，生成视频产物或失败原因。"),
            sequence={"search_assets": 6, "prepare_assets": 7, "render_video": 8}.get(step_key, 8),
        )
        self.step_lifecycle.step_service.fail_step(
            failed_step.id,
            message=message,
            retryable=True,
            retryable_step=step_key,
        )
        self.session_repo.fail_operation(session_id, "job", job_id, message)

    def mark_job_requeued_after_replan(self, session_id: str, failed_job_id: str, replacement_job_id: str) -> None:
        if not self.session_repo.try_start_operation(session_id, "job", replacement_job_id):
            raise RuntimeError("Session has an active operation")
        session_record = self.session_repo.get(session_id)
        session_record.status = "queued"
        session_record.progress = 25
        session_record.current_step = "任务已重新规划并重新入队"
        session_record.active_job_id = replacement_job_id
        session_record.error_message = None
        session_record.error_retryable_step = None
        self.event_service.record_event(
            session_id=session_id,
            job_id=replacement_job_id,
            event_type="job_requeued_after_replan",
            step="queued",
            message="执行失败后已自动重规划并重新入队",
            progress=25,
            payload={
                "failedJobId": failed_job_id,
                "replacementJobId": replacement_job_id,
            },
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
            workflow_state = _WorkflowJobStateAdapter(db)

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
                workflow_state.mark_job_running(session_id, job_id)
                db.commit()

                clips = self.asset_executor.execute(
                    job_state_service=workflow_state,
                    artifact_service=workflow_state.artifact_service,
                    step_lifecycle=workflow_state.step_lifecycle,
                    session_id=session_id,
                    job_id=job_id,
                    plan=plan,
                )
                db.commit()

                video_url = self.render_executor.execute(
                    job_state_service=workflow_state,
                    event_service=workflow_state.event_service,
                    artifact_service=workflow_state.artifact_service,
                    step_lifecycle=workflow_state.step_lifecycle,
                    session_id=session_id,
                    job_id=job_id,
                    clips=clips,
                )
                workflow_state.mark_job_succeeded(session_id, job_id, video_url)
                db.commit()
            except Exception as exc:
                db.rollback()
                self._handle_failure(db, job_id, exc)

    def _handle_failure(self, db, job_id: str, exc: Exception) -> None:
        job_repo = AgentJobRepository(db)
        job_record = job_repo.get(job_id)
        if job_record is None or not job_record.session_id:
            raise exc

        workflow_state = _WorkflowJobStateAdapter(db)
        retryable_step = "rendering" if job_record.progress >= 80 else "searching"
        workflow_state.mark_job_failed(
            session_id=job_record.session_id,
            job_id=job_id,
            message=str(exc),
            retryable_step=retryable_step,
        )
        self._replace_latest_failed_event_payload(workflow_state.event_service, job_id, exc, retryable_step)

        replacement_job_id = None
        try:
            replacement_job_id = self.replan_service.attempt_replan(
                db=db,
                job_state_service=workflow_state,
                event_service=workflow_state.event_service,
                job_record=job_record,
                exc=exc,
                retryable_step=retryable_step,
            )
        except Exception:
            db.rollback()
            job_record = job_repo.get(job_id)
            if job_record is None or not job_record.session_id:
                raise
            workflow_state = _WorkflowJobStateAdapter(db)
            if job_record.status != "failed":
                workflow_state.mark_job_failed(
                    session_id=job_record.session_id,
                    job_id=job_id,
                    message=str(exc),
                    retryable_step=retryable_step,
                )
                self._replace_latest_failed_event_payload(workflow_state.event_service, job_id, exc, retryable_step)

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

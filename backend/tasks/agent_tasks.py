from backend.app.execution import AssetExecutionService, ExecutionReplanService, ExecutionWorkflowService, RenderExecutionService
from backend.app.execution.execution_replan_service import (
    build_execution_feedback_payload as _build_execution_feedback_payload,
)
from backend.app.execution.execution_replan_service import (
    build_worker_failure_payload as _build_worker_failure_payload,
)
from backend.app.execution.execution_replan_service import (
    extract_failed_scene_ids as _extract_failed_scene_ids,
)
from backend.app.execution.execution_replan_service import (
    should_attempt_execution_replan as _should_attempt_execution_replan,
)
from backend.infrastructure.media.search_service import search_and_download_agent_clips
from backend.tasks.celery_app import celery_app


SessionLocal = None
render_video = None


def dispatch_agent_job(job_id: str) -> None:
    # 单元测试里的 fake celery task 可能只暴露普通函数，此时由测试自行 patch 此 helper。
    delay = getattr(run_agent_job, "delay", None)
    if callable(delay):
        delay(job_id)


@celery_app.task(name="backend.tasks.agent_tasks.run_agent_job")
def run_agent_job(job_id: str) -> None:
    global SessionLocal
    if SessionLocal is None:
        from backend.db import SessionLocal as _SessionLocal

        SessionLocal = _SessionLocal

    workflow = ExecutionWorkflowService(
        session_factory=SessionLocal,
        asset_executor=AssetExecutionService(search_runner=search_and_download_agent_clips),
        render_executor=RenderExecutionService(render_runner=render_video),
        replan_service=ExecutionReplanService(),
        dispatch_job=dispatch_agent_job,
    )
    workflow.run_job(job_id)

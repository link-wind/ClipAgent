import asyncio

from backend.db.repositories import AgentJobRepository, AgentPlanRepository, AgentSessionRepository
from backend.models.agent import ClipInfo, EditPlan
from backend.services.agent_progress_service import AgentProgressService
from backend.services.asset_providers.metadata import pop_clip_metadata
from backend.services.planner_projection import execution_plan_to_edit_plan
from backend.services.planner_orchestrator import PlannerOrchestrator
from backend.services.search_service import search_and_download_agent_clips
from backend.tasks.celery_app import celery_app


SessionLocal = None
render_video = None


def _should_attempt_execution_replan(retryable_step: str) -> bool:
    return retryable_step == "searching"


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

    # 执行正式任务并持久化状态
    with SessionLocal() as db:
        job_repo = AgentJobRepository(db)
        plan_repo = AgentPlanRepository(db)
        progress_service = AgentProgressService(db)

        try:
            job_record = job_repo.get(job_id)
            if job_record is None:
                raise KeyError(job_id)
            if not job_record.session_id:
                raise RuntimeError("任务缺少 session_id")
            if not job_record.plan_id:
                raise RuntimeError("任务缺少 plan_id")

            session_id = job_record.session_id
            plan_record = plan_repo.get(job_record.plan_id)
            if plan_record is None:
                raise RuntimeError("任务缺少可执行计划")

            execution_plan_json = getattr(plan_record, "execution_plan_json", None) or {}
            if execution_plan_json.get("scenes"):
                plan = execution_plan_to_edit_plan(execution_plan_json)
            else:
                plan = EditPlan.model_validate(plan_record.plan_json)
            progress_service.mark_job_running(session_id, job_id)
            db.commit()

            clips = [
                _coerce_clip_info(clip)
                for clip in asyncio.run(search_and_download_agent_clips(session_id, plan.scenes))
            ]
            if not clips:
                raise RuntimeError("没有下载到可用素材")

            progress_service.mark_clips_ready(session_id, job_id, len(clips))
            for clip in clips:
                metadata = {
                    **pop_clip_metadata(clip.localPath),
                    "caption": clip.caption,
                    "sourceDuration": clip.sourceDuration,
                    "trimStart": clip.trimStart,
                    "trimDuration": clip.trimDuration,
                }
                progress_service.create_artifact(
                    session_id=session_id,
                    job_id=job_id,
                    artifact_type="clip",
                    scene_id=str(clip.sceneId),
                    source_url=clip.sourceUrl,
                    local_path=clip.localPath,
                    public_url=clip.publicUrl,
                    duration=clip.duration,
                    metadata=metadata,
                )
            db.commit()

            progress_service.mark_render_started(session_id, job_id)
            db.commit()

            global render_video
            if render_video is None:
                from backend.services.render_service import render_video as _render_video

                render_video = _render_video

            def on_render_progress(event_type: str, message: str, progress: float) -> None:
                # 记录渲染阶段细粒度事件
                progress_service.record_event(
                    session_id=session_id,
                    job_id=job_id,
                    event_type=event_type,
                    step="rendering",
                    message=message,
                    progress=progress,
                )
                db.commit()

            video_url = asyncio.run(
                render_video(
                    session_id,
                    clips,
                    f"{session_id}.mp4",
                    progress_callback=on_render_progress,
                )
            )
            progress_service.create_artifact(
                session_id=session_id,
                job_id=job_id,
                artifact_type="video",
                local_path=f"backend/output/{session_id}.mp4",
                public_url=video_url,
            )
            progress_service.mark_job_succeeded(session_id, job_id, video_url)
            db.commit()
        except Exception as exc:
            db.rollback()
            job_record = job_repo.get(job_id)
            if job_record is not None and job_record.session_id:
                progress_service = AgentProgressService(db)
                retryable_step = "rendering" if job_record.progress >= 80 else "searching"
                if _should_attempt_execution_replan(retryable_step):
                    session_record = AgentSessionRepository(db).get(job_record.session_id)
                    if session_record is not None:
                        try:
                            planner_orchestrator = PlannerOrchestrator()
                            next_plan = planner_orchestrator.persist_execution_feedback_replan(
                                db=db,
                                session_record=session_record,
                                failed_job_record=job_record,
                                execution_feedback={
                                    "failedSceneIds": [],
                                    "failureReason": str(exc),
                                    "retryable": True,
                                    "feedbackSource": "worker_failure",
                                },
                            )
                            progress_service.mark_job_failed(
                                session_id=job_record.session_id,
                                job_id=job_id,
                                message=str(exc),
                                retryable_step=retryable_step,
                            )
                            replacement_job = job_repo.create(
                                session_id=job_record.session_id,
                                plan_id=next_plan.id,
                                job_type=job_record.job_type,
                                status="queued",
                                progress=0,
                                current_step="任务已重新入队",
                                max_attempts=job_record.max_attempts,
                            )
                            progress_service.mark_job_requeued_after_replan(
                                session_id=job_record.session_id,
                                failed_job_id=job_id,
                                replacement_job_id=replacement_job.id,
                            )
                            db.commit()
                            dispatch_agent_job(replacement_job.id)
                            return
                        except Exception:
                            db.rollback()
                            job_record = job_repo.get(job_id)
                            if job_record is None or not job_record.session_id:
                                raise
                            progress_service = AgentProgressService(db)
                progress_service.mark_job_failed(
                    session_id=job_record.session_id,
                    job_id=job_id,
                    message=str(exc),
                    retryable_step=retryable_step,
                )
                db.commit()
            else:
                raise


def _coerce_clip_info(clip) -> ClipInfo:
    # 兼容字典和 Pydantic 片段对象
    if isinstance(clip, ClipInfo):
        return clip
    return ClipInfo.model_validate(clip)

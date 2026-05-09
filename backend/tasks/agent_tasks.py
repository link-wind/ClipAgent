import asyncio

from backend.db.repositories import AgentJobRepository, AgentPlanRepository
from backend.models.agent import ClipInfo, EditPlan
from backend.services.agent_progress_service import AgentProgressService
from backend.services.asset_providers.metadata import pop_clip_metadata
from backend.services.search_service import search_and_download_agent_clips
from backend.tasks.celery_app import celery_app


SessionLocal = None
render_video = None


def _build_worker_failure_payload(exc: Exception, retryable_step: str) -> dict[str, object]:
    payload: dict[str, object] = {"retryableStep": retryable_step}

    failed_scene_ids = getattr(exc, "failed_scene_ids", None)
    if failed_scene_ids is None:
        return payload

    payload.update(
        {
            "failedSceneIds": list(failed_scene_ids),
            "failureReason": str(exc),
            "retryable": True,
            "feedbackSource": "worker_failure",
        }
    )
    failure_category = getattr(exc, "failure_category", None)
    if failure_category:
        payload["failureCategory"] = failure_category
    primary_provider = getattr(exc, "primary_provider", None)
    if primary_provider:
        payload["primaryProvider"] = primary_provider
    provider_diagnostics = getattr(exc, "provider_diagnostics", None)
    if provider_diagnostics:
        payload["providerDiagnostics"] = list(provider_diagnostics)
    scene_diagnostics = getattr(exc, "scene_diagnostics", None)
    if scene_diagnostics:
        payload["sceneDiagnostics"] = list(scene_diagnostics)
    retry_strategy_hint = getattr(exc, "retry_strategy_hint", None)
    if retry_strategy_hint:
        payload["retryStrategyHint"] = retry_strategy_hint
    return payload


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
                progress_service.mark_job_failed(
                    session_id=job_record.session_id,
                    job_id=job_id,
                    message=str(exc),
                    retryable_step=retryable_step,
                )
                failure_payload = _build_worker_failure_payload(exc, retryable_step)
                latest_events = progress_service.event_repo.list_for_job(job_id)
                if latest_events:
                    latest_event = latest_events[-1]
                    if latest_event.event_type == "job_failed":
                        latest_event.payload_json = failure_payload
                db.commit()
            else:
                raise


def _coerce_clip_info(clip) -> ClipInfo:
    # 兼容字典和 Pydantic 片段对象
    if isinstance(clip, ClipInfo):
        return clip
    return ClipInfo.model_validate(clip)

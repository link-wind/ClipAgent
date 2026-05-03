import asyncio

from backend.db import SessionLocal
from backend.db.repositories import AgentJobRepository, AgentPlanRepository
from backend.models.agent import ClipInfo, EditPlan
from backend.services.agent_progress_service import AgentProgressService
from backend.services.render_service import render_video
from backend.services.search_service import search_and_download_agent_clips
from backend.tasks.celery_app import celery_app


@celery_app.task(name="backend.tasks.agent_tasks.run_agent_job")
def run_agent_job(job_id: str) -> None:
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
                progress_service.create_artifact(
                    session_id=session_id,
                    job_id=job_id,
                    artifact_type="clip",
                    scene_id=str(clip.sceneId),
                    source_url=clip.sourceUrl,
                    local_path=clip.localPath,
                    public_url=clip.publicUrl,
                    duration=clip.duration,
                )
            db.commit()

            progress_service.mark_render_started(session_id, job_id)
            db.commit()

            video_url = asyncio.run(render_video(session_id, clips, f"{session_id}.mp4"))
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
                db.commit()
            else:
                raise


def _coerce_clip_info(clip) -> ClipInfo:
    # 兼容字典和 Pydantic 片段对象
    if isinstance(clip, ClipInfo):
        return clip
    return ClipInfo.model_validate(clip)

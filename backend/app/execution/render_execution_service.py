import asyncio


class RenderExecutionService:
    def __init__(self, render_runner=None):
        self.render_runner = render_runner

    def execute(
        self,
        *,
        commit,
        job_state_service,
        event_service,
        artifact_service,
        step_lifecycle,
        session_id: str,
        job_id: str,
        clips,
    ) -> str:
        job_state_service.mark_render_started(session_id, job_id)
        event_service.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="render_started",
            step="rendering",
            message="开始合成视频",
            progress=80,
        )
        step_lifecycle.ensure_step(
            session_id=session_id,
            job_id=job_id,
            step_key="render_video",
            title="渲染视频",
            description="调用渲染流程，生成视频产物或失败原因。",
            sequence=8,
        )
        commit()

        render_runner = self.render_runner
        if render_runner is None:
            from backend.infrastructure.media.render_service import render_video

            render_runner = render_video

        def on_render_progress(event_type: str, message: str, progress: float) -> None:
            event_service.record_event(
                session_id=session_id,
                job_id=job_id,
                event_type=event_type,
                step="rendering",
                message=message,
                progress=progress,
            )
            commit()

        video_url = asyncio.run(
            render_runner(
                session_id,
                clips,
                f"{session_id}.mp4",
                progress_callback=on_render_progress,
            )
        )
        artifact_service.create_artifact(
            session_id=session_id,
            job_id=job_id,
            artifact_type="video",
            local_path=f"backend/output/{session_id}.mp4",
            public_url=video_url,
        )
        return video_url

import asyncio


class RenderExecutionService:
    def __init__(self, render_runner=None):
        self.render_runner = render_runner

    def execute(self, *, progress_service, session_id: str, job_id: str, clips) -> str:
        progress_service.mark_render_started(session_id, job_id)
        progress_service.db.commit()

        render_runner = self.render_runner
        if render_runner is None:
            from backend.infrastructure.media.render_service import render_video

            render_runner = render_video

        def on_render_progress(event_type: str, message: str, progress: float) -> None:
            progress_service.record_event(
                session_id=session_id,
                job_id=job_id,
                event_type=event_type,
                step="rendering",
                message=message,
                progress=progress,
            )
            progress_service.db.commit()

        video_url = asyncio.run(
            render_runner(
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
        return video_url

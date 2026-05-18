import asyncio

from backend.models.agent import ClipInfo
from backend.infrastructure.media.asset_providers.metadata import pop_clip_metadata
from backend.infrastructure.media.search_service import search_and_download_agent_clips


class AssetExecutionService:
    def __init__(self, search_runner=None):
        self.search_runner = search_runner or search_and_download_agent_clips

    def execute(self, *, progress_service, session_id: str, job_id: str, plan) -> list[ClipInfo]:
        clips = [
            self._coerce_clip_info(clip)
            for clip in asyncio.run(self.search_runner(session_id, plan.scenes))
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
        return clips

    @staticmethod
    def _coerce_clip_info(clip) -> ClipInfo:
        if isinstance(clip, ClipInfo):
            return clip
        return ClipInfo.model_validate(clip)

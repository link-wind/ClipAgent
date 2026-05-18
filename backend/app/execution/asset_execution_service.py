import asyncio

from backend.models.agent import ClipInfo
from backend.infrastructure.media.asset_providers.metadata import pop_clip_metadata
from backend.infrastructure.media.search_service import search_and_download_agent_clips


class AssetExecutionService:
    def __init__(self, search_runner=None):
        self.search_runner = search_runner or search_and_download_agent_clips

    def execute(
        self,
        *,
        job_state_service,
        artifact_service,
        step_lifecycle,
        session_id: str,
        job_id: str,
        plan,
    ) -> list[ClipInfo]:
        clips = [
            self._coerce_clip_info(clip)
            for clip in asyncio.run(self.search_runner(session_id, plan.scenes))
        ]
        if not clips:
            raise RuntimeError("没有下载到可用素材")

        clip_count = len(clips)
        job_state_service.mark_clips_ready(session_id, job_id, clip_count)
        for clip in clips:
            metadata = {
                **pop_clip_metadata(clip.localPath),
                "caption": clip.caption,
                "sourceDuration": clip.sourceDuration,
                "trimStart": clip.trimStart,
                "trimDuration": clip.trimDuration,
            }
            artifact_service.create_artifact(
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

        search_step = step_lifecycle.ensure_step(
            session_id=session_id,
            job_id=job_id,
            step_key="search_assets",
            title="搜索素材",
            description="根据最终方案搜索候选素材并记录搜索结果。",
            sequence=6,
        )
        if search_step.status != "succeeded":
            step_lifecycle.step_service.succeed_step(
                search_step.id,
                summary=f"已找到 {clip_count} 段素材",
                result={"selectedCount": clip_count},
            )

        prepare_step = step_lifecycle.ensure_step(
            session_id=session_id,
            job_id=job_id,
            step_key="prepare_assets",
            title="准备素材",
            description="下载、裁剪、整理素材，形成渲染输入。",
            sequence=7,
        )
        step_lifecycle.step_service.succeed_step(
            prepare_step.id,
            summary=f"素材已准备完成，共 {clip_count} 段",
            result={"clipCount": clip_count},
        )
        return clips

    @staticmethod
    def _coerce_clip_info(clip) -> ClipInfo:
        if isinstance(clip, ClipInfo):
            return clip
        return ClipInfo.model_validate(clip)

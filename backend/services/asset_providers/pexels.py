from backend.infrastructure.media.asset_providers import pexels as _impl
from backend.infrastructure.media.asset_providers.pexels import (
    PEXELS_REQUEST_HEADERS,
    PEXELS_VIDEO_SEARCH_URL,
    search_pexels_candidates,
    select_pexels_video_file,
)
from backend.infrastructure.media.asset_providers.types import AssetCandidate, AssetDownload


DOWNLOADS_DIR = _impl.DOWNLOADS_DIR


def _sync_patchable_exports() -> None:
    _impl.DOWNLOADS_DIR = DOWNLOADS_DIR


def download_pexels_candidate(
    session_id: str,
    candidate: AssetCandidate,
    scene_id: int,
    output_filename: str,
) -> AssetDownload:
    _sync_patchable_exports()
    return _impl.download_pexels_candidate(session_id, candidate, scene_id, output_filename)


__all__ = [
    "AssetCandidate",
    "AssetDownload",
    "DOWNLOADS_DIR",
    "PEXELS_REQUEST_HEADERS",
    "PEXELS_VIDEO_SEARCH_URL",
    "download_pexels_candidate",
    "search_pexels_candidates",
    "select_pexels_video_file",
]

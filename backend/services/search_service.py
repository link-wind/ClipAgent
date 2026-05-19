from backend.infrastructure.media import search_service as _impl
from backend.infrastructure.media.search_service import (
    AgentSceneSearchFailure,
    DOWNLOADS_DIR,
    build_download_options,
    build_scene_keywords,
    build_search_options,
    calculate_trim_window,
    collapse_provider_failure_detail,
    download_asset_candidate,
    download_fixture_candidate,
    download_pexels_candidate,
    download_video,
    get_asset_provider_order,
    get_fixture_config,
    get_pexels_config,
    get_youtube_config,
    normalize_duration,
    provider_failure_message,
    remember_clip_metadata,
    search_fixture_candidates,
    search_pexels_candidates,
    search_youtube_candidates,
    summarize_download_error,
)

_PATCHABLE_EXPORTS = [
    "DOWNLOADS_DIR",
    "build_download_options",
    "download_asset_candidate",
    "download_fixture_candidate",
    "download_pexels_candidate",
    "download_video",
    "get_asset_provider_order",
    "get_fixture_config",
    "get_pexels_config",
    "get_youtube_config",
    "remember_clip_metadata",
    "search_fixture_candidates",
    "search_pexels_candidates",
    "search_youtube_candidates",
]


def _sync_patchable_exports() -> None:
    for name in _PATCHABLE_EXPORTS:
        setattr(_impl, name, globals()[name])


def search_youtube(keywords, max_results=5):
    _sync_patchable_exports()
    return _impl.search_youtube(keywords, max_results=max_results)


def search_and_download_all(task_id, scenes, progress_start=0, progress_end=50):
    _sync_patchable_exports()
    return _impl.search_and_download_all(
        task_id,
        scenes,
        progress_start=progress_start,
        progress_end=progress_end,
    )


def search_and_download_agent_clips(session_id, scenes, progress_callback=None):
    _sync_patchable_exports()
    return _impl.search_and_download_agent_clips(
        session_id,
        scenes,
        progress_callback=progress_callback,
    )


__all__ = [
    "AgentSceneSearchFailure",
    "DOWNLOADS_DIR",
    "build_download_options",
    "build_scene_keywords",
    "build_search_options",
    "calculate_trim_window",
    "collapse_provider_failure_detail",
    "download_asset_candidate",
    "download_fixture_candidate",
    "download_pexels_candidate",
    "download_video",
    "get_asset_provider_order",
    "get_fixture_config",
    "get_pexels_config",
    "get_youtube_config",
    "normalize_duration",
    "provider_failure_message",
    "remember_clip_metadata",
    "search_and_download_agent_clips",
    "search_and_download_all",
    "search_fixture_candidates",
    "search_pexels_candidates",
    "search_youtube",
    "search_youtube_candidates",
    "summarize_download_error",
]

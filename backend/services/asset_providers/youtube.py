from collections.abc import Callable
from typing import Any

from backend.services.asset_providers.config import YoutubeProviderConfig, get_youtube_config
from backend.services.asset_providers.types import AssetCandidate


def build_youtube_search_options(config: YoutubeProviderConfig | None = None) -> dict[str, Any]:
    config = config or get_youtube_config()
    options: dict[str, Any] = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": "in_search",
        "retries": 3,
        "extractor_retries": 3,
        "fragment_retries": 3,
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:npm"],
        "extractor_args": {"youtube": {"player_client": config.player_clients}},
    }
    _apply_optional_youtube_options(options, config)
    return options


def build_youtube_download_options(
    output_path: str,
    progress_hooks: list[Callable[..., None]],
    config: YoutubeProviderConfig | None = None,
) -> dict[str, Any]:
    config = config or get_youtube_config()
    options: dict[str, Any] = {
        "format": config.format_selector,
        "merge_output_format": "mp4",
        "outtmpl": output_path,
        "quiet": True,
        "retries": 5,
        "extractor_retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "progress_hooks": progress_hooks,
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:npm"],
        "extractor_args": {"youtube": {"player_client": config.player_clients}},
    }
    _apply_optional_youtube_options(options, config)
    return options


def _apply_optional_youtube_options(options: dict[str, Any], config: YoutubeProviderConfig) -> None:
    if config.cookies_file:
        options["cookiefile"] = config.cookies_file
    if config.po_token:
        options["extractor_args"]["youtube"]["po_token"] = [config.po_token]
    if config.impersonate:
        options["impersonate"] = config.impersonate


def search_youtube_candidates(keywords: list[str], max_results: int = 5) -> list[AssetCandidate]:
    import yt_dlp

    query = " ".join(keywords)
    search_query = f"ytsearch{max_results}:{query}"
    results: list[AssetCandidate] = []
    try:
        with yt_dlp.YoutubeDL(build_youtube_search_options()) as ydl:
            search_results = ydl.extract_info(search_query, download=False)
    except Exception as exc:
        raise RuntimeError(f"素材搜索失败：{exc}") from exc

    for entry in (search_results or {}).get("entries", []):
        if not entry:
            continue
        video_id = entry.get("id", "") or ""
        results.append(
            AssetCandidate(
                provider="youtube",
                id=video_id,
                title=entry.get("title", "") or "",
                source_url=f"https://www.youtube.com/watch?v={video_id}",
                download_url=f"https://www.youtube.com/watch?v={video_id}",
                duration=entry.get("duration", 0) or 0,
                thumbnail=entry.get("thumbnail", "") or "",
                author=entry.get("channel", "") or entry.get("uploader", "") or "",
                diagnostics={"query": query},
            )
        )
    return results

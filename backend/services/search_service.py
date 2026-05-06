import asyncio
import os
import re
from typing import Dict, List, Optional

from backend.models.agent import ClipInfo as AgentClipInfo, PlanScene
from backend.models.task import Scene
from backend.services.asset_providers.config import get_asset_provider_order, get_pexels_config, get_youtube_config
from backend.services.asset_providers.metadata import remember_clip_metadata
from backend.services.asset_providers.pexels import download_pexels_candidate, search_pexels_candidates
from backend.services.asset_providers.types import AssetCandidate, AssetDownload
from backend.services.asset_providers.youtube import search_youtube_candidates

DOWNLOADS_DIR = "backend/downloads"


def normalize_duration(value: object) -> float:
    """统一时长值，避免空值和负数。"""
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, duration)


def calculate_trim_window(source_duration: float, target_duration: float) -> tuple[float, float]:
    """为长素材计算默认裁剪区间。"""
    source_duration = normalize_duration(source_duration)
    target_duration = normalize_duration(target_duration)

    if source_duration <= 0.0:
        return 0.0, 0.0
    if target_duration <= 0.0:
        return 0.0, source_duration
    if source_duration <= target_duration:
        return 0.0, source_duration

    available = source_duration - target_duration
    trim_start = max(0.0, available * 0.35)
    return trim_start, target_duration


def build_search_options() -> Dict:
    """构造 YouTube 搜索参数，降低客户端兼容问题。"""
    from backend.services.asset_providers.youtube import build_youtube_search_options

    return build_youtube_search_options()


def build_download_options(output_path: str, progress_hooks: List[callable]) -> Dict:
    """构造 YouTube 下载参数，优先选择可合并的 mp4 素材。"""
    from backend.services.asset_providers.youtube import build_youtube_download_options

    return build_youtube_download_options(output_path, progress_hooks)


def summarize_download_error(error: object) -> str:
    """把 yt-dlp 底层错误压缩成可读原因。"""
    text = str(error)
    lowered = text.lower()
    if "only images are available" in lowered or "requested format is not available" in lowered:
        return "YouTube 当前没有返回可下载视频格式，可能需要 PO Token、Cookie 或更换素材源。"
    if "po token" in lowered:
        return "YouTube 当前要求 PO Token，公开视频下载被平台策略限制。"
    if "challenge solving failed" in lowered or "signature solving failed" in lowered:
        return "YouTube 签名挑战解析失败，请确认 Node.js、yt-dlp-ejs 和 yt-dlp 都已更新。"
    return text


def search_youtube(keywords: List[str], max_results: int = 5) -> List[Dict]:
    """使用 yt-dlp 从 YouTube 搜索视频。"""
    return [candidate.to_legacy_video_info() for candidate in search_youtube_candidates(keywords, max_results=max_results)]


async def download_video(
    task_id: str,
    video_info: Dict,
    scene_id: int,
    output_filename: str,
    progress_callback: callable = None,
) -> str:
    """下载单个 YouTube 视频到 backend/downloads/。"""
    import yt_dlp
    from backend.utils.websocket import ws_manager

    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    output_path = os.path.join(DOWNLOADS_DIR, output_filename)

    def progress_hook(d):
        if d["status"] == "downloading":
            progress = d.get("_percent_str", "0%")
            if progress_callback:
                progress_callback(progress)
            asyncio.create_task(ws_manager.send_progress(task_id, -1, f"Downloading scene {scene_id}: {progress}", {}))

    ydl_opts = build_download_options(output_path, [progress_hook])

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_info["url"]])
    except Exception as e:
        raise Exception(f"Download failed: {e}")

    return output_path


async def search_and_download_all(
    task_id: str,
    scenes: List[Scene],
    progress_start: int = 0,
    progress_end: int = 50,
) -> List[Dict]:
    """搜索并下载所有场景的视频素材。"""
    from backend.utils.websocket import ws_manager

    clips = []
    total = len(scenes)

    for i, scene in enumerate(scenes):
        scene_progress_start = progress_start + (progress_end - progress_start) * i / total
        scene_progress_end = progress_start + (progress_end - progress_start) * (i + 1) / total

        await ws_manager.send_progress(task_id, scene_progress_start, f"Searching for scene {scene.id}: {scene.description[:50]}...", {})

        search_results = search_youtube(scene.keywords, max_results=3)
        if not search_results:
            await ws_manager.send_progress(task_id, scene_progress_start, f"No results for scene {scene.id}", {})
            continue

        best_video = None
        for video in search_results:
            duration = video.get("duration", 0)
            if 5 <= duration <= 30:
                best_video = video
                break

        if not best_video:
            best_video = search_results[0]

        await ws_manager.send_progress(task_id, scene_progress_start + 5, f"Downloading scene {scene.id}: {best_video['title'][:30]}...", {})

        output_filename = f"{task_id}_{scene.id}.mp4"
        try:
            await download_video(task_id, best_video, scene.id, output_filename)
            clips.append(
                {
                    "sceneId": scene.id,
                    "videoUrl": f"/downloads/{output_filename}",
                    "startTime": 0,
                    "duration": best_video.get("duration", 10),
                }
            )
        except Exception as e:
            await ws_manager.send_progress(task_id, -1, f"Failed to download scene {scene.id}: {e}", {})

    return clips


def build_scene_keywords(scene: PlanScene) -> List[str]:
    keywords = [keyword for keyword in (scene.keywords or []) if keyword]
    if keywords:
        return keywords
    return [scene.searchQuery] if scene.searchQuery else []


def provider_failure_message(provider_errors: list[tuple[str, str]]) -> str:
    if not provider_errors:
        return "没有下载到可用素材"
    summaries: list[str] = []
    grouped: dict[tuple[str, str], int] = {}
    has_specific_error = {
        provider
        for provider, message in provider_errors
        if message and message not in {"没有返回候选素材", "没有可下载候选素材"}
    }
    for provider, message in provider_errors:
        if not message:
            continue
        if provider in has_specific_error and message in {"没有返回候选素材", "没有可下载候选素材"}:
            continue
        summary = collapse_provider_failure_detail(message)
        key = (provider, summary)
        grouped[key] = grouped.get(key, 0) + 1
    for (provider, message), count in grouped.items():
        suffix = f"（{count} 次）" if count > 1 else ""
        summaries.append(f"{provider}: {message}{suffix}")
    return "；".join(summaries) if summaries else "没有下载到可用素材"


def collapse_provider_failure_detail(message: str) -> str:
    http_match = re.match(r"^(.*?HTTP\s+\d{3}(?:\s+[A-Za-z][A-Za-z-]*)?)\b", message)
    if http_match:
        return http_match.group(1).strip()
    return message


async def download_asset_candidate(
    session_id: str,
    candidate: AssetCandidate,
    scene_id: int,
    output_filename: str,
) -> AssetDownload:
    if candidate.provider == "youtube":
        local_path = await download_video(session_id, candidate.to_legacy_video_info(), scene_id, output_filename)
        return AssetDownload(
            local_path=local_path,
            public_url=f"/downloads/{output_filename}",
            metadata=candidate.to_metadata(),
        )
    if candidate.provider == "pexels":
        return download_pexels_candidate(session_id, candidate, scene_id, output_filename)
    raise RuntimeError(f"未知素材源：{candidate.provider}")


async def search_and_download_agent_clips(
    session_id: str,
    scenes: List[PlanScene],
    progress_callback: callable = None,
) -> List[AgentClipInfo]:
    """搜索并下载 Agent 场景素材，返回本地路径和公开 URL。"""
    clips: List[AgentClipInfo] = []
    provider_errors: list[tuple[str, str]] = []

    for scene in scenes:
        if progress_callback:
            progress_callback(AgentClipInfo, scene.id)

        keywords = build_scene_keywords(scene)
        for provider_name in get_asset_provider_order():
            candidates: list[AssetCandidate] | None = None
            if provider_name == "youtube":
                if not get_youtube_config().enabled:
                    continue
                try:
                    candidates = search_youtube_candidates(keywords, max_results=3)
                except Exception as exc:
                    provider_errors.append(("youtube", summarize_download_error(exc)))

            if provider_name == "pexels":
                pexels_config = get_pexels_config()
                if pexels_config.enabled and pexels_config.api_key:
                    try:
                        candidates = search_pexels_candidates(keywords, max_results=3)
                    except Exception as exc:
                        provider_errors.append(("pexels", str(exc)))
                elif pexels_config.enabled:
                    provider_errors.append(("pexels", "缺少 PEXELS_API_KEY，已跳过 Pexels 素材源"))
                    continue
            if not candidates:
                provider_errors.append((provider_name, "没有返回候选素材"))
                continue

            last_error: Optional[str] = None
            for index, candidate in enumerate(candidates, start=1):
                suffix = "" if provider_name == "youtube" and index == 1 else f"_{provider_name}_{index}"
                output_filename = f"{session_id}_{scene.id}{suffix}.mp4"
                try:
                    download = await download_asset_candidate(session_id, candidate, scene.id, output_filename)
                except Exception as exc:
                    last_error = summarize_download_error(exc)
                    continue

                source_duration = normalize_duration(candidate.duration)
                trim_start, trim_duration = calculate_trim_window(source_duration, scene.duration)
                remember_clip_metadata(download.local_path, download.metadata)
                clips.append(
                    AgentClipInfo(
                        sceneId=scene.id,
                        sourceUrl=candidate.source_url,
                        localPath=download.local_path,
                        publicUrl=download.public_url,
                        caption=scene.description,
                        startTime=0,
                        duration=scene.duration,
                        sourceDuration=source_duration,
                        trimStart=trim_start,
                        trimDuration=trim_duration,
                    )
                )
                break
            else:
                print(f"Download skipped for scene {scene.id}: {last_error or '没有可用候选素材'}")
                provider_errors.append((provider_name, last_error or "没有可下载候选素材"))
                continue
            break
        else:
            continue

    if not clips:
        raise RuntimeError(provider_failure_message(provider_errors))

    return clips

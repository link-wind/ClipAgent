import asyncio
import os
from typing import Dict, List, Optional

from backend.models.agent import ClipInfo as AgentClipInfo, PlanScene
from backend.models.task import Scene

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
    return {
        "quiet": True,
        "skip_download": True,
        "extract_flat": "in_search",
        "retries": 3,
        "extractor_retries": 3,
        "fragment_retries": 3,
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:npm"],
        "extractor_args": {
            "youtube": {
                "player_client": ["web"],
            }
        },
    }


def build_download_options(output_path: str, progress_hooks: List[callable]) -> Dict:
    """构造 YouTube 下载参数，优先选择可合并的 mp4 素材。"""
    return {
        "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
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
        "extractor_args": {
            "youtube": {
                "player_client": ["web"],
            }
        },
    }


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
    import yt_dlp

    query = " ".join(keywords)
    search_query = f"ytsearch{max_results}:{query}"
    ydl_opts = build_search_options()

    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(search_query, download=False)
            if search_results and "entries" in search_results:
                for entry in search_results["entries"]:
                    if entry:
                        results.append(
                            {
                                "id": entry.get("id", ""),
                                "title": entry.get("title", ""),
                                "url": f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                                "duration": entry.get("duration", 0) or 0,
                                "thumbnail": entry.get("thumbnail", ""),
                            }
                        )
    except Exception as e:
        raise RuntimeError(f"素材搜索失败：{e}") from e

    return results


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


async def search_and_download_agent_clips(
    session_id: str,
    scenes: List[PlanScene],
    progress_callback: callable = None,
) -> List[AgentClipInfo]:
    """搜索并下载 Agent 场景素材，返回本地路径和公开 URL。"""
    clips: List[AgentClipInfo] = []
    last_external_error: Optional[str] = None

    for scene in scenes:
        if progress_callback:
            progress_callback(AgentClipInfo, scene.id)

        keywords = scene.keywords or [scene.searchQuery]
        search_results = search_youtube(keywords, max_results=3)
        if not search_results:
            continue

        last_error: Optional[str] = None
        for index, selected_video in enumerate(search_results, start=1):
            output_filename = f"{session_id}_{scene.id}.mp4" if index == 1 else f"{session_id}_{scene.id}_{index}.mp4"
            try:
                local_path = await download_video(session_id, selected_video, scene.id, output_filename)
            except Exception as exc:
                last_error = summarize_download_error(exc)
                continue

            source_duration = normalize_duration(selected_video.get("duration", 0))
            trim_start, trim_duration = calculate_trim_window(source_duration, scene.duration)

            clips.append(
                AgentClipInfo(
                    sceneId=scene.id,
                    sourceUrl=selected_video.get("url", ""),
                    localPath=local_path,
                    publicUrl=f"/downloads/{output_filename}",
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
            if last_error:
                last_external_error = last_error

    if not clips and last_external_error:
        raise RuntimeError(last_external_error)

    return clips

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from backend.services.asset_providers.config import get_pexels_config
from backend.services.asset_providers.types import AssetCandidate, AssetDownload

DOWNLOADS_DIR = "backend/downloads"

PEXELS_VIDEO_SEARCH_URL = "https://api.pexels.com/v1/videos/search"


def search_pexels_candidates(keywords: list[str], max_results: int = 5) -> list[AssetCandidate]:
    config = get_pexels_config()
    if not config.enabled or not config.api_key:
        return []

    query = " ".join(part for part in keywords if part).strip()
    if not query:
        return []

    params = urllib.parse.urlencode(
        {
            "query": query,
            "per_page": max(1, max_results),
            "orientation": "portrait",
        }
    )
    request = urllib.request.Request(
        f"{PEXELS_VIDEO_SEARCH_URL}?{params}",
        headers={"Authorization": config.api_key},
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = getattr(response, "status", 200)
            body = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:240]
        raise RuntimeError(f"Pexels 搜索失败：HTTP {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Pexels 搜索失败：{exc.reason}") from exc

    if status >= 400:
        raise RuntimeError(f"Pexels 搜索失败：HTTP {status}")

    payload = json.loads(body.decode("utf-8"))
    candidates: list[AssetCandidate] = []
    for item in payload.get("videos", []):
        selected_file = select_pexels_video_file(item.get("video_files", []))
        if not selected_file:
            continue
        user = item.get("user") or {}
        candidates.append(
            AssetCandidate(
                provider="pexels",
                id=str(item.get("id", "")),
                title=f"Pexels video {item.get('id', '')}",
                source_url=item.get("url", "") or "",
                download_url=selected_file.get("link", "") or "",
                duration=item.get("duration", 0) or 0,
                width=selected_file.get("width") or item.get("width"),
                height=selected_file.get("height") or item.get("height"),
                thumbnail=item.get("image", "") or "",
                author=user.get("name", "") or "",
                diagnostics={
                    "query": query,
                    "authorUrl": user.get("url", "") or "",
                    "selectedFileId": selected_file.get("id"),
                    "selectedQuality": selected_file.get("quality"),
                },
            )
        )
    return candidates


def select_pexels_video_file(video_files: list[dict[str, Any]]) -> dict[str, Any]:
    mp4_files = [item for item in video_files if item.get("file_type") == "video/mp4" and item.get("link")]
    if not mp4_files:
        return {}

    def score(item: dict[str, Any]) -> tuple[int, int, int]:
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        is_vertical = height >= width and height > 0
        bounded = height <= 1280 if height else False
        resolution = height or width
        return (0 if is_vertical else 1, 0 if bounded else 1, resolution)

    return sorted(mp4_files, key=score)[0]


def download_pexels_candidate(
    session_id: str,
    candidate: AssetCandidate,
    scene_id: int,
    output_filename: str,
) -> AssetDownload:
    del session_id, scene_id

    if not candidate.download_url:
        raise RuntimeError("Pexels 下载失败：候选素材缺少下载链接")

    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    output_path = os.path.join(DOWNLOADS_DIR, output_filename)
    request = urllib.request.Request(candidate.download_url, headers={"User-Agent": "ClipForge/1.0"})

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = getattr(response, "status", 200)
            data = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:240]
        raise RuntimeError(f"Pexels 下载失败：HTTP {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Pexels 下载失败：{exc.reason}") from exc

    if status >= 400:
        raise RuntimeError(f"Pexels 下载失败：HTTP {status}")
    if not data:
        raise RuntimeError("Pexels 下载失败：返回了空文件")

    with open(output_path, "wb") as output_file:
        output_file.write(data)

    return AssetDownload(
        local_path=output_path,
        public_url=f"/downloads/{output_filename}",
        metadata=candidate.to_metadata(),
    )

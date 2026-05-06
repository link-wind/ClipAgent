import json
import os
import shutil
from pathlib import Path

from backend.services.asset_providers.config import get_fixture_config
from backend.services.asset_providers.types import AssetCandidate, AssetDownload


ROOT_DIR = Path(__file__).resolve().parents[3]
DOWNLOADS_DIR = "backend/downloads"


def load_fixture_library() -> list[dict]:
    config = get_fixture_config()
    library_path = ROOT_DIR / config.library_path
    with library_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_fixture_tokens(text: str) -> list[str]:
    return [part.strip() for part in text.split() if part.strip()]


def build_fixture_text(entry: dict) -> str:
    title = entry.get("title", "") or ""
    description = entry.get("description", "") or ""
    tags = entry.get("tags") or []
    return " ".join([title, description, *[str(tag) for tag in tags]])


def build_matched_keywords(entry_tokens: list[str], keywords: list[str]) -> list[str]:
    return [
        keyword
        for keyword in keywords
        if keyword and any(keyword in token for token in entry_tokens)
    ]


def score_fixture_entry(entry, keywords) -> int:
    entry_tokens = normalize_fixture_tokens(build_fixture_text(entry))
    return len(build_matched_keywords(entry_tokens, keywords))


def search_fixture_candidates(keywords, max_results=5) -> list[AssetCandidate]:
    normalized_keywords = []
    for keyword in keywords:
        normalized_keywords.extend(normalize_fixture_tokens(str(keyword)))

    if not normalized_keywords:
        return []

    scored_entries: list[tuple[int, dict]] = []
    for entry in load_fixture_library():
        score = score_fixture_entry(entry, normalized_keywords)
        if score > 0:
            scored_entries.append((score, entry))

    scored_entries.sort(key=lambda item: item[0], reverse=True)

    candidates: list[AssetCandidate] = []
    for score, entry in scored_entries[:max(0, max_results)]:
        entry_tokens = normalize_fixture_tokens(build_fixture_text(entry))
        matched_keywords = build_matched_keywords(entry_tokens, normalized_keywords)
        video_url = entry.get("videoUrl", "") or ""
        candidates.append(
            AssetCandidate(
                provider="fixture",
                id=entry.get("id", "") or "",
                title=entry.get("title", "") or "",
                source_url=video_url,
                download_url=video_url,
                duration=entry.get("duration", 0) or 0,
                thumbnail=entry.get("thumbnailUrl", "") or "",
                diagnostics={
                    "score": score,
                    "matchedKeywords": matched_keywords,
                },
            )
        )
    return candidates


def resolve_fixture_source_path(source_url: str) -> Path:
    relative_path = source_url.lstrip("/")
    return ROOT_DIR / relative_path


def download_fixture_candidate(
    session_id: str,
    candidate: AssetCandidate,
    scene_id: int,
    output_filename: str,
) -> AssetDownload:
    del session_id, scene_id

    source_url = candidate.download_url or candidate.source_url
    if not source_url:
        raise RuntimeError("Fixture 下载失败：候选素材缺少本地文件路径")

    source_path = resolve_fixture_source_path(source_url)
    if not source_path.is_file():
        raise RuntimeError(f"Fixture 下载失败：本地素材文件不存在: {source_path}")

    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    output_path = os.path.join(DOWNLOADS_DIR, output_filename)
    shutil.copyfile(source_path, output_path)

    return AssetDownload(
        local_path=output_path,
        public_url=f"/downloads/{output_filename}",
        metadata=candidate.to_metadata(),
    )

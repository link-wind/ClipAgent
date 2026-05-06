import json
from pathlib import Path

from backend.services.asset_providers.config import get_fixture_config
from backend.services.asset_providers.types import AssetCandidate


ROOT_DIR = Path(__file__).resolve().parents[3]


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

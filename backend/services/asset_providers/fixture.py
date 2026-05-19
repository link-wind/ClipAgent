from pathlib import Path

from backend.infrastructure.media.asset_providers import fixture as _impl
from backend.infrastructure.media.asset_providers.fixture import (
    build_fixture_text,
    build_matched_keywords,
    normalize_fixture_tokens,
    score_fixture_entry,
)
from backend.infrastructure.media.asset_providers.types import AssetCandidate, AssetDownload


ROOT_DIR = _impl.ROOT_DIR
DOWNLOADS_DIR = _impl.DOWNLOADS_DIR
probe_fixture_duration = _impl.probe_fixture_duration


def _sync_patchable_exports() -> None:
    _impl.ROOT_DIR = ROOT_DIR
    _impl.DOWNLOADS_DIR = DOWNLOADS_DIR
    _impl.probe_fixture_duration = probe_fixture_duration


def load_fixture_library() -> list[dict]:
    _sync_patchable_exports()
    return _impl.load_fixture_library()


def search_fixture_candidates(keywords, max_results=5) -> list[AssetCandidate]:
    _sync_patchable_exports()
    return _impl.search_fixture_candidates(keywords, max_results=max_results)


def resolve_fixture_source_path(source_url: str) -> Path:
    _sync_patchable_exports()
    return _impl.resolve_fixture_source_path(source_url)


def download_fixture_candidate(
    session_id: str,
    candidate: AssetCandidate,
    scene_id: int,
    output_filename: str,
) -> AssetDownload:
    _sync_patchable_exports()
    return _impl.download_fixture_candidate(session_id, candidate, scene_id, output_filename)


__all__ = [
    "AssetCandidate",
    "AssetDownload",
    "DOWNLOADS_DIR",
    "ROOT_DIR",
    "build_fixture_text",
    "build_matched_keywords",
    "download_fixture_candidate",
    "load_fixture_library",
    "normalize_fixture_tokens",
    "probe_fixture_duration",
    "resolve_fixture_source_path",
    "score_fixture_entry",
    "search_fixture_candidates",
]

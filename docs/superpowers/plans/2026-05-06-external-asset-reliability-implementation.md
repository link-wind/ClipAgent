# External Asset Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the existing YouTube yt-dlp path and add Pexels fallback so real `/workspace` worker runs can search/download external footage and render MP4s more reliably.

**Architecture:** Split external asset handling into small provider modules under `backend/services/asset_providers/`. Keep public rendering inputs as `ClipInfo`, attach provider metadata through a lightweight sidecar registry, and let `search_and_download_agent_clips(...)` orchestrate YouTube first, then Pexels. Preserve existing YouTube behavior when no new environment variables are set.

**Tech Stack:** Python 3, FastAPI/Celery backend, `yt-dlp`, `urllib.request`, Pydantic models, SQLAlchemy artifact metadata, unittest/AsyncMock, Next.js build checks.

---

## File Structure

- Create `backend/services/asset_providers/__init__.py`
  - Exports shared provider types and provider helpers.
- Create `backend/services/asset_providers/types.py`
  - Owns `AssetCandidate`, `AssetDownload`, `ProviderDiagnostic`, and `ProviderResult`.
- Create `backend/services/asset_providers/config.py`
  - Reads provider environment variables and builds safe config values.
- Create `backend/services/asset_providers/youtube.py`
  - Owns yt-dlp option construction, YouTube search, and YouTube download.
- Create `backend/services/asset_providers/pexels.py`
  - Owns Pexels API search, candidate normalization, file selection, and direct MP4 download.
- Create `backend/services/asset_providers/metadata.py`
  - Owns a tiny in-memory sidecar for clip provider metadata keyed by `localPath`.
- Modify `backend/services/search_service.py`
  - Keep compatibility wrappers for existing tests and older code, but delegate provider work to new modules.
  - Convert `search_and_download_agent_clips(...)` into provider orchestration.
- Modify `backend/tasks/agent_tasks.py`
  - Include provider metadata when creating clip artifacts.
- Modify `.env.example`
  - Document provider environment variables.
- Modify `README.md`
  - Document YouTube hardening, Pexels setup, provider toggles, and diagnostics.
- Modify `tests/test_agent_backend.py`
  - Add provider config, YouTube option, Pexels, and orchestration tests.
- Modify `tests/test_agent_jobs.py`
  - Add artifact metadata persistence test and keep trim/caption tests passing.

Use `urllib.request` for Pexels HTTP to avoid adding a runtime dependency. Tests must mock network boundaries and must not call Pexels or YouTube.

## Task 1: Shared Provider Types And Metadata Sidecar

**Files:**
- Create: `backend/services/asset_providers/__init__.py`
- Create: `backend/services/asset_providers/types.py`
- Create: `backend/services/asset_providers/metadata.py`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Add failing tests for shared provider types and metadata**

Append these tests inside the existing backend test class that already covers search service behavior in `tests/test_agent_backend.py`:

```python
    def test_asset_candidate_exposes_legacy_video_info(self):
        from backend.services.asset_providers.types import AssetCandidate

        candidate = AssetCandidate(
            provider="youtube",
            id="abc123",
            title="Demo",
            source_url="https://www.youtube.com/watch?v=abc123",
            download_url="https://www.youtube.com/watch?v=abc123",
            duration=12.5,
            thumbnail="https://example.com/thumb.jpg",
            author="Clip Channel",
            diagnostics={"client": "web"},
        )

        self.assertEqual(
            candidate.to_legacy_video_info(),
            {
                "id": "abc123",
                "title": "Demo",
                "url": "https://www.youtube.com/watch?v=abc123",
                "duration": 12.5,
                "thumbnail": "https://example.com/thumb.jpg",
                "provider": "youtube",
                "downloadUrl": "https://www.youtube.com/watch?v=abc123",
                "author": "Clip Channel",
                "diagnostics": {"client": "web"},
            },
        )

    def test_clip_metadata_sidecar_round_trips_by_local_path(self):
        from backend.services.asset_providers.metadata import pop_clip_metadata, remember_clip_metadata

        remember_clip_metadata(
            "backend/downloads/session_1.mp4",
            {
                "provider": "pexels",
                "providerId": "42",
                "author": "Pexels Creator",
            },
        )

        self.assertEqual(
            pop_clip_metadata("backend/downloads/session_1.mp4"),
            {
                "provider": "pexels",
                "providerId": "42",
                "author": "Pexels Creator",
            },
        )
        self.assertEqual(pop_clip_metadata("backend/downloads/session_1.mp4"), {})
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_asset_candidate_exposes_legacy_video_info \
  tests.test_agent_backend.AgentExecutionContractTests.test_clip_metadata_sidecar_round_trips_by_local_path -v
```

Expected: fail with `ModuleNotFoundError: No module named 'backend.services.asset_providers'`.

- [ ] **Step 3: Create provider package exports**

Create `backend/services/asset_providers/__init__.py`:

```python
from backend.services.asset_providers.types import AssetCandidate, AssetDownload, ProviderDiagnostic, ProviderResult

__all__ = [
    "AssetCandidate",
    "AssetDownload",
    "ProviderDiagnostic",
    "ProviderResult",
]
```

- [ ] **Step 4: Create shared provider types**

Create `backend/services/asset_providers/types.py`:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderDiagnostic:
    provider: str
    phase: str
    message: str
    retryable: bool = True

    def to_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "phase": self.phase,
            "message": self.message,
            "retryable": self.retryable,
        }


@dataclass(frozen=True)
class AssetCandidate:
    provider: str
    id: str
    title: str
    source_url: str
    download_url: str = ""
    duration: float = 0.0
    width: int | None = None
    height: int | None = None
    thumbnail: str = ""
    author: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_legacy_video_info(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.source_url,
            "duration": self.duration,
            "thumbnail": self.thumbnail,
            "provider": self.provider,
            "downloadUrl": self.download_url,
            "author": self.author,
            "diagnostics": self.diagnostics,
        }

    def to_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "provider": self.provider,
            "providerId": self.id,
            "title": self.title,
            "sourceUrl": self.source_url,
        }
        if self.download_url:
            metadata["downloadUrl"] = self.download_url
        if self.width is not None:
            metadata["width"] = self.width
        if self.height is not None:
            metadata["height"] = self.height
        if self.thumbnail:
            metadata["thumbnail"] = self.thumbnail
        if self.author:
            metadata["author"] = self.author
        if self.diagnostics:
            metadata["diagnostics"] = self.diagnostics
        return metadata


@dataclass(frozen=True)
class AssetDownload:
    local_path: str
    public_url: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    candidates: list[AssetCandidate] = field(default_factory=list)
    diagnostics: list[ProviderDiagnostic] = field(default_factory=list)
```

- [ ] **Step 5: Create clip metadata sidecar**

Create `backend/services/asset_providers/metadata.py`:

```python
from typing import Any

_CLIP_METADATA_BY_LOCAL_PATH: dict[str, dict[str, Any]] = {}


def remember_clip_metadata(local_path: str, metadata: dict[str, Any]) -> None:
    if not local_path or not metadata:
        return
    _CLIP_METADATA_BY_LOCAL_PATH[local_path] = dict(metadata)


def pop_clip_metadata(local_path: str) -> dict[str, Any]:
    if not local_path:
        return {}
    return _CLIP_METADATA_BY_LOCAL_PATH.pop(local_path, {})
```

- [ ] **Step 6: Run tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_asset_candidate_exposes_legacy_video_info \
  tests.test_agent_backend.AgentExecutionContractTests.test_clip_metadata_sidecar_round_trips_by_local_path -v
```

Expected: both tests pass.

- [ ] **Step 7: Commit Task 1**

```bash
git add backend/services/asset_providers tests/test_agent_backend.py
git commit -m "feat: add asset provider shared types"
```

## Task 2: Provider Configuration And YouTube Option Hardening

**Files:**
- Create: `backend/services/asset_providers/config.py`
- Create: `backend/services/asset_providers/youtube.py`
- Modify: `backend/services/search_service.py`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Add failing tests for provider config and YouTube options**

Replace the existing expectations in `test_youtube_options_avoid_po_token_clients_and_enable_node_ejs` and add two new tests near the existing YouTube option tests:

```python
    def test_youtube_options_avoid_po_token_clients_and_enable_node_ejs(self):
        from backend.services.search_service import build_download_options, build_search_options

        search_options = build_search_options()
        download_options = build_download_options("backend/downloads/example.mp4", [])

        self.assertEqual(search_options["extractor_args"]["youtube"]["player_client"], ["mweb", "web_safari", "web"])
        self.assertEqual(download_options["extractor_args"]["youtube"]["player_client"], ["mweb", "web_safari", "web"])
        self.assertEqual(download_options["js_runtimes"], {"node": {}})
        self.assertIn("ejs:npm", download_options["remote_components"])

    def test_youtube_options_use_hardening_environment(self):
        from backend.services.search_service import build_download_options, build_search_options

        with patch.dict(
            "os.environ",
            {
                "YTDLP_COOKIES_FILE": "/tmp/youtube.cookies.txt",
                "YTDLP_PLAYER_CLIENTS": "mweb,web",
                "YTDLP_PO_TOKEN": "web.gvs+token-value",
                "YTDLP_IMPERSONATE": "chrome",
                "YTDLP_FORMAT": "best[height<=480][ext=mp4]",
            },
            clear=False,
        ):
            search_options = build_search_options()
            download_options = build_download_options("backend/downloads/example.mp4", [])

        self.assertEqual(search_options["cookiefile"], "/tmp/youtube.cookies.txt")
        self.assertEqual(download_options["cookiefile"], "/tmp/youtube.cookies.txt")
        self.assertEqual(search_options["extractor_args"]["youtube"]["player_client"], ["mweb", "web"])
        self.assertEqual(download_options["extractor_args"]["youtube"]["player_client"], ["mweb", "web"])
        self.assertEqual(search_options["extractor_args"]["youtube"]["po_token"], ["web.gvs+token-value"])
        self.assertEqual(download_options["extractor_args"]["youtube"]["po_token"], ["web.gvs+token-value"])
        self.assertEqual(search_options["impersonate"], "chrome")
        self.assertEqual(download_options["impersonate"], "chrome")
        self.assertEqual(download_options["format"], "best[height<=480][ext=mp4]")

    def test_provider_boolean_env_parsing(self):
        from backend.services.asset_providers.config import env_flag

        with patch.dict("os.environ", {"YTDLP_PROVIDER_ENABLED": "false", "PEXELS_PROVIDER_ENABLED": "1"}, clear=False):
            self.assertFalse(env_flag("YTDLP_PROVIDER_ENABLED", default=True))
            self.assertTrue(env_flag("PEXELS_PROVIDER_ENABLED", default=False))
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_youtube_options_avoid_po_token_clients_and_enable_node_ejs \
  tests.test_agent_backend.AgentExecutionContractTests.test_youtube_options_use_hardening_environment \
  tests.test_agent_backend.AgentExecutionContractTests.test_provider_boolean_env_parsing -v
```

Expected: fail because defaults and config module are not implemented.

- [ ] **Step 3: Create provider config helpers**

Create `backend/services/asset_providers/config.py`:

```python
import os
from dataclasses import dataclass

DEFAULT_YTDLP_FORMAT = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]"


def env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"0", "false", "no", "off", ""}


def env_csv(name: str, default: list[str]) -> list[str]:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return list(default)
    values = [part.strip() for part in raw_value.split(",") if part.strip()]
    return values or list(default)


@dataclass(frozen=True)
class YoutubeProviderConfig:
    enabled: bool
    cookies_file: str
    player_clients: list[str]
    po_token: str
    impersonate: str
    format_selector: str


@dataclass(frozen=True)
class PexelsProviderConfig:
    enabled: bool
    api_key: str


def get_youtube_config() -> YoutubeProviderConfig:
    return YoutubeProviderConfig(
        enabled=env_flag("YTDLP_PROVIDER_ENABLED", default=True),
        cookies_file=os.environ.get("YTDLP_COOKIES_FILE", "").strip(),
        player_clients=env_csv("YTDLP_PLAYER_CLIENTS", ["mweb", "web_safari", "web"]),
        po_token=os.environ.get("YTDLP_PO_TOKEN", "").strip(),
        impersonate=os.environ.get("YTDLP_IMPERSONATE", "").strip(),
        format_selector=os.environ.get("YTDLP_FORMAT", DEFAULT_YTDLP_FORMAT).strip() or DEFAULT_YTDLP_FORMAT,
    )


def get_pexels_config() -> PexelsProviderConfig:
    api_key = os.environ.get("PEXELS_API_KEY", "").strip()
    return PexelsProviderConfig(
        enabled=env_flag("PEXELS_PROVIDER_ENABLED", default=bool(api_key)),
        api_key=api_key,
    )
```

- [ ] **Step 4: Create YouTube provider option helpers and wrappers**

Create `backend/services/asset_providers/youtube.py`:

```python
from typing import Any, Callable

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
    progress_hooks: list[Callable],
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
```

- [ ] **Step 5: Delegate existing search service option functions**

In `backend/services/search_service.py`, replace `build_search_options()` and `build_download_options(...)` with:

```python
def build_search_options() -> Dict:
    """构造 YouTube 搜索参数，降低客户端兼容问题。"""
    from backend.services.asset_providers.youtube import build_youtube_search_options

    return build_youtube_search_options()


def build_download_options(output_path: str, progress_hooks: List[callable]) -> Dict:
    """构造 YouTube 下载参数，优先选择可合并的 mp4 素材。"""
    from backend.services.asset_providers.youtube import build_youtube_download_options

    return build_youtube_download_options(output_path, progress_hooks)
```

- [ ] **Step 6: Delegate `search_youtube(...)` through YouTube provider candidates**

In `backend/services/search_service.py`, replace the body of `search_youtube(...)` with:

```python
def search_youtube(keywords: List[str], max_results: int = 5) -> List[Dict]:
    """使用 yt-dlp 从 YouTube 搜索视频。"""
    from backend.services.asset_providers.youtube import search_youtube_candidates

    return [candidate.to_legacy_video_info() for candidate in search_youtube_candidates(keywords, max_results=max_results)]
```

- [ ] **Step 7: Run tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_youtube_options_use_current_clients_and_retry_settings \
  tests.test_agent_backend.AgentExecutionContractTests.test_youtube_options_avoid_po_token_clients_and_enable_node_ejs \
  tests.test_agent_backend.AgentExecutionContractTests.test_youtube_options_use_hardening_environment \
  tests.test_agent_backend.AgentExecutionContractTests.test_provider_boolean_env_parsing \
  tests.test_agent_backend.AgentExecutionContractTests.test_youtube_search_surfaces_external_error -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit Task 2**

```bash
git add backend/services/asset_providers/config.py backend/services/asset_providers/youtube.py backend/services/search_service.py tests/test_agent_backend.py
git commit -m "feat: harden youtube provider options"
```

## Task 3: Pexels Provider Search And File Selection

**Files:**
- Create: `backend/services/asset_providers/pexels.py`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Add failing Pexels search and selection tests**

Add these tests near the provider tests in `tests/test_agent_backend.py`:

```python
    def test_pexels_search_maps_api_response_to_candidates(self):
        import json
        from unittest.mock import MagicMock

        from backend.services.asset_providers.pexels import search_pexels_candidates

        response_payload = {
            "videos": [
                {
                    "id": 101,
                    "url": "https://www.pexels.com/video/demo-101/",
                    "duration": 9,
                    "width": 1080,
                    "height": 1920,
                    "image": "https://images.pexels.com/videos/101/thumb.jpg",
                    "user": {"name": "Pexels Creator", "url": "https://www.pexels.com/@creator"},
                    "video_files": [
                        {
                            "id": 1,
                            "quality": "hd",
                            "file_type": "video/mp4",
                            "width": 720,
                            "height": 1280,
                            "link": "https://videos.pexels.com/video-files/101/portrait.mp4",
                        }
                    ],
                }
            ]
        }
        fake_response = MagicMock()
        fake_response.status = 200
        fake_response.read.return_value = json.dumps(response_payload).encode("utf-8")
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = None

        with patch.dict("os.environ", {"PEXELS_API_KEY": "pexels-key"}, clear=False), patch(
            "urllib.request.urlopen",
            return_value=fake_response,
        ) as mock_urlopen:
            candidates = search_pexels_candidates(["product", "demo"], max_results=3)

        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.headers["Authorization"], "pexels-key")
        self.assertIn("/v1/videos/search", request.full_url)
        self.assertIn("orientation=portrait", request.full_url)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].provider, "pexels")
        self.assertEqual(candidates[0].id, "101")
        self.assertEqual(candidates[0].source_url, "https://www.pexels.com/video/demo-101/")
        self.assertEqual(candidates[0].download_url, "https://videos.pexels.com/video-files/101/portrait.mp4")
        self.assertEqual(candidates[0].author, "Pexels Creator")

    def test_pexels_selects_vertical_mp4_with_bounded_resolution(self):
        from backend.services.asset_providers.pexels import select_pexels_video_file

        selected = select_pexels_video_file(
            [
                {"file_type": "video/mp4", "width": 3840, "height": 2160, "link": "landscape-4k.mp4"},
                {"file_type": "video/mp4", "width": 720, "height": 1280, "link": "portrait-720.mp4"},
                {"file_type": "video/webm", "width": 720, "height": 1280, "link": "portrait.webm"},
            ]
        )

        self.assertEqual(selected["link"], "portrait-720.mp4")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_pexels_search_maps_api_response_to_candidates \
  tests.test_agent_backend.AgentExecutionContractTests.test_pexels_selects_vertical_mp4_with_bounded_resolution -v
```

Expected: fail because `pexels.py` does not exist.

- [ ] **Step 3: Create Pexels provider**

Create `backend/services/asset_providers/pexels.py`:

```python
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from backend.services.asset_providers.config import get_pexels_config
from backend.services.asset_providers.types import AssetCandidate

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
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_pexels_search_maps_api_response_to_candidates \
  tests.test_agent_backend.AgentExecutionContractTests.test_pexels_selects_vertical_mp4_with_bounded_resolution -v
```

Expected: both tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add backend/services/asset_providers/pexels.py tests/test_agent_backend.py
git commit -m "feat: add pexels asset search"
```

## Task 4: Pexels Direct Download

**Files:**
- Modify: `backend/services/asset_providers/pexels.py`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Add failing Pexels direct download test**

Add this test in `tests/test_agent_backend.py`:

```python
    def test_pexels_direct_download_writes_mp4(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import MagicMock

        from backend.services.asset_providers.pexels import download_pexels_candidate
        from backend.services.asset_providers.types import AssetCandidate

        candidate = AssetCandidate(
            provider="pexels",
            id="101",
            title="Pexels video 101",
            source_url="https://www.pexels.com/video/demo-101/",
            download_url="https://videos.pexels.com/video-files/101/portrait.mp4",
            duration=9,
            width=720,
            height=1280,
            author="Pexels Creator",
        )
        fake_response = MagicMock()
        fake_response.status = 200
        fake_response.read.return_value = b"\x00\x00\x00\x18ftypmp42video-bytes"
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = None

        with TemporaryDirectory() as tmp_dir, patch(
            "backend.services.asset_providers.pexels.DOWNLOADS_DIR",
            tmp_dir,
        ), patch("urllib.request.urlopen", return_value=fake_response):
            download = download_pexels_candidate("session", candidate, scene_id=4, output_filename="session_4.mp4")

            output_path = Path(tmp_dir) / "session_4.mp4"
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), b"\x00\x00\x00\x18ftypmp42video-bytes")
            self.assertEqual(download.local_path, str(output_path))
            self.assertEqual(download.public_url, "/downloads/session_4.mp4")
            self.assertEqual(download.metadata["provider"], "pexels")
            self.assertEqual(download.metadata["author"], "Pexels Creator")
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_pexels_direct_download_writes_mp4 -v
```

Expected: fail because `download_pexels_candidate` is missing.

- [ ] **Step 3: Implement direct download**

Append to `backend/services/asset_providers/pexels.py`:

```python
import os

from backend.services.asset_providers.types import AssetDownload


def download_pexels_candidate(
    session_id: str,
    candidate: AssetCandidate,
    scene_id: int,
    output_filename: str,
) -> AssetDownload:
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
```

- [ ] **Step 4: Run test and verify it passes**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_pexels_direct_download_writes_mp4 -v
```

Expected: pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add backend/services/asset_providers/pexels.py tests/test_agent_backend.py
git commit -m "feat: download pexels clips"
```

## Task 5: Provider Orchestration In Search Service

**Files:**
- Modify: `backend/services/search_service.py`
- Modify: `backend/services/asset_providers/youtube.py`
- Modify: `backend/services/asset_providers/pexels.py`
- Test: `tests/test_agent_backend.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Add failing orchestration tests**

Update existing search/download tests in `tests/test_agent_backend.py` to patch provider functions instead of legacy wrappers where needed, and add these tests:

```python
    def test_agent_download_falls_back_from_youtube_search_failure_to_pexels(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service
        from backend.services.asset_providers.types import AssetCandidate, AssetDownload

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )
        pexels_candidate = AssetCandidate(
            provider="pexels",
            id="101",
            title="Pexels video 101",
            source_url="https://www.pexels.com/video/demo-101/",
            download_url="https://videos.pexels.com/101.mp4",
            duration=14,
            author="Pexels Creator",
        )

        with patch("backend.services.search_service.search_youtube_candidates") as mock_youtube_search, patch(
            "backend.services.search_service.search_pexels_candidates",
        ) as mock_pexels_search, patch(
            "backend.services.search_service.download_pexels_candidate",
        ) as mock_pexels_download:
            mock_youtube_search.side_effect = RuntimeError("素材搜索失败：Sign in to confirm you’re not a bot.")
            mock_pexels_search.return_value = [pexels_candidate]
            mock_pexels_download.return_value = AssetDownload(
                local_path="backend/downloads/session_3.mp4",
                public_url="/downloads/session_3.mp4",
                metadata=pexels_candidate.to_metadata(),
            )

            clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].sourceUrl, "https://www.pexels.com/video/demo-101/")
        self.assertEqual(clips[0].localPath, "backend/downloads/session_3.mp4")

    def test_agent_download_falls_back_from_youtube_download_failure_to_pexels(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service
        from backend.services.asset_providers.types import AssetCandidate, AssetDownload

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )
        youtube_candidate = AssetCandidate(
            provider="youtube",
            id="bad",
            title="Bad",
            source_url="https://www.youtube.com/watch?v=bad",
            download_url="https://www.youtube.com/watch?v=bad",
            duration=12,
        )
        pexels_candidate = AssetCandidate(
            provider="pexels",
            id="101",
            title="Pexels video 101",
            source_url="https://www.pexels.com/video/demo-101/",
            download_url="https://videos.pexels.com/101.mp4",
            duration=14,
        )

        with patch("backend.services.search_service.search_youtube_candidates", return_value=[youtube_candidate]), patch(
            "backend.services.search_service.download_video",
            side_effect=Exception("Download failed: YouTube 当前要求 PO Token"),
        ), patch(
            "backend.services.search_service.search_pexels_candidates",
            return_value=[pexels_candidate],
        ), patch(
            "backend.services.search_service.download_pexels_candidate",
            return_value=AssetDownload(
                local_path="backend/downloads/session_3_pexels_1.mp4",
                public_url="/downloads/session_3_pexels_1.mp4",
                metadata=pexels_candidate.to_metadata(),
            ),
        ):
            clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].sourceUrl, "https://www.pexels.com/video/demo-101/")
        self.assertEqual(clips[0].publicUrl, "/downloads/session_3_pexels_1.mp4")

    def test_all_provider_failure_surfaces_safe_summaries(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )

        with patch("backend.services.search_service.search_youtube_candidates") as mock_youtube_search, patch(
            "backend.services.search_service.search_pexels_candidates",
        ) as mock_pexels_search:
            mock_youtube_search.side_effect = RuntimeError("素材搜索失败：Sign in to confirm you’re not a bot.")
            mock_pexels_search.side_effect = RuntimeError("Pexels 搜索失败：HTTP 401 Unauthorized")

            with self.assertRaisesRegex(RuntimeError, "youtube.*Sign in.*pexels.*401"):
                asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_download_falls_back_from_youtube_search_failure_to_pexels \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_download_falls_back_from_youtube_download_failure_to_pexels \
  tests.test_agent_backend.AgentExecutionContractTests.test_all_provider_failure_surfaces_safe_summaries -v
```

Expected: fail because search service does not import or orchestrate providers yet.

- [ ] **Step 3: Add imports to search service**

At the top of `backend/services/search_service.py`, add:

```python
from backend.services.asset_providers.config import get_pexels_config, get_youtube_config
from backend.services.asset_providers.metadata import remember_clip_metadata
from backend.services.asset_providers.pexels import download_pexels_candidate, search_pexels_candidates
from backend.services.asset_providers.types import AssetCandidate, AssetDownload
from backend.services.asset_providers.youtube import search_youtube_candidates
```

- [ ] **Step 4: Add provider helper functions to search service**

Insert these helpers above `search_and_download_agent_clips(...)`:

```python
def build_scene_keywords(scene: PlanScene) -> List[str]:
    keywords = [keyword for keyword in (scene.keywords or []) if keyword]
    if keywords:
        return keywords
    return [scene.searchQuery] if scene.searchQuery else []


def provider_failure_message(provider_errors: list[tuple[str, str]]) -> str:
    if not provider_errors:
        return "没有下载到可用素材"
    return "；".join(f"{provider}: {message}" for provider, message in provider_errors if message)


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
```

- [ ] **Step 5: Replace agent clip orchestration**

Replace `search_and_download_agent_clips(...)` in `backend/services/search_service.py` with:

```python
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
        provider_candidates: list[tuple[str, list[AssetCandidate]]] = []

        if get_youtube_config().enabled:
            try:
                provider_candidates.append(("youtube", search_youtube_candidates(keywords, max_results=3)))
            except Exception as exc:
                provider_errors.append(("youtube", summarize_download_error(exc)))

        pexels_config = get_pexels_config()
        if pexels_config.enabled and pexels_config.api_key:
            try:
                provider_candidates.append(("pexels", search_pexels_candidates(keywords, max_results=3)))
            except Exception as exc:
                provider_errors.append(("pexels", str(exc)))
        elif pexels_config.enabled:
            provider_errors.append(("pexels", "缺少 PEXELS_API_KEY，已跳过 Pexels 素材源"))

        for provider_name, candidates in provider_candidates:
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
                provider_errors.append((provider_name, last_error or "没有可下载候选素材"))
                continue
            break

    if not clips:
        raise RuntimeError(provider_failure_message(provider_errors))

    return clips
```

- [ ] **Step 6: Update legacy tests to patch provider search**

In existing tests that currently patch `backend.services.search_service.search_youtube` for `search_and_download_agent_clips(...)`, change the patch to `backend.services.search_service.search_youtube_candidates` and return `AssetCandidate` objects.

Example replacement:

```python
from backend.services.asset_providers.types import AssetCandidate

mock_search.return_value = [
    AssetCandidate(
        provider="youtube",
        id="abc123",
        title="Product detail",
        source_url="https://www.youtube.com/watch?v=abc123",
        download_url="https://www.youtube.com/watch?v=abc123",
        duration=12,
    )
]
```

Keep `search_youtube(...)` tests patched against `yt_dlp.YoutubeDL`.

- [ ] **Step 7: Run targeted orchestration and existing clip tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_search_download_returns_agent_clip_paths \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_download_tries_next_search_result_after_youtube_failure \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_download_failure_surfaces_last_external_error \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_search_failure_surfaces_external_error \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_download_falls_back_from_youtube_search_failure_to_pexels \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_download_falls_back_from_youtube_download_failure_to_pexels \
  tests.test_agent_backend.AgentExecutionContractTests.test_all_provider_failure_surfaces_safe_summaries \
  tests.test_agent_jobs.SearchClipAssemblyTests.test_search_and_download_agent_clips_populates_trim_metadata \
  tests.test_agent_jobs.SearchClipAssemblyTests.test_search_and_download_agent_clips_populates_caption -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit Task 5**

```bash
git add backend/services/search_service.py backend/services/asset_providers tests/test_agent_backend.py tests/test_agent_jobs.py
git commit -m "feat: orchestrate external asset providers"
```

## Task 6: Persist Provider Metadata In Clip Artifacts

**Files:**
- Modify: `backend/tasks/agent_tasks.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Add failing artifact metadata test**

Add this test next to the existing artifact metadata tests in `tests/test_agent_jobs.py`:

```python
    def test_run_agent_job_persists_provider_metadata_in_artifacts(self):
        from backend.db.repositories import AgentArtifactRepository
        from backend.services.asset_providers.metadata import remember_clip_metadata
        from backend.tasks.agent_tasks import run_agent_job

        session_id, job_id = self._create_queued_job()

        async def fake_search_runner(_session_id, _scenes):
            local_path = "backend/downloads/provider-demo.mp4"
            remember_clip_metadata(
                local_path,
                {
                    "provider": "pexels",
                    "providerId": "101",
                    "author": "Pexels Creator",
                    "sourceUrl": "https://www.pexels.com/video/demo-101/",
                    "downloadUrl": "https://videos.pexels.com/101.mp4",
                    "width": 720,
                    "height": 1280,
                },
            )
            return [
                {
                    "sceneId": 1,
                    "sourceUrl": "https://www.pexels.com/video/demo-101/",
                    "localPath": local_path,
                    "publicUrl": "/downloads/provider-demo.mp4",
                    "duration": 6.0,
                    "caption": "开场镜头",
                    "sourceDuration": 20.0,
                    "trimStart": 4.9,
                    "trimDuration": 6.0,
                }
            ]

        async def fake_render_runner(_session_id, _clips, _filename):
            return "/output/final.mp4"

        with patch("backend.tasks.agent_tasks.SessionLocal", self.session_factory), patch(
            "backend.tasks.agent_tasks.search_and_download_agent_clips",
            fake_search_runner,
        ), patch(
            "backend.tasks.agent_tasks.render_video",
            fake_render_runner,
        ):
            run_agent_job(job_id)

        with self.session_factory() as db:
            artifact_repo = AgentArtifactRepository(db)
            artifacts = artifact_repo.list_for_session(session_id)

        clip_artifact = next(row for row in artifacts if row.artifact_type == "clip")
        self.assertEqual(clip_artifact.metadata_json["provider"], "pexels")
        self.assertEqual(clip_artifact.metadata_json["providerId"], "101")
        self.assertEqual(clip_artifact.metadata_json["author"], "Pexels Creator")
        self.assertEqual(clip_artifact.metadata_json["caption"], "开场镜头")
        self.assertEqual(clip_artifact.metadata_json["trimDuration"], 6.0)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_jobs.ArtifactTrimMetadataTests.test_run_agent_job_persists_provider_metadata_in_artifacts -v
```

Expected: fail because `run_agent_job` does not pop sidecar metadata.

- [ ] **Step 3: Import metadata sidecar in worker**

In `backend/tasks/agent_tasks.py`, add:

```python
from backend.services.asset_providers.metadata import pop_clip_metadata
```

- [ ] **Step 4: Merge provider metadata when creating clip artifacts**

Inside the `for clip in clips:` loop in `run_agent_job(...)`, replace the current inline metadata dict with:

```python
                provider_metadata = pop_clip_metadata(clip.localPath)
                clip_metadata = {
                    **provider_metadata,
                    "caption": clip.caption,
                    "sourceDuration": clip.sourceDuration,
                    "trimStart": clip.trimStart,
                    "trimDuration": clip.trimDuration,
                }
                progress_service.create_artifact(
                    session_id=session_id,
                    job_id=job_id,
                    artifact_type="clip",
                    scene_id=str(clip.sceneId),
                    source_url=clip.sourceUrl,
                    local_path=clip.localPath,
                    public_url=clip.publicUrl,
                    duration=clip.duration,
                    metadata=clip_metadata,
                )
```

- [ ] **Step 5: Run artifact metadata tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_jobs.ArtifactTrimMetadataTests.test_run_agent_job_persists_trim_metadata_in_artifacts \
  tests.test_agent_jobs.ArtifactTrimMetadataTests.test_run_agent_job_persists_caption_in_artifacts \
  tests.test_agent_jobs.ArtifactTrimMetadataTests.test_run_agent_job_persists_provider_metadata_in_artifacts -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 6**

```bash
git add backend/tasks/agent_tasks.py tests/test_agent_jobs.py
git commit -m "feat: persist asset provider metadata"
```

## Task 7: Documentation And Environment Variables

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Update `.env.example`**

Append these lines to `.env.example`:

```bash

# External asset providers
YTDLP_PROVIDER_ENABLED=true
YTDLP_COOKIES_FILE=
YTDLP_PLAYER_CLIENTS=mweb,web_safari,web
YTDLP_PO_TOKEN=
YTDLP_IMPERSONATE=
YTDLP_FORMAT=
PEXELS_PROVIDER_ENABLED=true
PEXELS_API_KEY=
```

- [ ] **Step 2: Update README environment variable section**

In `README.md`, add these bullets under `## 环境变量`:

```markdown
- `YTDLP_PROVIDER_ENABLED`：可选，是否启用 YouTube/yt-dlp 素材源，默认启用。
- `YTDLP_COOKIES_FILE`：可选，Netscape cookies 文件路径，用于 YouTube 要求登录或验证时的本地联调。只配置路径，不提交 cookie 文件。
- `YTDLP_PLAYER_CLIENTS`：可选，yt-dlp YouTube client 顺序，默认 `mweb,web_safari,web`。
- `YTDLP_PO_TOKEN`：可选，yt-dlp YouTube PO Token 配置字符串。只有在本机已经按 yt-dlp 文档配置好 token 流程时再使用。
- `YTDLP_IMPERSONATE`：可选，浏览器 TLS 指纹模拟值，例如 `chrome`。
- `YTDLP_FORMAT`：可选，覆盖 yt-dlp 下载格式选择；默认优先 720p 左右的 MP4。
- `PEXELS_PROVIDER_ENABLED`：可选，是否启用 Pexels 素材源；当 `PEXELS_API_KEY` 存在时默认启用。
- `PEXELS_API_KEY`：Pexels API key，用于稳定搜索和下载公开视频素材。
```

- [ ] **Step 3: Update README real external material notes**

Replace the paragraph that starts with `本机还需要能在命令行运行` with:

```markdown
本机还需要能在命令行运行 `node --version`。如果日志出现 `GVS PO Token`、`Only images are available for download` 或 `Sign in to confirm you’re not a bot`，说明 YouTube 对当前视频、账号、客户端或网络环境要求额外 Cookie/PO Token。可以先尝试：

1. 升级后端依赖：`pip install -r backend/requirements.txt --upgrade`。
2. 配置 `YTDLP_COOKIES_FILE` 指向本机导出的 Netscape cookies 文件。
3. 按 yt-dlp 官方文档配置 PO Token 后填写 `YTDLP_PO_TOKEN`。
4. 用 `YTDLP_PLAYER_CLIENTS` 或 `YTDLP_IMPERSONATE` 调整本地联调环境。

这些配置只能降低 YouTube 失败概率，不能保证 YouTube 永久稳定。生产和稳定联调建议配置 `PEXELS_API_KEY`，让 worker 在 YouTube 失败后继续尝试 Pexels。Pexels 视频搜索使用官方 `https://api.pexels.com/v1/videos/search` endpoint，并通过 `Authorization` header 传入 API key。

失败任务会保留素材源诊断信息。看到 `youtube: ...`、`pexels: ...` 这类错误时，先确认对应 provider 的环境变量和外部网络，再决定是否禁用某个 provider 做单独排查。

排查 provider 顺序或单独验证时，可以临时设置：

```bash
YTDLP_PROVIDER_ENABLED=false
PEXELS_PROVIDER_ENABLED=true
```

这会跳过 YouTube，只验证 Pexels 搜索、下载和渲染链路。反过来设置 `PEXELS_PROVIDER_ENABLED=false` 可以只验证 YouTube/yt-dlp 链路。
```

- [ ] **Step 4: Run docs checks**

Run:

```bash
rg -n "PEXELS_API_KEY|YTDLP_COOKIES_FILE|YTDLP_PLAYER_CLIENTS|PO Token|v1/videos/search" README.md .env.example
```

Expected: output includes both `README.md` and `.env.example`.

- [ ] **Step 5: Commit Task 7**

```bash
git add README.md .env.example
git commit -m "docs: document external asset providers"
```

## Task 8: Final Verification

**Files:**
- No planned source edits.

- [ ] **Step 1: Run targeted provider tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_asset_candidate_exposes_legacy_video_info \
  tests.test_agent_backend.AgentExecutionContractTests.test_clip_metadata_sidecar_round_trips_by_local_path \
  tests.test_agent_backend.AgentExecutionContractTests.test_youtube_options_use_current_clients_and_retry_settings \
  tests.test_agent_backend.AgentExecutionContractTests.test_youtube_options_avoid_po_token_clients_and_enable_node_ejs \
  tests.test_agent_backend.AgentExecutionContractTests.test_youtube_options_use_hardening_environment \
  tests.test_agent_backend.AgentExecutionContractTests.test_provider_boolean_env_parsing \
  tests.test_agent_backend.AgentExecutionContractTests.test_pexels_search_maps_api_response_to_candidates \
  tests.test_agent_backend.AgentExecutionContractTests.test_pexels_selects_vertical_mp4_with_bounded_resolution \
  tests.test_agent_backend.AgentExecutionContractTests.test_pexels_direct_download_writes_mp4 \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_download_falls_back_from_youtube_search_failure_to_pexels \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_download_falls_back_from_youtube_download_failure_to_pexels \
  tests.test_agent_backend.AgentExecutionContractTests.test_all_provider_failure_surfaces_safe_summaries \
  tests.test_agent_jobs.ArtifactTrimMetadataTests.test_run_agent_job_persists_provider_metadata_in_artifacts -v
```

Expected: all tests pass.

- [ ] **Step 2: Run backend suite**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest discover tests -v
```

Expected: all backend tests pass. The latest known baseline was 137 tests; the count should increase by the new provider tests.

- [ ] **Step 3: Run frontend build**

Run:

```bash
npm run build
```

Expected: Next.js build completes successfully.

- [ ] **Step 4: Run product page structural checks**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: product page checks pass.

- [ ] **Step 5: Inspect final git status**

Run:

```bash
git status --short
git log --oneline -8
```

Expected: clean worktree after task commits, with commits for provider types, YouTube hardening, Pexels search/download, orchestration, metadata, and docs.

## Implementation Notes For Subagents

- Workers are not alone in the codebase. Do not revert edits made by other workers; adjust your changes to fit the current files.
- Keep write scopes disjoint when possible:
  - Worker A: `backend/services/asset_providers/types.py`, `config.py`, `metadata.py`, shared tests.
  - Worker B: `backend/services/asset_providers/youtube.py`, YouTube option tests, compatibility wrappers.
  - Worker C: `backend/services/asset_providers/pexels.py`, Pexels tests.
  - Worker D: `backend/services/search_service.py`, orchestration tests.
  - Worker E: `backend/tasks/agent_tasks.py`, artifact tests, docs.
- If tests expose a real mismatch in class names, use `rg -n "class .*Tests" tests/test_agent_backend.py tests/test_agent_jobs.py` and patch the command/test location accordingly.
- Do not make live YouTube or Pexels calls in automated tests. Mock `yt_dlp.YoutubeDL` and `urllib.request.urlopen`.
- Do not log cookies, PO tokens, API keys, or full Pexels response bodies.
- Keep old wrapper functions `build_search_options`, `build_download_options`, `search_youtube`, and `download_video` because existing code and tests import them.

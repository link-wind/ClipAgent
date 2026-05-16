# Editable Runtime Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an editable local `/settings` page backed by a gitignored runtime config file so users can configure ClipForge environment parameters from the UI without exposing secrets back to the browser.

**Architecture:** Add a backend runtime config service that reads/writes `backend/runtime_config.local.json`, merges runtime overrides with environment/default values, and emits sanitized field metadata. Add `GET/PATCH/clear` config API routes, wire existing provider/OpenAI/backend config readers through the service where appropriate, then add a Tailwind-based `/settings` page and product checks. Sensitive values are write-only from the UI: users can set or clear them, but read APIs only return configured/source metadata.

**Tech Stack:** FastAPI, Pydantic, Python `unittest`, Next.js 14 App Router, React 18, TypeScript, Tailwind CSS, existing `ProductShell`, Node structural checks.

---

## File Structure

- Modify: `.gitignore`
  - Ignore `backend/runtime_config.local.json`.
- Create: `backend/services/runtime_config_service.py`
  - Own field definitions, runtime JSON load/write/clear, effective value lookup, sanitized settings response, and validation.
- Create: `backend/api/config.py`
  - Expose `GET /api/config/settings`, `PATCH /api/config/settings`, and `POST /api/config/settings/clear`.
- Modify: `backend/main.py`
  - Mount config router under `/api/config`.
- Modify: `backend/config.py`
  - Read infrastructure values through runtime config service.
- Modify: `backend/services/asset_providers/config.py`
  - Read provider order, provider enabled flags, Pexels key, and YouTube options through runtime config service.
- Modify: `backend/services/gpt_service.py`
  - Read OpenAI key/base URL through runtime config service.
- Create: `src/lib/settingsApi.ts`
  - Frontend API types and helpers.
- Create: `src/components/settings/SettingsPage.tsx`
  - Editable settings UI.
- Create: `src/app/settings/page.tsx`
  - Route entry.
- Modify: `src/components/layout/ProductShell.tsx`
  - Add settings navigation item.
- Modify: `scripts/check-product-pages.mjs`
  - Include `/settings` static checks.
- Modify: `tests/test_agent_backend.py`
  - Add backend runtime config/API contract tests and frontend source-contract tests.

---

### Task 1: Lock Runtime Config Backend Contracts With Failing Tests

**Files:**
- Modify: `tests/test_agent_backend.py`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.RuntimeConfigServiceTests`

- [ ] **Step 1: Add imports for runtime config tests**

Near the top of `tests/test_agent_backend.py`, update imports:

```python
import json
import tempfile
```

Keep existing imports intact.

- [ ] **Step 2: Add `RuntimeConfigServiceTests` before `FrontendClientContractTests`**

Add this test class before `class FrontendClientContractTests(unittest.TestCase):`

```python
class RuntimeConfigServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_path = Path(self.temp_dir.name) / "runtime_config.local.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_runtime_config_file_is_gitignored(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("backend/runtime_config.local.json", gitignore)

    def test_runtime_values_override_environment_and_defaults_without_leaking_secrets(self):
        from backend.services.runtime_config_service import RuntimeConfigService

        self.runtime_path.write_text(
            json.dumps(
                {
                    "PEXELS_API_KEY": "runtime-pexels-key",
                    "CLIPFORGE_ASSET_PROVIDER_ORDER": "pexels,youtube",
                }
            ),
            encoding="utf-8",
        )
        service = RuntimeConfigService(config_path=self.runtime_path)

        with patch.dict(os.environ, {"PEXELS_API_KEY": "env-pexels-key"}, clear=False):
            self.assertEqual(service.get_effective_value("PEXELS_API_KEY"), "runtime-pexels-key")
            response = service.get_settings_response()

        providers = next(group for group in response["groups"] if group["id"] == "providers")
        pexels_key = next(field for field in providers["fields"] if field["key"] == "PEXELS_API_KEY")
        provider_order = next(
            field for field in providers["fields"] if field["key"] == "CLIPFORGE_ASSET_PROVIDER_ORDER"
        )

        self.assertTrue(pexels_key["configured"])
        self.assertEqual(pexels_key["source"], "runtime")
        self.assertIsNone(pexels_key.get("value"))
        self.assertNotIn("runtime-pexels-key", json.dumps(response, ensure_ascii=False))
        self.assertEqual(provider_order["value"], "pexels,youtube")

    def test_clear_runtime_override_falls_back_to_environment(self):
        from backend.services.runtime_config_service import RuntimeConfigService

        self.runtime_path.write_text(json.dumps({"PEXELS_API_KEY": "runtime-key"}), encoding="utf-8")
        service = RuntimeConfigService(config_path=self.runtime_path)

        with patch.dict(os.environ, {"PEXELS_API_KEY": "env-key"}, clear=False):
            service.clear(["PEXELS_API_KEY"])
            self.assertEqual(service.get_effective_value("PEXELS_API_KEY"), "env-key")
            response = service.get_settings_response()

        providers = next(group for group in response["groups"] if group["id"] == "providers")
        pexels_key = next(field for field in providers["fields"] if field["key"] == "PEXELS_API_KEY")
        self.assertEqual(pexels_key["source"], "env")
        self.assertTrue(pexels_key["configured"])

    def test_invalid_provider_order_is_rejected(self):
        from backend.services.runtime_config_service import RuntimeConfigService

        service = RuntimeConfigService(config_path=self.runtime_path)

        with self.assertRaisesRegex(ValueError, "Unknown asset provider"):
            service.update({"CLIPFORGE_ASSET_PROVIDER_ORDER": "pexels,vimeo"})

    def test_runtime_settings_api_returns_grouped_sanitized_fields(self):
        from backend.api.config import create_config_router
        from backend.main import app
        from backend.services.runtime_config_service import RuntimeConfigService

        service = RuntimeConfigService(config_path=self.runtime_path)
        app.include_router(create_config_router(service), prefix="/api/test-config")
        client = _make_test_client(app)

        response = client.patch(
            "/api/test-config/settings",
            json={"updates": {"PEXELS_API_KEY": "secret-value", "CLIPFORGE_ASSET_PROVIDER_ORDER": "pexels,youtube"}},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("mode", data)
        self.assertIn("groups", data)
        self.assertNotIn("secret-value", json.dumps(data, ensure_ascii=False))
        self.assertTrue(self.runtime_path.exists())

        clear_response = client.post("/api/test-config/settings/clear", json={"keys": ["PEXELS_API_KEY"]})
        self.assertEqual(clear_response.status_code, 200)
```

- [ ] **Step 3: Run the new tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.RuntimeConfigServiceTests
```

Expected: FAIL because `.gitignore` does not yet include `backend/runtime_config.local.json`, and `backend.services.runtime_config_service` / `backend.api.config` do not exist.

- [ ] **Step 4: Commit the red tests**

Run:

```bash
git add tests/test_agent_backend.py
git commit -m "test: lock editable runtime settings backend contract"
```

---

### Task 2: Implement Runtime Config Service And API

**Files:**
- Modify: `.gitignore`
- Create: `backend/services/runtime_config_service.py`
- Create: `backend/api/config.py`
- Modify: `backend/main.py`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.RuntimeConfigServiceTests`

- [ ] **Step 1: Add runtime config file to `.gitignore`**

Append:

```gitignore
backend/runtime_config.local.json
```

- [ ] **Step 2: Create `backend/services/runtime_config_service.py`**

Create this file:

```python
import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_CONFIG_PATH = ROOT_DIR / "backend" / "runtime_config.local.json"
DEFAULT_DATABASE_URL = "postgresql+psycopg://clipforge:clipforge@localhost:5432/clipforge"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_YTDLP_FORMAT = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]"
DEFAULT_FIXTURE_LIBRARY_PATH = "fixtures/videos.json"
DEFAULT_ASSET_PROVIDER_ORDER = "youtube,pexels"
KNOWN_ASSET_PROVIDERS = {"fixture", "pexels", "youtube"}


@dataclass(frozen=True)
class RuntimeField:
    key: str
    label: str
    group: str
    kind: str
    sensitive: bool
    default: Any = None
    env_keys: tuple[str, ...] = ()
    restart: str = "immediate"
    help: str = ""


FIELD_DEFINITIONS: tuple[RuntimeField, ...] = (
    RuntimeField("OPENAI_API_KEY", "OpenAI API Key", "ai", "secret", True, env_keys=("OPENAI_API_KEY",), help="用于生成智能剪辑方案。"),
    RuntimeField("OPENAI_BASE_URL", "OpenAI Base URL", "ai", "string", False, "https://api.openai.com/v1", ("OPENAI_BASE_URL",), help="OpenAI 兼容 API 地址。"),
    RuntimeField("CLIPFORGE_ASSET_PROVIDER_ORDER", "素材源顺序", "providers", "provider_order", False, DEFAULT_ASSET_PROVIDER_ORDER, ("CLIPFORGE_ASSET_PROVIDER_ORDER",), help="demo 建议 fixture,pexels,youtube；真实外部素材联调建议 pexels,youtube。"),
    RuntimeField("FIXTURE_PROVIDER_ENABLED", "Fixture Provider", "providers", "boolean", False, True, ("FIXTURE_PROVIDER_ENABLED",), help="启用本地 deterministic fixture 素材源。"),
    RuntimeField("PEXELS_PROVIDER_ENABLED", "Pexels Provider", "providers", "boolean", False, None, ("PEXELS_PROVIDER_ENABLED",), help="启用 Pexels 素材源。未显式设置时，有 Pexels key 即启用。"),
    RuntimeField("PEXELS_API_KEY", "Pexels API Key", "providers", "secret", True, env_keys=("PEXELS_API_KEY",), help="用于 Pexels 视频搜索和下载。"),
    RuntimeField("YOUTUBE_PROVIDER_ENABLED", "YouTube Provider", "youtube", "boolean", False, True, ("YTDLP_PROVIDER_ENABLED", "YOUTUBE_PROVIDER_ENABLED"), help="启用 YouTube/yt-dlp 素材源。"),
    RuntimeField("YTDLP_COOKIES_FILE", "yt-dlp Cookies File", "youtube", "string", False, "", ("YTDLP_COOKIES_FILE",), help="本地 cookies 文件路径。"),
    RuntimeField("YTDLP_PO_TOKEN", "yt-dlp PO Token", "youtube", "secret", True, env_keys=("YTDLP_PO_TOKEN",), help="YouTube PO Token。只降低失败概率，不保证永久稳定。"),
    RuntimeField("YTDLP_PLAYER_CLIENTS", "yt-dlp Player Clients", "youtube", "csv", False, "mweb,web_safari,web", ("YTDLP_PLAYER_CLIENTS",), help="传给 yt-dlp 的 YouTube player clients。"),
    RuntimeField("YTDLP_FORMAT", "yt-dlp Format", "youtube", "string", False, DEFAULT_YTDLP_FORMAT, ("YTDLP_FORMAT",), help="yt-dlp 格式选择器。"),
    RuntimeField("YTDLP_IMPERSONATE", "yt-dlp Impersonate", "youtube", "string", False, "", ("YTDLP_IMPERSONATE",), help="yt-dlp impersonate 选项。"),
    RuntimeField("CLIPFORGE_DATABASE_URL", "Database URL", "infrastructure", "secret", True, DEFAULT_DATABASE_URL, ("CLIPFORGE_DATABASE_URL", "DATABASE_URL"), "api_worker", "PostgreSQL 连接地址，通常需要重启 API。"),
    RuntimeField("CLIPFORGE_REDIS_URL", "Redis URL", "infrastructure", "secret", True, DEFAULT_REDIS_URL, ("CLIPFORGE_REDIS_URL", "REDIS_URL"), "api_worker", "Redis 连接地址，通常需要重启 API 和 worker。"),
    RuntimeField("CELERY_BROKER_URL", "Celery Broker URL", "infrastructure", "secret", True, None, ("CELERY_BROKER_URL",), "api_worker", "Celery broker 地址，通常需要重启 API 和 worker。"),
    RuntimeField("CELERY_RESULT_BACKEND", "Celery Result Backend", "infrastructure", "secret", True, None, ("CELERY_RESULT_BACKEND",), "api_worker", "Celery result backend 地址，通常需要重启 worker。"),
    RuntimeField("CLIPFORGE_CELERY_QUEUE", "Celery Queue", "infrastructure", "string", False, "clipforge-agent", ("CLIPFORGE_CELERY_QUEUE",), "api_worker", "API 入队和 worker 监听必须使用同一个队列名。"),
)

GROUPS = {
    "ai": ("AI 配置", "OpenAI 兼容服务配置。"),
    "providers": ("素材源配置", "控制 fixture、Pexels、YouTube 的启用状态和搜索顺序。"),
    "youtube": ("YouTube 高级配置", "yt-dlp 相关增强参数。"),
    "infrastructure": ("基础设施配置", "数据库、Redis 和 Celery 运行配置。"),
}


class RuntimeConfigService:
    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or DEFAULT_RUNTIME_CONFIG_PATH
        self.fields = {field.key: field for field in FIELD_DEFINITIONS}

    def get_effective_value(self, key: str) -> Any:
        field = self._field(key)
        runtime = self._load_runtime_config()
        if key in runtime:
            return runtime[key]
        for env_key in field.env_keys:
            value = os.environ.get(env_key)
            if value is not None:
                return value
        if key == "CELERY_BROKER_URL":
            return self.get_effective_value("CLIPFORGE_REDIS_URL")
        if key == "CELERY_RESULT_BACKEND":
            return self.get_effective_value("CLIPFORGE_REDIS_URL")
        if key == "PEXELS_PROVIDER_ENABLED" and field.default is None:
            return bool(str(self.get_effective_value("PEXELS_API_KEY") or "").strip())
        return field.default

    def get_bool(self, key: str) -> bool:
        value = self.get_effective_value(key)
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() not in {"0", "false", "no", "off", ""}

    def get_csv(self, key: str, default: list[str]) -> list[str]:
        value = self.get_effective_value(key)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()] or list(default)
        if value is None:
            return list(default)
        parsed = [part.strip() for part in str(value).split(",") if part.strip()]
        return parsed or list(default)

    def update(self, updates: dict[str, Any]) -> dict[str, Any]:
        runtime = self._load_runtime_config()
        normalized = {key: self._validate_value(key, value) for key, value in updates.items()}
        runtime.update(normalized)
        self._write_runtime_config(runtime)
        return self.get_settings_response()

    def clear(self, keys: list[str]) -> dict[str, Any]:
        runtime = self._load_runtime_config()
        for key in keys:
            self._field(key)
            runtime.pop(key, None)
        self._write_runtime_config(runtime)
        return self.get_settings_response()

    def get_settings_response(self) -> dict[str, Any]:
        fields_by_group: dict[str, list[dict[str, Any]]] = {group_id: [] for group_id in GROUPS}
        for field in FIELD_DEFINITIONS:
            fields_by_group[field.group].append(self._field_response(field))

        return {
            "mode": self._mode_response(),
            "groups": [
                {
                    "id": group_id,
                    "title": title,
                    "description": description,
                    "fields": fields_by_group[group_id],
                }
                for group_id, (title, description) in GROUPS.items()
            ],
        }

    def _field_response(self, field: RuntimeField) -> dict[str, Any]:
        source = self._source(field)
        value = self.get_effective_value(field.key)
        configured = value is not None and str(value).strip() != ""
        response = {
            "key": field.key,
            "label": field.label,
            "group": field.group,
            "kind": field.kind,
            "sensitive": field.sensitive,
            "configured": configured,
            "source": source,
            "restart": field.restart,
            "help": field.help,
        }
        response["value"] = None if field.sensitive else value
        return response

    def _source(self, field: RuntimeField) -> str:
        runtime = self._load_runtime_config()
        if field.key in runtime:
            return "runtime"
        for env_key in field.env_keys:
            if os.environ.get(env_key) is not None:
                return "env"
        value = self.get_effective_value(field.key)
        return "default" if value not in (None, "") else "missing"

    def _mode_response(self) -> dict[str, str]:
        order = self.get_csv("CLIPFORGE_ASSET_PROVIDER_ORDER", ["youtube", "pexels"])
        openai_configured = bool(str(self.get_effective_value("OPENAI_API_KEY") or "").strip())
        enabled = {
            "fixture": self.get_bool("FIXTURE_PROVIDER_ENABLED"),
            "pexels": self.get_bool("PEXELS_PROVIDER_ENABLED"),
            "youtube": self.get_bool("YOUTUBE_PROVIDER_ENABLED"),
        }
        pexels_ready = enabled["pexels"] and bool(str(self.get_effective_value("PEXELS_API_KEY") or "").strip())
        any_enabled = any(enabled.get(provider, False) for provider in order)

        if not openai_configured or not any_enabled:
            return {
                "id": "incomplete",
                "label": "配置不完整",
                "description": "缺少规划或素材源所需配置，请补齐后再运行真实流程。",
            }
        if order and order[0] == "fixture" and enabled["fixture"]:
            return {
                "id": "fixture_smoke",
                "label": "fixture smoke/demo",
                "description": "当前优先使用本地 fixture 素材，适合稳定演示和冒烟验证。",
            }
        if pexels_ready or enabled["youtube"]:
            return {
                "id": "real_provider",
                "label": "真实外部素材联调",
                "description": "当前配置会优先尝试真实外部素材源。",
            }
        return {
            "id": "incomplete",
            "label": "配置不完整",
            "description": "当前素材源顺序缺少可用 provider。",
        }

    def _validate_value(self, key: str, value: Any) -> Any:
        field = self._field(key)
        if field.kind == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be a boolean")
            return value
        if field.kind == "provider_order":
            providers = self._normalize_provider_order(value)
            return ",".join(providers)
        if field.sensitive and isinstance(value, str) and not value.strip():
            raise ValueError(f"{key} cannot be blank; clear it instead")
        if value is None:
            raise ValueError(f"{key} cannot be null")
        return str(value).strip()

    def _normalize_provider_order(self, value: Any) -> list[str]:
        raw_parts = value if isinstance(value, list) else str(value).split(",")
        providers = [str(part).strip() for part in raw_parts if str(part).strip()]
        if not providers:
            raise ValueError("Asset provider order cannot be empty")
        unknown = [provider for provider in providers if provider not in KNOWN_ASSET_PROVIDERS]
        if unknown:
            raise ValueError(f"Unknown asset provider: {unknown[0]}")
        ordered: list[str] = []
        for provider in providers:
            if provider not in ordered:
                ordered.append(provider)
        return ordered

    def _field(self, key: str) -> RuntimeField:
        if key not in self.fields:
            raise ValueError(f"Unknown settings key: {key}")
        return self.fields[key]

    def _load_runtime_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Runtime config file is invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("Runtime config file must contain a JSON object")
        return data

    def _write_runtime_config(self, data: dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.config_path.parent, delete=False) as temp_file:
            json.dump(data, temp_file, ensure_ascii=False, indent=2, sort_keys=True)
            temp_file.write("\n")
            temp_name = temp_file.name
        Path(temp_name).replace(self.config_path)


runtime_config_service = RuntimeConfigService()
```

- [ ] **Step 3: Create `backend/api/config.py`**

Create:

```python
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.runtime_config_service import RuntimeConfigService, runtime_config_service


class SettingsUpdateRequest(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)


class SettingsClearRequest(BaseModel):
    keys: list[str] = Field(default_factory=list)


def create_config_router(service: RuntimeConfigService = runtime_config_service) -> APIRouter:
    router = APIRouter()

    @router.get("/settings")
    async def get_settings():
        try:
            return service.get_settings_response()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @router.patch("/settings")
    async def update_settings(request: SettingsUpdateRequest):
        try:
            return service.update(request.updates)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/settings/clear")
    async def clear_settings(request: SettingsClearRequest):
        try:
            return service.clear(request.keys)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return router


router = create_config_router()
```

- [ ] **Step 4: Mount config router in `backend/main.py`**

Add import:

```python
from backend.api.config import router as config_router
```

Then include:

```python
app.include_router(config_router, prefix="/api/config")
```

Place it near the existing API routers.

- [ ] **Step 5: Run backend contract tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.RuntimeConfigServiceTests
```

Expected: PASS.

- [ ] **Step 6: Commit backend runtime config service**

Run:

```bash
git add .gitignore backend/services/runtime_config_service.py backend/api/config.py backend/main.py tests/test_agent_backend.py
git commit -m "feat: add editable runtime config API"
```

---

### Task 3: Wire Existing Backend Config Readers Through Runtime Config

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/services/asset_providers/config.py`
- Modify: `backend/services/gpt_service.py`
- Modify: `tests/test_agent_backend.py`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.RuntimeConfigIntegrationTests`

- [ ] **Step 1: Add integration tests**

Add this class after `RuntimeConfigServiceTests`:

```python
class RuntimeConfigIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_path = Path(self.temp_dir.name) / "runtime_config.local.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_asset_provider_config_reads_runtime_overrides(self):
        import backend.services.asset_providers.config as provider_config
        from backend.services.runtime_config_service import RuntimeConfigService

        service = RuntimeConfigService(config_path=self.runtime_path)
        service.update(
            {
                "CLIPFORGE_ASSET_PROVIDER_ORDER": "fixture,pexels,youtube",
                "PEXELS_API_KEY": "runtime-pexels",
                "PEXELS_PROVIDER_ENABLED": True,
                "YOUTUBE_PROVIDER_ENABLED": False,
            }
        )

        with patch.object(provider_config, "runtime_config_service", service):
            self.assertEqual(provider_config.get_asset_provider_order(), ["fixture", "pexels", "youtube"])
            self.assertEqual(provider_config.get_pexels_config().api_key, "runtime-pexels")
            self.assertTrue(provider_config.get_pexels_config().enabled)
            self.assertFalse(provider_config.get_youtube_config().enabled)

    def test_gpt_service_reads_runtime_openai_config(self):
        import backend.services.gpt_service as gpt_service_module
        from backend.services.runtime_config_service import RuntimeConfigService

        service = RuntimeConfigService(config_path=self.runtime_path)
        service.update({"OPENAI_API_KEY": "runtime-openai", "OPENAI_BASE_URL": "https://example.test/v1"})

        with patch.object(gpt_service_module, "runtime_config_service", service):
            with patch.object(gpt_service_module, "OpenAI") as openai_client:
                gpt_service_module.GPTService()

        openai_client.assert_called_once_with(api_key="runtime-openai", base_url="https://example.test/v1")

    def test_backend_settings_reads_runtime_infrastructure_values(self):
        import backend.config as backend_config
        from backend.services.runtime_config_service import RuntimeConfigService

        service = RuntimeConfigService(config_path=self.runtime_path)
        service.update(
            {
                "CLIPFORGE_DATABASE_URL": "postgresql+psycopg://runtime/runtime",
                "CLIPFORGE_REDIS_URL": "redis://localhost:6379/9",
                "CLIPFORGE_CELERY_QUEUE": "clipforge-runtime",
            }
        )

        backend_config.get_settings.cache_clear()
        with patch.object(backend_config, "runtime_config_service", service):
            settings = backend_config.get_settings()
        backend_config.get_settings.cache_clear()

        self.assertEqual(settings.database_url, "postgresql+psycopg://runtime/runtime")
        self.assertEqual(settings.redis_url, "redis://localhost:6379/9")
        self.assertEqual(settings.celery_broker_url, "redis://localhost:6379/9")
        self.assertEqual(settings.celery_result_backend, "redis://localhost:6379/9")
        self.assertEqual(settings.celery_queue, "clipforge-runtime")
```

- [ ] **Step 2: Run integration tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.RuntimeConfigIntegrationTests
```

Expected: FAIL because current config readers still read `os.environ` directly.

- [ ] **Step 3: Update `backend/config.py`**

Replace the existing env reads with runtime config reads:

```python
from backend.services.runtime_config_service import (
    DEFAULT_DATABASE_URL,
    DEFAULT_REDIS_URL,
    runtime_config_service,
)
```

Then update `get_settings()`:

```python
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    redis_url = runtime_config_service.get_effective_value("CLIPFORGE_REDIS_URL") or DEFAULT_REDIS_URL
    database_url = runtime_config_service.get_effective_value("CLIPFORGE_DATABASE_URL") or DEFAULT_DATABASE_URL

    return Settings(
        database_url=database_url,
        redis_url=redis_url,
        celery_broker_url=runtime_config_service.get_effective_value("CELERY_BROKER_URL") or redis_url,
        celery_result_backend=runtime_config_service.get_effective_value("CELERY_RESULT_BACKEND") or redis_url,
        celery_queue=runtime_config_service.get_effective_value("CLIPFORGE_CELERY_QUEUE") or "clipforge-agent",
    )
```

Remove the now-unused `import os` and local `DEFAULT_*` definitions if they duplicate imported constants.

- [ ] **Step 4: Update `backend/services/asset_providers/config.py`**

Import runtime service/constants:

```python
from backend.services.runtime_config_service import (
    DEFAULT_ASSET_PROVIDER_ORDER,
    DEFAULT_FIXTURE_LIBRARY_PATH,
    DEFAULT_YTDLP_FORMAT,
    runtime_config_service,
)
```

Remove local duplicate constants and change helpers:

```python
def get_asset_provider_order() -> list[str]:
    configured = runtime_config_service.get_csv("CLIPFORGE_ASSET_PROVIDER_ORDER", DEFAULT_ASSET_PROVIDER_ORDER.split(","))
    allowed = {"fixture", "youtube", "pexels"}
    ordered: list[str] = []

    for provider in configured:
        if provider in allowed and provider not in ordered:
            ordered.append(provider)

    for provider in DEFAULT_ASSET_PROVIDER_ORDER.split(","):
        if provider not in ordered:
            ordered.append(provider)

    return ordered
```

Update config functions:

```python
def get_youtube_config() -> YoutubeProviderConfig:
    return YoutubeProviderConfig(
        enabled=runtime_config_service.get_bool("YOUTUBE_PROVIDER_ENABLED"),
        cookies_file=str(runtime_config_service.get_effective_value("YTDLP_COOKIES_FILE") or "").strip(),
        player_clients=runtime_config_service.get_csv("YTDLP_PLAYER_CLIENTS", ["mweb", "web_safari", "web"]),
        po_token=str(runtime_config_service.get_effective_value("YTDLP_PO_TOKEN") or "").strip(),
        impersonate=str(runtime_config_service.get_effective_value("YTDLP_IMPERSONATE") or "").strip(),
        format_selector=str(runtime_config_service.get_effective_value("YTDLP_FORMAT") or DEFAULT_YTDLP_FORMAT).strip() or DEFAULT_YTDLP_FORMAT,
    )


def get_pexels_config() -> PexelsProviderConfig:
    api_key = str(runtime_config_service.get_effective_value("PEXELS_API_KEY") or "").strip()
    return PexelsProviderConfig(
        enabled=runtime_config_service.get_bool("PEXELS_PROVIDER_ENABLED"),
        api_key=api_key,
    )


def get_fixture_config() -> FixtureProviderConfig:
    library_path = str(runtime_config_service.get_effective_value("FIXTURE_LIBRARY_PATH") or DEFAULT_FIXTURE_LIBRARY_PATH).strip()
    return FixtureProviderConfig(
        enabled=runtime_config_service.get_bool("FIXTURE_PROVIDER_ENABLED"),
        library_path=library_path or DEFAULT_FIXTURE_LIBRARY_PATH,
    )
```

Remove `env_flag()` / `env_csv()` if no longer used in this file.

- [ ] **Step 5: Update `backend/services/gpt_service.py`**

Add import:

```python
from backend.services.runtime_config_service import runtime_config_service
```

Update `GPTService.__init__` so it reads runtime config:

```python
api_key = str(runtime_config_service.get_effective_value("OPENAI_API_KEY") or "")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not configured")

self.client = OpenAI(
    api_key=api_key,
    base_url=str(runtime_config_service.get_effective_value("OPENAI_BASE_URL") or "https://api.openai.com/v1"),
)
```

- [ ] **Step 6: Run integration and existing provider tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.RuntimeConfigIntegrationTests \
  tests.test_agent_backend.AgentExecutionContractTests.test_provider_boolean_env_parsing \
  tests.test_agent_backend.AgentExecutionContractTests.test_youtube_options_use_current_clients_and_retry_settings \
  tests.test_agent_backend.AgentExecutionContractTests.test_youtube_options_use_hardening_environment
```

Expected: PASS. If an existing test expects `YTDLP_PROVIDER_ENABLED`, preserve compatibility by keeping `YTDLP_PROVIDER_ENABLED` in `YOUTUBE_PROVIDER_ENABLED` field `env_keys`.

- [ ] **Step 7: Commit config reader integration**

Run:

```bash
git add backend/config.py backend/services/asset_providers/config.py backend/services/gpt_service.py tests/test_agent_backend.py
git commit -m "feat: read runtime settings in backend config"
```

---

### Task 4: Lock And Build Frontend `/settings` Contract

**Files:**
- Modify: `tests/test_agent_backend.py`
- Create: `src/lib/settingsApi.ts`
- Create: `src/components/settings/SettingsPage.tsx`
- Create: `src/app/settings/page.tsx`
- Modify: `src/components/layout/ProductShell.tsx`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_settings_page_renders_editable_runtime_settings_contract`
- Test: `npm run build`

- [ ] **Step 1: Add frontend source-contract test**

Inside `FrontendClientContractTests`, add:

```python
    def test_settings_page_renders_editable_runtime_settings_contract(self):
        settings_page = (ROOT / "src" / "components" / "settings" / "SettingsPage.tsx").read_text(
            encoding="utf-8"
        )
        settings_route = (ROOT / "src" / "app" / "settings" / "page.tsx").read_text(encoding="utf-8")
        settings_api = (ROOT / "src" / "lib" / "settingsApi.ts").read_text(encoding="utf-8")
        shell_source = (ROOT / "src" / "components" / "layout" / "ProductShell.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("运行设置", settings_page)
        self.assertIn("AI 配置", settings_page)
        self.assertIn("素材源配置", settings_page)
        self.assertIn("YouTube 高级配置", settings_page)
        self.assertIn("基础设施配置", settings_page)
        self.assertIn("输入新值以替换当前配置", settings_page)
        self.assertIn("保存修改", settings_page)
        self.assertIn("放弃修改", settings_page)
        self.assertIn("清除", settings_page)
        self.assertIn("getRuntimeSettings", settings_api)
        self.assertIn("updateRuntimeSettings", settings_api)
        self.assertIn("clearRuntimeSettings", settings_api)
        self.assertIn("SettingsPage", settings_route)
        self.assertIn("href: '/settings'", shell_source)
```

- [ ] **Step 2: Run frontend contract test and verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_settings_page_renders_editable_runtime_settings_contract
```

Expected: FAIL because settings files do not exist yet.

- [ ] **Step 3: Create `src/lib/settingsApi.ts`**

Create:

```ts
import { requestJson } from './agentApi'

export type RuntimeSettingsSource = 'runtime' | 'env' | 'default' | 'missing'
export type RuntimeSettingsRestart = 'immediate' | 'api' | 'worker' | 'api_worker'

export interface RuntimeSettingsMode {
  id: string
  label: string
  description: string
}

export interface RuntimeSettingsField {
  key: string
  label: string
  group: string
  kind: string
  sensitive: boolean
  configured: boolean
  source: RuntimeSettingsSource
  restart: RuntimeSettingsRestart
  help: string
  value?: string | boolean | null
}

export interface RuntimeSettingsGroup {
  id: string
  title: string
  description: string
  fields: RuntimeSettingsField[]
}

export interface RuntimeSettingsResponse {
  mode: RuntimeSettingsMode
  groups: RuntimeSettingsGroup[]
}

export type RuntimeSettingsUpdateValue = string | boolean

export function getRuntimeSettings(): Promise<RuntimeSettingsResponse> {
  return requestJson<RuntimeSettingsResponse>('/api/config/settings')
}

export function updateRuntimeSettings(updates: Record<string, RuntimeSettingsUpdateValue>): Promise<RuntimeSettingsResponse> {
  return requestJson<RuntimeSettingsResponse>('/api/config/settings', {
    method: 'PATCH',
    body: { updates },
  })
}

export function clearRuntimeSettings(keys: string[]): Promise<RuntimeSettingsResponse> {
  return requestJson<RuntimeSettingsResponse>('/api/config/settings/clear', {
    method: 'POST',
    body: { keys },
  })
}
```

- [ ] **Step 4: Create `src/components/settings/SettingsPage.tsx`**

Create a compact client component:

```tsx
'use client';

import { useEffect, useMemo, useState } from 'react';
import ProductShell from '@/components/layout/ProductShell';
import {
  clearRuntimeSettings,
  getRuntimeSettings,
  updateRuntimeSettings,
  type RuntimeSettingsField,
  type RuntimeSettingsResponse,
  type RuntimeSettingsUpdateValue,
} from '@/lib/settingsApi';

const SOURCE_LABELS: Record<string, string> = {
  runtime: 'runtime',
  env: 'env',
  default: 'default',
  missing: 'missing',
};

const RESTART_LABELS: Record<string, string> = {
  immediate: '立即生效',
  api: '需重启 API',
  worker: '需重启 worker',
  api_worker: '需重启 API + worker',
};

const PROVIDER_ORDER_PRESETS = ['fixture,pexels,youtube', 'pexels,youtube', 'youtube,pexels'];

function stringifyFieldValue(field: RuntimeSettingsField) {
  if (field.sensitive) {
    return '';
  }
  if (typeof field.value === 'boolean') {
    return field.value ? 'true' : 'false';
  }
  return field.value === undefined || field.value === null ? '' : String(field.value);
}

function parseDraftValue(field: RuntimeSettingsField, value: string): RuntimeSettingsUpdateValue {
  if (field.kind === 'boolean') {
    return value === 'true';
  }
  return value;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<RuntimeSettingsResponse | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [dirtyKeys, setDirtyKeys] = useState<string[]>([]);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<'saved' | 'dirty' | 'saving' | 'failed'>('saved');

  useEffect(() => {
    void loadSettings();
  }, []);

  const fieldByKey = useMemo(() => {
    const fields: Record<string, RuntimeSettingsField> = {};
    settings?.groups.forEach((group) => {
      group.fields.forEach((field) => {
        fields[field.key] = field;
      });
    });
    return fields;
  }, [settings]);

  async function loadSettings() {
    try {
      const nextSettings = await getRuntimeSettings();
      setSettings(nextSettings);
      setDrafts({});
      setDirtyKeys([]);
      setSaveState('saved');
      setErrorText(null);
    } catch {
      setErrorText('设置服务暂时不可用。');
      setSaveState('failed');
    }
  }

  function updateDraft(field: RuntimeSettingsField, value: string) {
    setDrafts((prev) => ({ ...prev, [field.key]: value }));
    setDirtyKeys((prev) => (prev.includes(field.key) ? prev : [...prev, field.key]));
    setSaveState('dirty');
  }

  async function saveChanges() {
    const updates: Record<string, RuntimeSettingsUpdateValue> = {};
    dirtyKeys.forEach((key) => {
      const field = fieldByKey[key];
      if (!field) {
        return;
      }
      updates[key] = parseDraftValue(field, drafts[key] ?? '');
    });

    if (Object.keys(updates).length === 0) {
      return;
    }

    try {
      setSaveState('saving');
      const nextSettings = await updateRuntimeSettings(updates);
      setSettings(nextSettings);
      setDrafts({});
      setDirtyKeys([]);
      setSaveState('saved');
      setErrorText(null);
    } catch (error) {
      setSaveState('failed');
      setErrorText(error instanceof Error ? error.message : '保存失败，请检查字段。');
    }
  }

  async function clearField(field: RuntimeSettingsField) {
    try {
      const nextSettings = await clearRuntimeSettings([field.key]);
      setSettings(nextSettings);
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[field.key];
        return next;
      });
      setDirtyKeys((prev) => prev.filter((key) => key !== field.key));
      setSaveState('saved');
      setErrorText(null);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : '清除失败，请稍后重试。');
    }
  }

  function resetDrafts() {
    setDrafts({});
    setDirtyKeys([]);
    setSaveState('saved');
    setErrorText(null);
  }

  return (
    <ProductShell>
      <div className="grid min-w-0 gap-4 lg:gap-5">
        <section className="rounded-lg border border-border bg-white/90 p-5 shadow-soft sm:p-6" aria-label="运行设置">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <span className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">Settings</span>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">运行设置</h1>
                <p className="max-w-3xl text-sm leading-6 text-secondary sm:text-base">
                  编辑本地 runtime 配置，管理 AI、素材源、YouTube 高级参数和基础设施连接。
                </p>
              </div>
            </div>
            <div className="grid gap-2 text-sm text-secondary lg:text-right">
              <span className="font-semibold text-ink">{settings?.mode.label ?? '配置加载中'}</span>
              <span>{settings?.mode.description ?? '正在读取本地运行配置。'}</span>
              <span>{saveState === 'dirty' ? '有未保存修改' : saveState === 'saving' ? '保存中' : saveState === 'failed' ? '保存失败' : '已保存'}</span>
            </div>
          </div>
        </section>

        {errorText ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 shadow-soft">
            {errorText}
          </p>
        ) : null}

        {settings ? (
          <div className="grid gap-4">
            {settings.groups.map((group) => (
              <section key={group.id} className="rounded-lg border border-border bg-white/85 p-5 shadow-soft sm:p-6">
                <div className="border-b border-border pb-4">
                  <h2 className="text-xl font-semibold text-ink">{group.title}</h2>
                  <p className="mt-1 text-sm leading-6 text-secondary">{group.description}</p>
                </div>
                <div className="mt-4 grid gap-3">
                  {group.fields.map((field) => {
                    const draftValue = drafts[field.key] ?? stringifyFieldValue(field);
                    return (
                      <article key={field.key} className="grid gap-3 rounded-lg border border-border bg-slate-50/80 p-4 lg:grid-cols-[minmax(180px,0.8fr)_minmax(0,1.4fr)_auto] lg:items-start">
                        <div className="space-y-2">
                          <h3 className="text-sm font-semibold text-ink">{field.label}</h3>
                          <p className="text-xs leading-5 text-secondary">{field.help}</p>
                          <div className="flex flex-wrap gap-2">
                            <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-secondary ring-1 ring-border">{SOURCE_LABELS[field.source]}</span>
                            <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-secondary ring-1 ring-border">{RESTART_LABELS[field.restart]}</span>
                            {field.sensitive && field.configured ? <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 ring-1 ring-emerald-200">已配置</span> : null}
                          </div>
                        </div>

                        <div className="grid gap-2">
                          {field.kind === 'boolean' ? (
                            <label className="inline-flex items-center gap-3 text-sm font-medium text-ink">
                              <input
                                type="checkbox"
                                checked={draftValue === 'true'}
                                onChange={(event) => updateDraft(field, event.target.checked ? 'true' : 'false')}
                                className="h-4 w-4 rounded border-border text-slate-900 focus:ring-slate-300"
                              />
                              启用
                            </label>
                          ) : field.key === 'CLIPFORGE_ASSET_PROVIDER_ORDER' ? (
                            <div className="grid gap-2">
                              <select
                                value={PROVIDER_ORDER_PRESETS.includes(draftValue) ? draftValue : 'custom'}
                                onChange={(event) => {
                                  if (event.target.value !== 'custom') {
                                    updateDraft(field, event.target.value);
                                  }
                                }}
                                className="min-h-10 rounded-lg border border-border bg-white px-3 text-sm text-ink outline-none focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                              >
                                {PROVIDER_ORDER_PRESETS.map((preset) => (
                                  <option key={preset} value={preset}>{preset}</option>
                                ))}
                                <option value="custom">自定义</option>
                              </select>
                              <input
                                value={draftValue}
                                onChange={(event) => updateDraft(field, event.target.value)}
                                className="min-h-10 rounded-lg border border-border bg-white px-3 text-sm text-ink outline-none focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                              />
                            </div>
                          ) : (
                            <input
                              type={field.sensitive ? 'password' : 'text'}
                              value={draftValue}
                              placeholder={field.sensitive ? '输入新值以替换当前配置' : undefined}
                              onChange={(event) => updateDraft(field, event.target.value)}
                              className="min-h-10 rounded-lg border border-border bg-white px-3 text-sm text-ink outline-none focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                            />
                          )}
                        </div>

                        <div className="flex flex-wrap gap-2 lg:justify-end">
                          <button
                            type="button"
                            onClick={() => void clearField(field)}
                            className="inline-flex min-h-10 items-center rounded-lg border border-border bg-white px-4 text-sm font-semibold text-ink transition hover:bg-slate-50"
                          >
                            清除
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
            ))}

            <div className="sticky bottom-4 flex flex-wrap justify-end gap-3 rounded-lg border border-border bg-white/95 p-4 shadow-soft">
              <button
                type="button"
                onClick={resetDrafts}
                disabled={dirtyKeys.length === 0}
                className="inline-flex min-h-10 items-center rounded-lg border border-border bg-white px-4 text-sm font-semibold text-ink transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45"
              >
                放弃修改
              </button>
              <button
                type="button"
                onClick={() => void saveChanges()}
                disabled={dirtyKeys.length === 0 || saveState === 'saving'}
                className="inline-flex min-h-10 items-center rounded-lg bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-45"
              >
                保存修改
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </ProductShell>
  );
}
```

- [ ] **Step 5: Create `src/app/settings/page.tsx`**

Create:

```tsx
import SettingsPage from '@/components/settings/SettingsPage';

export default function SettingsRoutePage() {
  return <SettingsPage />;
}
```

- [ ] **Step 6: Add settings nav item**

In `src/components/layout/ProductShell.tsx`, add:

```tsx
  { href: '/settings', label: '设置', shortLabel: 'S' },
```

to `NAV_ITEMS`.

- [ ] **Step 7: Run frontend contract test and build**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_settings_page_renders_editable_runtime_settings_contract
npm run build
```

Expected: PASS.

- [ ] **Step 8: Commit frontend settings page**

Run:

```bash
git add src/lib/settingsApi.ts src/components/settings/SettingsPage.tsx src/app/settings/page.tsx src/components/layout/ProductShell.tsx tests/test_agent_backend.py
git commit -m "feat: add editable runtime settings page"
```

---

### Task 5: Update Product Checks And Complete Verification

**Files:**
- Modify: `scripts/check-product-pages.mjs`
- Test: `npm run build`
- Test: `node scripts/check-product-pages.mjs`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend`

- [ ] **Step 1: Add `/settings` to product page checks**

In `scripts/check-product-pages.mjs`, after the `/tasks` checks, add:

```js
  const settingsHtml = await readText('.next/server/app/settings.html');
  assertIncludes(settingsHtml, '运行设置', 'settings 页面缺少页面标题');
  assertIncludes(settingsHtml, 'AI 配置', 'settings 页面缺少 AI 配置分组');
  assertIncludes(settingsHtml, '素材源配置', 'settings 页面缺少素材源配置分组');
  assertIncludes(settingsHtml, 'YouTube 高级配置', 'settings 页面缺少 YouTube 高级配置分组');
  assertIncludes(settingsHtml, '基础设施配置', 'settings 页面缺少基础设施配置分组');
  assertIncludes(settingsHtml, '保存修改', 'settings 页面缺少保存动作');
```

- [ ] **Step 2: Run build**

Run:

```bash
npm run build
```

Expected: PASS and route list includes `/settings`.

- [ ] **Step 3: Run product page structural checks**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected:

```text
product page checks passed
```

- [ ] **Step 4: Run full backend/frontend contract suite**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend
```

Expected: PASS.

- [ ] **Step 5: Manual local settings smoke**

With backend and frontend running locally:

1. Open `/settings`.
2. Confirm page title `运行设置`.
3. Enter a fake `PEXELS_API_KEY` value such as `test-pexels-key`.
4. Save.
5. Reload settings.
6. Confirm the UI shows `PEXELS_API_KEY` as configured but does not show `test-pexels-key`.
7. Clear `PEXELS_API_KEY`.
8. Confirm `backend/runtime_config.local.json` is ignored by git:

```bash
git check-ignore backend/runtime_config.local.json
```

- [ ] **Step 6: Commit product checks and final docs**

Run:

```bash
git add scripts/check-product-pages.mjs docs/superpowers/specs/2026-05-07-editable-runtime-settings-design.md docs/superpowers/plans/2026-05-07-editable-runtime-settings-implementation.md
git commit -m "test: verify editable runtime settings page"
```

---

## Self-Review

- Spec coverage:
  - editable local settings page: Task 4
  - runtime config JSON layer: Task 2
  - secret masking: Task 2 + Task 4
  - clear sensitive fields: Task 2 + Task 4
  - runtime/env/default priority: Task 2 + Task 3
  - provider/OpenAI config integration: Task 3
  - restart badges and grouped fields: Task 2 + Task 4
  - gitignore protection: Task 2
  - product checks and verification: Task 5
- Placeholder scan:
  - No `TODO`, `TBD`, or “similar to Task N” instructions.
  - Each implementation step includes exact files and concrete code.
- Type consistency:
  - API shape uses `mode`, `groups`, `fields`, `updates`, and `keys` consistently.
  - Restart values are consistently `immediate`, `api`, `worker`, `api_worker`.
  - Source values are consistently `runtime`, `env`, `default`, `missing`.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-07-editable-runtime-settings-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

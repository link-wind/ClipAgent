import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_CONFIG_PATH = ROOT_DIR / "backend" / "runtime" / "runtime_config.local.json"
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
    RuntimeField("FIXTURE_LIBRARY_PATH", "Fixture Library Path", "providers", "string", False, DEFAULT_FIXTURE_LIBRARY_PATH, ("FIXTURE_LIBRARY_PATH",), help="本地 fixture metadata 文件路径。"),
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

VISIBLE_GROUPS = {
    "ai": ("AI 配置", "OpenAI 兼容服务配置。"),
    "providers": ("素材源配置", "控制 fixture、Pexels、YouTube 的启用状态和搜索顺序。"),
    "youtube": ("高级设置", "高级联调参数。只有在真实外部素材链路需要时才需要调整。"),
}

GROUPS = {
    **VISIBLE_GROUPS,
    "infrastructure": ("基础设施配置", "数据库、Redis 和 Celery 运行配置。"),
}


class RuntimeConfigService:
    def __init__(self, config_path: Path | None = None):
        configured_path = os.environ.get("CLIPFORGE_RUNTIME_CONFIG_PATH")
        self.config_path = config_path or Path(configured_path) if configured_path else config_path or DEFAULT_RUNTIME_CONFIG_PATH
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
        if key in {"CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"}:
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
        fields_by_group: dict[str, list[dict[str, Any]]] = {group_id: [] for group_id in VISIBLE_GROUPS}
        for field in FIELD_DEFINITIONS:
            if field.group in fields_by_group:
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
                for group_id, (title, description) in VISIBLE_GROUPS.items()
            ],
        }

    def _field_response(self, field: RuntimeField) -> dict[str, Any]:
        source = self._source(field)
        value = self.get_effective_value(field.key)
        configured = value is not None and str(value).strip() != ""
        return {
            "key": field.key,
            "label": field.label,
            "group": field.group,
            "kind": field.kind,
            "sensitive": field.sensitive,
            "configured": configured,
            "source": source,
            "restart": field.restart,
            "help": field.help,
            "value": None if field.sensitive else value,
        }

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
        if value is None:
            raise ValueError(f"{key} cannot be null")
        normalized = str(value).strip()
        if field.sensitive and not normalized:
            raise ValueError(f"{key} cannot be blank; clear it instead")
        return normalized

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

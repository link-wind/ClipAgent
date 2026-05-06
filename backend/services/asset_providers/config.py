import os
from dataclasses import dataclass

DEFAULT_YTDLP_FORMAT = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]"
DEFAULT_ASSET_PROVIDER_ORDER = ["youtube", "pexels"]
DEFAULT_FIXTURE_LIBRARY_PATH = "fixtures/videos.json"


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


def get_asset_provider_order() -> list[str]:
    configured = env_csv("CLIPFORGE_ASSET_PROVIDER_ORDER", DEFAULT_ASSET_PROVIDER_ORDER)
    allowed = {"youtube", "pexels"}
    ordered: list[str] = []

    for provider in configured:
        if provider in allowed and provider not in ordered:
            ordered.append(provider)

    for provider in DEFAULT_ASSET_PROVIDER_ORDER:
        if provider not in ordered:
            ordered.append(provider)

    return ordered


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


@dataclass(frozen=True)
class FixtureProviderConfig:
    enabled: bool
    library_path: str


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


def get_fixture_config() -> FixtureProviderConfig:
    library_path = os.environ.get("FIXTURE_LIBRARY_PATH", DEFAULT_FIXTURE_LIBRARY_PATH).strip()
    return FixtureProviderConfig(
        enabled=env_flag("FIXTURE_PROVIDER_ENABLED", default=True),
        library_path=library_path or DEFAULT_FIXTURE_LIBRARY_PATH,
    )

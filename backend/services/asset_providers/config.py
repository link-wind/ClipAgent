import os
from dataclasses import dataclass

from backend.services.runtime_config_service import (
    DEFAULT_ASSET_PROVIDER_ORDER,
    DEFAULT_FIXTURE_LIBRARY_PATH,
    DEFAULT_YTDLP_FORMAT,
    runtime_config_service,
)


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
    default_order = DEFAULT_ASSET_PROVIDER_ORDER.split(",")
    configured = runtime_config_service.get_csv("CLIPFORGE_ASSET_PROVIDER_ORDER", default_order)
    allowed = {"fixture", "youtube", "pexels"}
    ordered: list[str] = []

    for provider in configured:
        if provider in allowed and provider not in ordered:
            ordered.append(provider)

    for provider in default_order:
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
        enabled=runtime_config_service.get_bool("YOUTUBE_PROVIDER_ENABLED"),
        cookies_file=str(runtime_config_service.get_effective_value("YTDLP_COOKIES_FILE") or "").strip(),
        player_clients=runtime_config_service.get_csv("YTDLP_PLAYER_CLIENTS", ["mweb", "web_safari", "web"]),
        po_token=str(runtime_config_service.get_effective_value("YTDLP_PO_TOKEN") or "").strip(),
        impersonate=str(runtime_config_service.get_effective_value("YTDLP_IMPERSONATE") or "").strip(),
        format_selector=str(
            runtime_config_service.get_effective_value("YTDLP_FORMAT") or DEFAULT_YTDLP_FORMAT
        ).strip()
        or DEFAULT_YTDLP_FORMAT,
    )


def get_pexels_config() -> PexelsProviderConfig:
    api_key = str(runtime_config_service.get_effective_value("PEXELS_API_KEY") or "").strip()
    return PexelsProviderConfig(
        enabled=runtime_config_service.get_bool("PEXELS_PROVIDER_ENABLED"),
        api_key=api_key,
    )


def get_fixture_config() -> FixtureProviderConfig:
    library_path = str(
        runtime_config_service.get_effective_value("FIXTURE_LIBRARY_PATH") or DEFAULT_FIXTURE_LIBRARY_PATH
    ).strip()
    return FixtureProviderConfig(
        enabled=runtime_config_service.get_bool("FIXTURE_PROVIDER_ENABLED"),
        library_path=library_path or DEFAULT_FIXTURE_LIBRARY_PATH,
    )

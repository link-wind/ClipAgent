from backend.infrastructure.media.asset_providers import config as _impl
from backend.infrastructure.media.asset_providers.config import (
    FixtureProviderConfig,
    PexelsProviderConfig,
    YoutubeProviderConfig,
    env_csv,
    env_flag,
)
from backend.infrastructure.config.runtime_config_service import (
    DEFAULT_ASSET_PROVIDER_ORDER,
    DEFAULT_FIXTURE_LIBRARY_PATH,
    DEFAULT_YTDLP_FORMAT,
    runtime_config_service,
)


def _sync_patchable_exports() -> None:
    _impl.runtime_config_service = runtime_config_service


def get_asset_provider_order() -> list[str]:
    _sync_patchable_exports()
    return _impl.get_asset_provider_order()


def get_youtube_config() -> YoutubeProviderConfig:
    _sync_patchable_exports()
    return _impl.get_youtube_config()


def get_pexels_config() -> PexelsProviderConfig:
    _sync_patchable_exports()
    return _impl.get_pexels_config()


def get_fixture_config() -> FixtureProviderConfig:
    _sync_patchable_exports()
    return _impl.get_fixture_config()


__all__ = [
    "DEFAULT_ASSET_PROVIDER_ORDER",
    "DEFAULT_FIXTURE_LIBRARY_PATH",
    "DEFAULT_YTDLP_FORMAT",
    "FixtureProviderConfig",
    "PexelsProviderConfig",
    "YoutubeProviderConfig",
    "env_csv",
    "env_flag",
    "get_asset_provider_order",
    "get_fixture_config",
    "get_pexels_config",
    "get_youtube_config",
    "runtime_config_service",
]

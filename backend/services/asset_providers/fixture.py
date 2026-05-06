import json
from pathlib import Path

from backend.services.asset_providers.config import get_fixture_config


ROOT_DIR = Path(__file__).resolve().parents[3]


def load_fixture_library() -> list[dict]:
    config = get_fixture_config()
    library_path = ROOT_DIR / config.library_path
    with library_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

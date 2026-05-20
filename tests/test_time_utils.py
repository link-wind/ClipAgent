from datetime import datetime
from pathlib import Path

from backend.utils.time import utc_now_naive


ROOT = Path(__file__).resolve().parents[1]


def test_utc_now_naive_returns_naive_datetime() -> None:
    value = utc_now_naive()

    assert isinstance(value, datetime)
    assert value.tzinfo is None


def test_targeted_modules_do_not_use_datetime_utcnow_directly() -> None:
    target_paths = [
        "backend/db/models.py",
        "backend/db/repositories/knowledge.py",
        "tests/test_agent_persistence.py",
        "tests/test_rag_foundation.py",
    ]

    for relative_path in target_paths:
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "datetime.utcnow(" not in source, relative_path

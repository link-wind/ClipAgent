from datetime import datetime

from backend.utils.time import utc_now_naive


def test_utc_now_naive_returns_naive_datetime() -> None:
    value = utc_now_naive()

    assert isinstance(value, datetime)
    assert value.tzinfo is None

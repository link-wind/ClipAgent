from __future__ import annotations

import sqlite3
from datetime import date, datetime


def install_sqlite_datetime_adapters() -> None:
    sqlite3.register_adapter(datetime, lambda value: value.isoformat(sep=" "))
    sqlite3.register_adapter(date, lambda value: value.isoformat())

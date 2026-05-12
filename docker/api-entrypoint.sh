#!/bin/sh
set -eu

python - <<'PY'
import os
import socket
import time
from urllib.parse import urlparse


def wait_for(name: str, url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port
    if not host or not port:
        raise SystemExit(f"{name} URL must include host and port")

    deadline = time.monotonic() + 60
    while True:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


wait_for("Postgres", os.environ["CLIPFORGE_DATABASE_URL"])
wait_for("Redis", os.environ["CLIPFORGE_REDIS_URL"])
PY

python -m alembic -c backend/alembic.ini upgrade head

exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8010

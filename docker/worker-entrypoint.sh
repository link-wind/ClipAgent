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
        raise RuntimeError(f"Invalid {name} URL {url}: missing host or port")

    deadline = time.monotonic() + 60
    while True:
        print(f"Waiting for {name} at {host}:{port}...", flush=True)
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"{name} reachable at {host}:{port}", flush=True)
                return
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Timed out waiting for {name} at {host}:{port}") from exc
            time.sleep(1)


database_url = os.environ.get("CLIPFORGE_DATABASE_URL") or os.environ.get("DATABASE_URL") or "postgresql+psycopg://clipforge:clipforge@postgres:5432/clipforge"
redis_url = os.environ.get("CLIPFORGE_REDIS_URL") or os.environ.get("REDIS_URL") or "redis://redis:6379/0"
wait_for("Postgres", database_url)
wait_for("Redis", redis_url)
PY

exec python -m celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO -Q "${CLIPFORGE_CELERY_QUEUE:-clipforge-agent}"

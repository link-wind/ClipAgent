from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class DockerDeployContractTests(unittest.TestCase):
    def test_dockerfiles_and_entrypoints_exist(self) -> None:
        self.assertTrue((ROOT / "Dockerfile.backend").is_file())
        self.assertTrue((ROOT / "Dockerfile.frontend").is_file())
        self.assertTrue((ROOT / "docker/api-entrypoint.sh").is_file())
        self.assertTrue((ROOT / "docker/worker-entrypoint.sh").is_file())

    def test_compose_defines_full_clipforge_stack(self) -> None:
        compose = read("docker-compose.yml")

        for service in ("postgres:", "redis:", "api:", "worker:", "frontend:"):
            self.assertIn(service, compose)

        self.assertIn("Dockerfile.backend", compose)
        self.assertIn("Dockerfile.frontend", compose)
        self.assertIn("clipforge-downloads:", compose)
        self.assertIn("clipforge-output:", compose)
        self.assertIn("backend/downloads", compose)
        self.assertIn("backend/output", compose)
        self.assertIn("CLIPFORGE_DATABASE_URL", compose)
        self.assertIn("CLIPFORGE_REDIS_URL", compose)
        self.assertIn("CELERY_BROKER_URL", compose)
        self.assertIn("CELERY_RESULT_BACKEND", compose)
        self.assertIn("CLIPFORGE_API_ORIGIN", compose)
        self.assertIn("OPENAI_API_KEY", compose)
        self.assertNotIn("env_file:", compose)

    def test_backend_entrypoints_run_expected_commands(self) -> None:
        api = read("docker/api-entrypoint.sh")
        worker = read("docker/worker-entrypoint.sh")

        self.assertIn("python -m alembic -c backend/alembic.ini upgrade head", api)
        self.assertIn("python -m uvicorn backend.main:app --host 0.0.0.0 --port 8010", api)
        self.assertIn("python -m celery -A backend.tasks.celery_app:celery_app worker", worker)
        self.assertIn('-Q "${CLIPFORGE_CELERY_QUEUE:-clipforge-agent}"', worker)

    def test_next_rewrites_include_api_and_media_paths(self) -> None:
        next_config = read("next.config.js")

        self.assertIn("CLIPFORGE_API_ORIGIN", next_config)
        self.assertIn("source: '/api/agent/:path*'", next_config)
        self.assertIn("source: '/downloads/:path*'", next_config)
        self.assertIn("source: '/output/:path*'", next_config)

    def test_env_example_and_readme_document_one_click_deploy(self) -> None:
        env_example = read(".env.example")
        readme = read("README.md")

        self.assertIn("postgres:5432", env_example)
        self.assertIn("redis:6379", env_example)
        self.assertIn("CLIPFORGE_API_ORIGIN=http://api:8010", env_example)
        self.assertIn("docker compose up --build -d", readme)
        self.assertIn("Docker 一键部署", readme)
        self.assertIn("docker compose ps", readme)

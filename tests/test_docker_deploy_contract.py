from __future__ import annotations

import unittest
import re
from pathlib import Path
from packaging.version import Version


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def parse_requirements() -> dict[str, str]:
    requirements: dict[str, str] = {}
    for line in read("backend/requirements.txt").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        package, version = line.split("==", 1)
        requirements[package] = version
    return requirements


class DockerDeployContractTests(unittest.TestCase):
    def test_dockerfiles_and_entrypoints_exist(self) -> None:
        self.assertTrue((ROOT / "Dockerfile.backend").is_file())
        self.assertTrue((ROOT / "Dockerfile.frontend").is_file())
        self.assertTrue((ROOT / "docker/api-entrypoint.sh").is_file())
        self.assertTrue((ROOT / "docker/worker-entrypoint.sh").is_file())

    def test_compose_defines_full_clipforge_stack(self) -> None:
        compose = read("docker-compose.yml")

        for service_name in ("postgres", "redis", "api", "worker", "frontend"):
            self.assertRegex(compose, rf"(?m)^  {re.escape(service_name)}:\s*$")

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

    def test_compose_persists_runtime_settings_for_api_and_worker(self) -> None:
        compose = read("docker-compose.yml")
        runtime_service = read("backend/services/runtime_config_service.py")

        self.assertIn("CLIPFORGE_RUNTIME_CONFIG_PATH", compose)
        self.assertIn("clipforge-runtime-config:", compose)
        self.assertIn("/app/backend/runtime", compose)
        self.assertIn("DEFAULT_RUNTIME_CONFIG_PATH = ROOT_DIR / \"backend\" / \"runtime\" / \"runtime_config.local.json\"", runtime_service)

    def test_backend_dockerfile_uses_node_runtime_without_debian_npm(self) -> None:
        dockerfile = read("Dockerfile.backend")

        self.assertIn("FROM node:20-slim AS node-runtime", dockerfile)
        self.assertIn("FROM python:3.12-slim-bookworm", dockerfile)
        self.assertIn("COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node", dockerfile)
        self.assertIn("COPY --from=node-runtime /usr/local/bin/npm /usr/local/bin/npm", dockerfile)
        self.assertNotRegex(dockerfile, r"apt-get install[^\n]*\bnodejs\b")
        self.assertNotRegex(dockerfile, r"apt-get install[^\n]*\bnpm\b")

    def test_frontend_docker_build_injects_api_origin_for_next_rewrites(self) -> None:
        dockerfile = read("Dockerfile.frontend")
        compose = read("docker-compose.yml")

        self.assertIn("ARG CLIPFORGE_API_ORIGIN", dockerfile)
        self.assertIn("ENV CLIPFORGE_API_ORIGIN=${CLIPFORGE_API_ORIGIN}", dockerfile)
        self.assertRegex(
            compose,
            r"frontend:\n(?:.*\n)*?\s+build:\n(?:.*\n)*?\s+args:\n(?:.*\n)*?\s+CLIPFORGE_API_ORIGIN: \${CLIPFORGE_API_ORIGIN:-http://api:8010}",
        )

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

    def test_backend_requirements_keep_langchain_and_pydantic_compatible(self) -> None:
        requirements = parse_requirements()

        self.assertEqual(requirements["langchain"], "0.3.25")
        self.assertGreaterEqual(Version(requirements["pydantic"]), Version("2.7.4"))

    def test_backend_requirements_keep_langchain_openai_and_openai_compatible(self) -> None:
        requirements = parse_requirements()

        self.assertEqual(requirements["langchain-openai"], "0.2.14")
        self.assertGreaterEqual(Version(requirements["openai"]), Version("1.58.1"))

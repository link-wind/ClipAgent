# ClipForge Docker One-Click Deploy Design

## Overview

ClipForge is ready for a deployment packaging stage. The product now depends on a real multi-process runtime:

- Next.js frontend
- FastAPI API server
- Celery worker
- PostgreSQL
- Redis
- FFmpeg-backed render output
- persisted downloads and generated videos

The current `docker-compose.yml` only starts PostgreSQL and Redis. That is enough for local development, but not enough for putting ClipForge on a server for small-scale use. The next stage should provide a single-machine Docker Compose deployment that can run the whole product with one command after environment variables are filled.

The target operator experience is:

```bash
cp .env.example .env
# Fill OPENAI_API_KEY and optional provider keys such as PEXELS_API_KEY.
docker compose up --build -d
```

After startup, the user should be able to open:

```text
http://<server-ip>:3000/workspace
```

and use the existing agent workflow.

## Goal

Build the first one-click Docker deployment path for ClipForge on a single VPS or small server.

This stage should make the existing product runtime reproducible, not redesign the product architecture. The deployment should include:

1. A backend image that can run FastAPI or Celery worker from the same codebase.
2. A frontend image that runs Next.js in production mode.
3. A Compose stack with `postgres`, `redis`, `api`, `worker`, and `frontend`.
4. Automatic database migration before the API starts.
5. Shared persistent volumes for downloads, render outputs, database data, and Redis data.
6. Environment defaults that work inside Compose service networking.
7. README instructions for server deployment and smoke verification.

## Non-Goals

This stage does not include:

- HTTPS, domain binding, Caddy, or Nginx.
- User accounts, authentication, billing, or permissions.
- Object storage such as S3, R2, or OSS.
- Multi-machine deployment.
- Kubernetes.
- GitHub Actions image publishing.
- Automatic database backups.
- Production log aggregation.
- Secrets management beyond `.env` and Compose environment variables.
- Rewriting the agent, planner, provider, worker, or render architecture.

Those belong after the Compose stack is proven to run the product end to end.

## Approaches Considered

### Approach A: Single-Machine Docker Compose

Package the existing runtime into Docker images and run all services with Docker Compose.

Pros:

- Closest to the current codebase.
- Fastest path to a real server demo.
- Easy to reproduce locally and on a VPS.
- Keeps operational complexity low.

Cons:

- Not enough for serious production traffic.
- Still relies on local server disk volumes.
- HTTPS and domain setup remain manual future work.

This is the recommended approach.

### Approach B: Compose With Reverse Proxy And HTTPS

Add Caddy or Nginx now and make the first deployment domain-ready.

Pros:

- Closer to production.
- Better public-facing shape.

Cons:

- Adds certificate, host routing, and proxy configuration before the base runtime is proven.
- Makes debugging first Docker failures harder.

This should be the next stage after the base stack is stable.

### Approach C: CI-Built Images And Registry Deployment

Build images through GitHub Actions, push them to a registry, and deploy by pulling tagged images.

Pros:

- Good long-term release workflow.
- Server does not need to build images.

Cons:

- Requires registry, CI credentials, tagging policy, and deployment discipline before the Docker runtime is validated.
- Slower feedback loop for the first packaging pass.

This should wait until the Compose stack works.

## Recommended Direction

Use Approach A: single-machine Docker Compose.

The design should favor a clear, boring deployment over a production platform. A small server operator should be able to clone the repo, fill `.env`, run Compose, and reach `/workspace`.

## Runtime Architecture

The Compose stack should define five services.

### `postgres`

- Image: `postgres:16`
- Database: `clipforge`
- User: `clipforge`
- Password: configurable, defaulting to local-demo values in `.env.example`
- Volume: `clipforge-postgres-data:/var/lib/postgresql/data`

### `redis`

- Image: `redis:7`
- Command: `redis-server --appendonly yes`
- Volume: `clipforge-redis-data:/data`

### `api`

- Built from the backend Dockerfile.
- Command runs a startup script that:
  1. waits for PostgreSQL and Redis,
  2. runs `alembic -c backend/alembic.ini upgrade head`,
  3. starts `uvicorn backend.main:app --host 0.0.0.0 --port 8010`.
- Depends on `postgres` and `redis`.
- Uses the same persistent download/output volumes as the worker.
- Exposes port `8010` for direct health checks and debugging.

### `worker`

- Built from the backend Dockerfile.
- Command runs a worker startup script that:
  1. waits for PostgreSQL and Redis,
  2. starts `celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO -Q "$CLIPFORGE_CELERY_QUEUE"`.
- Depends on `postgres`, `redis`, and `api`.
- Uses the same environment and persistent download/output volumes as `api`.

### `frontend`

- Built from the frontend Dockerfile.
- Runs `npm run start`.
- Exposes port `3000`.
- Uses `CLIPFORGE_API_ORIGIN=http://api:8010` so Next rewrites can proxy API calls to the API container.

## Networking And Routing

The browser should talk to `frontend` on port `3000`.

The existing frontend calls relative paths like `/api/agent/...`. Next.js rewrites should forward those requests to `CLIPFORGE_API_ORIGIN`.

The current app also returns media URLs such as `/downloads/example.mp4` and `/output/final.mp4`. In Docker deployment, those URLs are requested from the frontend origin. Therefore `next.config.js` must proxy these paths to the API container as well:

- `/downloads/:path*` -> `${CLIPFORGE_API_ORIGIN}/downloads/:path*`
- `/output/:path*` -> `${CLIPFORGE_API_ORIGIN}/output/:path*`

Without those rewrites, successful jobs can produce MP4 files that the browser cannot load through the frontend origin.

## Environment Contract

`.env.example` should support both local development and Compose deployment clearly.

The Compose defaults should use service names, not `localhost`:

```env
CLIPFORGE_DATABASE_URL=postgresql+psycopg://clipforge:clipforge@postgres:5432/clipforge
CLIPFORGE_REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
CLIPFORGE_CELERY_QUEUE=clipforge-agent
CLIPFORGE_API_ORIGIN=http://api:8010
```

The deployment documentation should explicitly list these required or high-value variables:

- `OPENAI_API_KEY`: required when `CLIPFORGE_PLANNER_MODE=langchain`.
- `OPENAI_BASE_URL`: optional OpenAI-compatible endpoint.
- `CLIPFORGE_PLANNER_MODE`: default `langchain`; can be `deterministic` for local smoke.
- `CLIPFORGE_PLANNER_MODEL`: default `gpt-4o-mini`.
- `CLIPFORGE_ASSET_PROVIDER_ORDER`: recommended `fixture,pexels,youtube` for smoke; recommended `pexels,youtube` for real external provider runs.
- `PEXELS_API_KEY`: recommended for stable real external assets.
- `PEXELS_PROVIDER_ENABLED`: optional provider toggle.
- YouTube/yt-dlp tuning variables such as `YTDLP_COOKIES_FILE`, `YTDLP_PO_TOKEN`, and `YTDLP_PLAYER_CLIENTS`: optional and not required for first Compose smoke.

Database and Redis variables should be treated as infrastructure settings for deployment, not editable user-facing runtime settings.

## Docker Images

### Backend Image

The backend image should:

- Use a Python 3.12 slim base image.
- Install system packages needed by the runtime:
  - `ffmpeg`
  - `nodejs`
  - `npm` if required by the distro package
  - build/network utilities only if required by dependencies or wait scripts
- Install `backend/requirements.txt`.
- Copy backend code, migrations, fixtures, and any assets needed by the worker.
- Set the repo root as working directory so existing paths like `backend/downloads` and `fixtures/videos.json` continue to resolve.

The same image should run both `api` and `worker` to avoid dependency drift.

### Frontend Image

The frontend image should:

- Use a Node LTS image.
- Install dependencies with `npm ci`.
- Build with `npm run build`.
- Run with `npm run start`.
- Accept `CLIPFORGE_API_ORIGIN` at runtime for Next rewrites.

If Next.js requires build-time environment for rewrites in this codebase, the implementation should document that and pass the same value during build and runtime. The preferred behavior is runtime configurability through `process.env.CLIPFORGE_API_ORIGIN`.

## Persistence

The Compose stack should persist:

- PostgreSQL data.
- Redis data.
- `backend/downloads`.
- `backend/output`.

The API and worker must mount the same downloads/output volumes so:

1. the worker can write downloaded clips and rendered MP4 files,
2. the API can serve them through `/downloads` and `/output`,
3. the frontend can proxy those paths back to the API.

The first version should keep paths compatible with existing code:

- `backend/downloads`
- `backend/output`

Changing the application to configurable artifact paths is useful later, but not required for this stage.

## Startup And Health

The backend startup scripts should be small and explicit.

`api` startup:

1. Wait until PostgreSQL accepts connections.
2. Wait until Redis accepts connections.
3. Run Alembic migrations.
4. Start Uvicorn.

`worker` startup:

1. Wait until PostgreSQL accepts connections.
2. Wait until Redis accepts connections.
3. Start Celery on `CLIPFORGE_CELERY_QUEUE`.

The API already has `/health`, returning `{"status":"ok"}`. Compose should include a healthcheck for `api` using that endpoint if the image has `curl` or Python can perform the check.

## Smoke Verification

The README should include a deployment smoke checklist:

1. `docker compose ps` shows all services running.
2. `curl http://127.0.0.1:8010/health` returns `{"status":"ok"}`.
3. `curl http://127.0.0.1:3000/workspace` returns HTML.
4. The browser can open `http://<server-ip>:3000/workspace`.
5. With fixture-first settings, a user can create a workspace session.
6. The user can confirm the plan and enqueue a job.
7. `worker` logs show it consumed the job.
8. The task reaches a terminal state.
9. If successful, `/output/<file>.mp4` opens through the frontend origin.
10. If failed, `/workspace` or `/tasks` shows the diagnostic panel added in the previous stage.

The first pass should use fixture-first mode:

```env
CLIPFORGE_PLANNER_MODE=deterministic
FIXTURE_PROVIDER_ENABLED=true
CLIPFORGE_ASSET_PROVIDER_ORDER=fixture,pexels,youtube
```

That smoke verifies deployment, persistence, worker execution, and MP4 serving without depending on external model or provider availability.

For real provider validation, switch to:

```env
CLIPFORGE_PLANNER_MODE=langchain
CLIPFORGE_ASSET_PROVIDER_ORDER=pexels,youtube
PEXELS_API_KEY=<real key>
OPENAI_API_KEY=<real key>
```

## Error Handling

Deployment errors should fail visibly:

- If PostgreSQL is unreachable, `api` and `worker` should not silently start in a broken state.
- If migrations fail, `api` should exit instead of serving a half-ready app.
- If Redis is unreachable, `worker` should exit or keep failing visibly.
- If `OPENAI_API_KEY` is missing while `CLIPFORGE_PLANNER_MODE=langchain`, the app may still start, but planning requests should fail with the existing clear runtime error.
- If `PEXELS_API_KEY` is missing, Pexels should be skipped or diagnosed according to existing provider behavior.

The Docker layer should not hide application-level diagnostics behind generic container messages.

## Testing Strategy

Implementation should include tests or checks at three levels:

1. Static contract checks:
   - Dockerfiles exist.
   - Compose contains `api`, `worker`, `frontend`, `postgres`, and `redis`.
   - Compose defines artifact volumes.
   - README documents one-click deployment.
2. Existing application tests:
   - Run the current backend agent/persistence suite.
   - Run `npm run build`.
3. Docker smoke:
   - Run `docker compose config`.
   - Build images with `docker compose build`.
   - Start the stack.
   - Verify API health and frontend HTML.

Full end-to-end browser workflow inside Docker is desirable but not required for the first implementation plan if local machine resources make it slow. The README smoke checklist must be accurate enough for manual server verification.

## Acceptance Criteria

This stage is complete when:

1. `docker compose up --build -d` starts all five services.
2. `api` runs migrations automatically before serving.
3. `frontend` serves `/workspace` on port `3000`.
4. Frontend API rewrites reach `api`.
5. Frontend media rewrites serve `/downloads/*` and `/output/*`.
6. `worker` consumes the same queue used by `api`.
7. Downloads and render outputs persist in Docker volumes.
8. README documents local development and server Compose deployment separately.
9. `docker compose config` succeeds.
10. Existing backend tests and `npm run build` still pass outside Docker.

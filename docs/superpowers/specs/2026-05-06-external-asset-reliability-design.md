# External Asset Reliability Design

Date: 2026-05-06

## Goal

Make the real external asset path reliable enough for `/workspace -> confirm -> worker -> render MP4` integration runs.

The current implementation uses `yt-dlp` for both YouTube keyword search (`ytsearchN:`) and YouTube download. Recent real runs reached the worker and then failed on the external source layer with network resets and YouTube anti-bot checks. This stage keeps the existing yt-dlp investment, hardens its YouTube path, and adds a stable provider fallback so YouTube is no longer the only route to real footage.

## Non-Goals

- Do not redesign `/workspace` UI.
- Do not perform a global Tailwind migration in this stage.
- Do not change the database schema in the first pass.
- Do not store cookies, PO tokens, API keys, or account material in git.
- Do not promise that YouTube can be made permanently stable. The design must treat YouTube as a high-value but volatile provider.

## Current Context

`backend/services/search_service.py` currently owns search, download, candidate retries, trim metadata, and public download paths.

The existing flow is:

1. `search_youtube(keywords, max_results)` builds `ytsearchN:<query>`.
2. `download_video(...)` uses `yt-dlp` to download the selected YouTube URL.
3. `search_and_download_agent_clips(...)` tries several YouTube candidates per scene and returns `ClipInfo` values.
4. Worker code persists returned clips as artifacts and renders the final video.

The previous bugfix made external failures visible instead of silently falling through. That is useful and should remain: a failed external source must be visible in task status, failed step mapping, event logs, and runbook notes.

## Recommended Approach

Use a provider orchestration layer with two tracks:

1. Harden the existing YouTube yt-dlp provider.
2. Add Pexels as the first stable external provider fallback.

The default order should be:

1. YouTube yt-dlp, when configured as enabled.
2. Pexels API, when `PEXELS_API_KEY` is available.
3. Clear failure with provider diagnostics when all providers fail.

This order keeps the user's current YouTube-based behavior intact while avoiding a single point of failure. If real runs keep showing YouTube anti-bot failures, the order can be changed later by configuration without changing the provider interfaces.

## Provider Model

Introduce a small internal candidate structure. It can be a dataclass or typed dict, but callers should see one shape:

- `provider`: `youtube` or `pexels`
- `id`: provider-native id
- `title`: human-readable title
- `sourceUrl`: source page URL
- `downloadUrl`: direct file URL when available
- `duration`: source duration in seconds
- `width`: optional source width
- `height`: optional source height
- `thumbnail`: optional preview URL
- `author`: optional author or channel name
- `diagnostics`: provider-specific safe diagnostics

Do not add fields to `ClipInfo` yet. Map provider data into `ClipInfo.sourceUrl`, existing local/public paths, trim metadata, and artifact `metadata_json`.

## YouTube Hardening

Keep `yt-dlp` as the YouTube provider, but move hard-coded YouTube options behind configuration helpers.

Supported environment variables:

- `YTDLP_COOKIES_FILE`: optional path to a Netscape cookies file. The backend passes this path to yt-dlp. It must never log the file contents.
- `YTDLP_PLAYER_CLIENTS`: optional comma-separated client preference, default `mweb,web_safari,web`.
- `YTDLP_PO_TOKEN`: optional token config string for yt-dlp extractor args when the operator has configured a valid PO token flow.
- `YTDLP_IMPERSONATE`: optional browser impersonation value such as `chrome`, passed only when configured.
- `YTDLP_FORMAT`: optional format override. Default remains MP4-oriented and capped around 720p for render speed.
- `YTDLP_PROVIDER_ENABLED`: optional boolean, default enabled.

The implementation should keep retries, socket timeout, `yt-dlp-ejs`, and Node runtime support. It should also preserve existing readable summaries for PO token, unavailable format, and challenge failures.

YouTube failure handling:

- Search failures should produce a provider diagnostic and allow the orchestrator to try the next provider.
- Download failures for one YouTube candidate should try the next YouTube candidate.
- If all YouTube candidates fail, return the last summarized YouTube error to the orchestrator.
- If every provider fails, raise a user-readable error that includes provider names and safe summaries.

## Pexels Provider

Add Pexels as a stable external provider.

Configuration:

- `PEXELS_API_KEY`: required to enable Pexels.
- `PEXELS_PROVIDER_ENABLED`: optional boolean, default enabled when the key exists.

Search:

- Call Pexels video search with the scene query.
- Prefer portrait/vertical results when possible.
- Request a small candidate set per scene to limit latency.
- Normalize every result into the shared candidate shape.

Download:

- Prefer MP4 video files.
- Prefer vertical files, then files at or below 720p or 1080p.
- Download direct file URLs without `yt-dlp`.
- Save to the existing `backend/downloads/{session_id}_{scene_id}.mp4` naming convention, with suffixes for retries.

Attribution and metadata:

- Store Pexels source URL, author, provider id, selected file dimensions, and selected file URL in artifact metadata.
- Surface provider name and safe diagnostic details in progress or event payloads where existing event structures support it.

## Data Flow

`search_and_download_agent_clips(...)` should become an orchestrator:

1. For each scene, build a normalized search query from `scene.keywords` or `scene.searchQuery`.
2. Ask each enabled provider for candidates in configured order.
3. For each provider, try candidates until one downloads.
4. After download, compute `sourceDuration`, `trimStart`, and `trimDuration` exactly as today.
5. Return `ClipInfo` values for rendering.
6. Attach provider metadata through artifact metadata creation in the worker/progress layer.

The renderer should not care whether a clip came from YouTube or Pexels. Its input remains local MP4 paths and trim metadata.

## Error Handling

Errors must remain visible and actionable.

- Missing `PEXELS_API_KEY` should be a skipped-provider diagnostic, not a hard failure when YouTube is enabled.
- Missing cookies or PO token should not block YouTube by default; they only affect hardened modes.
- Invalid cookie file path should be reported as a YouTube provider configuration failure.
- HTTP errors from Pexels should include status code and a short safe body summary.
- Downloaded non-video or empty files should be treated as provider download failures.
- Final failure should map to `search_assets` or `prepare_assets` according to the failing phase, not `render_video`.

## Testing Strategy

Use TDD and mock external network calls.

Backend tests should cover:

1. YouTube options include configured cookies file, player clients, PO token, impersonation, and format override.
2. Missing YouTube configuration falls back to safe defaults.
3. Pexels API responses map to normalized candidates.
4. Pexels file selection prefers vertical MP4 and bounded resolution.
5. Pexels direct download writes an MP4 to `backend/downloads`.
6. Provider orchestration falls back from YouTube search failure to Pexels.
7. Provider orchestration falls back from failed YouTube candidates to Pexels.
8. Missing `PEXELS_API_KEY` skips Pexels and reports diagnostics.
9. All-provider failure surfaces safe provider summaries.
10. Artifact metadata records provider, source URL, author, and selected file details.
11. Existing trim metadata tests continue to pass.
12. Existing API failed-step mapping tests continue to pass.

Automated verification after implementation:

- Targeted backend unit tests for provider behavior.
- Full backend test suite.
- `npm run build`.
- `node scripts/check-product-pages.mjs`.

Manual integration verification:

1. Configure local PostgreSQL, Redis, FastAPI, Celery, and Next.js as in the runbook.
2. Run once with YouTube enabled and available configuration.
3. Run once with a Pexels API key and YouTube disabled or forced to fail in test configuration.
4. Confirm `/workspace` can hand off execution and `/tasks` can show either a playable MP4 or precise provider failure diagnostics.

## Documentation Updates

Update `.env.example` with:

- `PEXELS_API_KEY`
- `PEXELS_PROVIDER_ENABLED`
- `YTDLP_PROVIDER_ENABLED`
- `YTDLP_COOKIES_FILE`
- `YTDLP_PLAYER_CLIENTS`
- `YTDLP_PO_TOKEN`
- `YTDLP_IMPERSONATE`
- `YTDLP_FORMAT`

Update `README.md` with:

- YouTube reliability notes.
- Safe cookie file guidance.
- PO token caveat and link to yt-dlp documentation.
- Pexels setup instructions.
- How to choose provider order or disable a provider for debugging.
- How to interpret provider diagnostics in failed tasks.

## Acceptance Criteria

1. Existing YouTube behavior still works when no new environment variables are set.
2. YouTube yt-dlp options can be hardened through environment variables.
3. Pexels can search and download real external MP4 footage when `PEXELS_API_KEY` is configured.
4. Worker execution can render a final MP4 from Pexels-downloaded clips.
5. If YouTube fails due to anti-bot or network issues, the system can try Pexels before failing the task.
6. If all providers fail, `/workspace` and `/tasks` expose a precise, user-readable failure instead of a generic render error.
7. Provider and attribution metadata are retained in artifact metadata.
8. Automated backend and frontend verification commands pass.

## Resolved Decisions

Default provider order is YouTube first, then Pexels. This preserves current product behavior. If integration runs show YouTube remains noisy even with hardening, switch the default order to Pexels first in a later small change.

The first implementation should keep provider metadata out of the public `ClipInfo` model. If the UI later needs source cards or attribution display, add explicit API fields in a separate spec.

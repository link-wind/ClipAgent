# Deterministic Fixture Fallback Design

Date: 2026-05-07

## Goal

Add a deterministic local fixture asset provider so ClipForge can complete a stable dev/demo render path without depending on live YouTube or Pexels availability.

This stage is a narrow follow-up to P0 workflow hardening. The goal is not to replace real external providers. It is to guarantee that local verification and demos can still reach MP4 output when external asset platforms are unavailable or intentionally disabled.

## Non-Goals

- Do not redesign `/workspace` or `/tasks`.
- Do not add a frontend toggle or control panel for asset source selection in this stage.
- Do not add database tables, uploaded fixture management, or an admin UI.
- Do not remove real provider support for YouTube or Pexels.
- Do not turn deterministic fixture mode into the default production behavior.

## Current Context

The current asset flow is owned by `backend/services/search_service.py`.

Today it supports:

- YouTube candidate search via `yt-dlp`
- Pexels API search and direct download
- provider ordering via `CLIPFORGE_ASSET_PROVIDER_ORDER`
- normalized `AssetCandidate` and `AssetDownload` structures

The repo already contains fixture metadata in `fixtures/videos.json`, with records that include:

- `id`
- `title`
- `description`
- `duration`
- `tags`
- `thumbnailUrl`
- `videoUrl`

What it does not yet have is an actual fixture provider wired into `search_and_download_agent_clips(...)`.

## Recommended Approach

Introduce a new backend-only provider named `fixture`.

This provider should:

1. Read fixture metadata from `fixtures/videos.json`
2. Match scene intent against fixture metadata using `keywords` and `searchQuery`
3. Return normalized `AssetCandidate` entries
4. Resolve selected fixtures into renderable local paths without hitting any external network

The fixture provider should be available through provider order, so local runs can set:

```bash
CLIPFORGE_ASSET_PROVIDER_ORDER=fixture,pexels,youtube
```

This makes deterministic local fixtures the first source for dev/demo while preserving external fallback for production-shaped validation.

## Provider Model

The fixture provider should conform to the same internal model already used by Pexels and YouTube.

Search output should be `AssetCandidate` values with:

- `provider="fixture"`
- `id` from fixture metadata
- `title` from fixture metadata
- `source_url` using the fixture `videoUrl`
- `download_url` also pointing at the fixture `videoUrl`
- `duration` from fixture metadata
- `thumbnail` from fixture metadata
- `diagnostics` including matched tags / score / source file info

No new public API model is required.

## Search Behavior

Fixture search should stay intentionally simple and deterministic.

Suggested matching rules:

1. Build a normalized query token set from:
   - `scene.keywords`
   - fallback `scene.searchQuery`
2. Build a normalized candidate token set from:
   - fixture `title`
   - fixture `description`
   - fixture `tags`
3. Score fixtures by token overlap
4. Return the top `max_results` matches
5. If nothing matches, return an empty list rather than inventing a fuzzy fallback

This stage does not need semantic search, embeddings, or multilingual NLP. Deterministic, transparent matching is more useful for demos and tests.

## Download Behavior

The fixture provider should not perform a real remote download.

Instead, it should resolve the fixture asset into the same shape expected by the renderer:

- `local_path`
- `public_url`
- artifact metadata

The safest implementation is:

1. Treat fixture files as local media under the repo-managed fixture directory
2. Copy the selected fixture into `backend/downloads/<session>_<scene>_fixture_<n>.mp4`
3. Return an `AssetDownload` pointing at that copied file

Copying rather than rendering directly from the source fixture path keeps downstream behavior aligned with existing assumptions:

- render stage still reads from `backend/downloads/...`
- artifact metadata still points to a concrete session-scoped file
- existing download/result routing stays unchanged

## Fixture File Requirements

The fixture metadata alone is not enough. This stage assumes the actual `.mp4` files referenced by `fixtures/videos.json` either already exist or will be added as part of the implementation.

The implementation should:

- fail clearly when metadata exists but the referenced fixture file is missing
- surface that as a fixture provider diagnostic
- not silently fall back to a fake success

If some fixture rows are incomplete, the provider should skip only those rows and continue evaluating other fixtures.

## Configuration

Add a small set of fixture-specific env controls:

- `FIXTURE_PROVIDER_ENABLED`
  - optional boolean
  - default enabled when fixture metadata exists
- `FIXTURE_LIBRARY_PATH`
  - optional path override
  - default `fixtures/videos.json`

No frontend env is needed.

The provider order env remains the primary switch for behavior:

- deterministic demo: `fixture,pexels,youtube`
- real external validation: `pexels,youtube`
- YouTube-only debugging: `youtube`

## Failure Handling

Fixture mode should improve local reliability, but it still needs precise diagnostics.

Expected failure types:

- fixture library metadata file missing
- fixture metadata malformed
- referenced fixture file missing
- no fixture candidates matched the scene
- copy/read error while preparing the local fixture asset

These should surface as provider-specific messages, for example:

- `fixture: 缺少 fixture library 文件`
- `fixture: 引用的本地素材文件不存在`
- `fixture: 没有匹配到本地演示素材`

As with other providers, a fixture provider failure should allow the next provider in order to run.

## Testing Strategy

This stage should use TDD and keep tests backend-focused.

Required tests:

1. Fixture metadata loader reads `fixtures/videos.json`
2. Fixture search returns normalized `AssetCandidate` values
3. Fixture search ranks candidates by token overlap
4. Fixture provider returns empty list when there are no matches
5. Fixture download/copy produces an `AssetDownload` under `backend/downloads`
6. Missing fixture file raises a clear fixture diagnostic
7. `search_and_download_agent_clips(...)` can complete a scene using provider order `fixture,...`
8. Fixture provider falls through to the next provider when no fixture matches
9. Full backend test suite still passes

Verification after implementation:

1. `python -m unittest tests.test_agent_backend`
2. `npm run build`
3. `node scripts/check-product-pages.mjs`
4. one real local session with `CLIPFORGE_ASSET_PROVIDER_ORDER=fixture,pexels,youtube`

## Documentation Updates

Update `README.md` to document:

- deterministic fixture mode purpose
- required env vars
- recommended provider orders for demo vs real runs
- where fixture metadata and files live
- what counts as a successful fixture-backed validation run

Update `.env.example` to include:

- `FIXTURE_PROVIDER_ENABLED`
- `FIXTURE_LIBRARY_PATH`

## Acceptance Criteria

This stage is complete when:

1. A local run can complete with `CLIPFORGE_ASSET_PROVIDER_ORDER=fixture,pexels,youtube` even when external providers are unavailable.
2. Selected fixtures are converted into `backend/downloads/...` files compatible with the existing render path.
3. Fixture provider failures are clear and do not masquerade as generic search failures.
4. Backend tests and the existing frontend verification suite still pass.
5. README clearly distinguishes deterministic fixture mode from real external validation mode.

## Resolved Decisions

The deterministic fallback will be implemented as a new backend provider, not a frontend feature.

The first version will use simple token overlap against `fixtures/videos.json`, not semantic ranking.

The first version will copy fixture media into `backend/downloads/...` rather than bypassing the existing render input contract.

# ClipForge Editable Runtime Settings Design

## Background

ClipForge now has the main product surfaces in place:

- Dashboard for product overview,
- `/workspace` for planning and execution handoff,
- `/tasks` for task operations,
- fixture-first smoke flow for deterministic local verification.

The remaining friction is configuration. Real local runs still depend on several environment variables:

- AI provider keys,
- asset provider ordering,
- Pexels credentials,
- YouTube yt-dlp hardening options,
- database, Redis, Celery broker/result backend, and queue settings.

Today these values are configured through shell environment variables and README runbooks. That works for developers, but it makes the product loop fragile:

- a missing `PEXELS_API_KEY` can look like provider failure,
- mismatched Celery queue names can look like stuck jobs,
- YouTube restrictions can look like generic asset search failure,
- changing provider order requires restarting commands or editing shell setup.

The next stage should add an editable settings surface so local users can configure and inspect the runtime without repeatedly editing terminal commands.

## Goal

Build an editable local settings page that lets users configure ClipForge runtime parameters from the UI while keeping sensitive values protected.

The first version should support:

1. reading current effective configuration,
2. editing local runtime overrides,
3. clearing local overrides,
4. masking sensitive fields,
5. explaining whether each change is immediate or requires service restart,
6. keeping secrets out of git.

## Chosen Direction

Use a gitignored local runtime config file as the editable layer:

```text
backend/runtime_config.local.json
```

Configuration precedence:

```text
runtime_config.local.json > environment variables > defaults
```

This gives the settings page a safe local persistence target without requiring it to mutate shell profiles, `.env` files, or process manager config.

## Why Not Edit `.env` Directly

Editing `.env` from a browser-facing workflow would be ambiguous in this project:

- the backend currently reads many settings from `os.environ`,
- Next.js, FastAPI, and Celery may each be started from different shells,
- running services do not automatically reload shell environment variables,
- `.env` ownership is unclear across root repo and worktrees.

A dedicated runtime config file is clearer:

- it has one owner,
- it can be gitignored,
- the backend can reload it per request or per config read,
- the UI can show exactly which values come from runtime overrides.

## Security Model

This is a local development tool, not a multi-user production admin console.

Even so, it must not leak secrets:

1. Sensitive values are never returned by read APIs.
2. Sensitive inputs are empty by default, even when configured.
3. A configured sensitive field only shows `configured: true`.
4. Replacing a sensitive field requires entering a new value.
5. Clearing a sensitive field uses an explicit clear action.
6. `backend/runtime_config.local.json` must be ignored by git.
7. Logs and test output should not print secret values.

This stage does not add authentication, authorization, encryption at rest, or multi-user audit history.

## Configuration Groups

### AI Configuration

Fields:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`

Behavior:

- `OPENAI_API_KEY` is sensitive.
- `OPENAI_BASE_URL` is not sensitive.
- If `GPTService` reads configuration per instantiation, updates can affect new planning calls without full backend restart.

### Asset Provider Configuration

Fields:

- `CLIPFORGE_ASSET_PROVIDER_ORDER`
- `FIXTURE_PROVIDER_ENABLED`
- `PEXELS_PROVIDER_ENABLED`
- `PEXELS_API_KEY`
- `YOUTUBE_PROVIDER_ENABLED`

Behavior:

- provider order should be editable through safe presets plus optional custom value.
- `PEXELS_API_KEY` is sensitive.
- provider enabled fields are booleans.
- changes should apply to future asset search calls if provider config reads runtime config at call time.

Recommended provider order presets:

- `fixture,pexels,youtube`
- `pexels,youtube`
- `youtube,pexels`

### YouTube Advanced Configuration

Fields:

- `YTDLP_COOKIES_FILE`
- `YTDLP_PO_TOKEN`
- `YTDLP_PLAYER_CLIENTS`
- `YTDLP_FORMAT`
- `YTDLP_IMPERSONATE`

Behavior:

- `YTDLP_PO_TOKEN` is sensitive.
- `YTDLP_COOKIES_FILE` is a local path and should be treated as non-secret but still not over-emphasized.
- These options only lower the chance of YouTube failure; the page should not imply YouTube can be made permanently stable.

### Infrastructure Configuration

Fields:

- `CLIPFORGE_DATABASE_URL`
- `CLIPFORGE_REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `CLIPFORGE_CELERY_QUEUE`

Behavior:

- database and broker URLs may contain credentials and should be treated as sensitive or masked.
- queue name is not sensitive.
- these settings usually require restarting API, worker, or both.
- changing them at runtime should not pretend to move already-running connections.

## Effective Configuration Model

Each field should have metadata:

```json
{
  "key": "PEXELS_API_KEY",
  "label": "Pexels API Key",
  "group": "providers",
  "sensitive": true,
  "configured": true,
  "source": "runtime",
  "restart": "immediate",
  "value": null,
  "help": "用于 Pexels 视频搜索和下载。保存后后续素材搜索可用。"
}
```

For non-sensitive fields:

```json
{
  "key": "CLIPFORGE_ASSET_PROVIDER_ORDER",
  "label": "素材源顺序",
  "group": "providers",
  "sensitive": false,
  "configured": true,
  "source": "runtime",
  "restart": "immediate",
  "value": "fixture,pexels,youtube",
  "help": "决定素材搜索顺序。demo 建议 fixture,pexels,youtube；真实外部素材联调建议 pexels,youtube。"
}
```

Allowed `source` values:

- `runtime`
- `env`
- `default`
- `missing`

Allowed `restart` values:

- `immediate`
- `api`
- `worker`
- `api_worker`

## API Design

### `GET /api/config/settings`

Returns grouped field metadata and mode summary.

Response shape:

```json
{
  "mode": {
    "id": "fixture_smoke",
    "label": "fixture smoke/demo",
    "description": "当前优先使用本地 fixture 素材，适合稳定演示和冒烟验证。"
  },
  "groups": [
    {
      "id": "providers",
      "title": "素材源配置",
      "description": "控制 fixture、Pexels、YouTube 的启用状态和搜索顺序。",
      "fields": []
    }
  ]
}
```

Sensitive fields must set `value` to `null` or omit it.

### `PATCH /api/config/settings`

Accepts partial updates:

```json
{
  "updates": {
    "PEXELS_API_KEY": "new-key",
    "CLIPFORGE_ASSET_PROVIDER_ORDER": "pexels,youtube",
    "PEXELS_PROVIDER_ENABLED": true
  }
}
```

Rules:

- unknown keys are rejected,
- values are validated by field type,
- empty strings for sensitive keys are rejected unless the request uses clear,
- updates are written only to `backend/runtime_config.local.json`,
- response returns the same shape as `GET /api/config/settings`.

### `POST /api/config/settings/clear`

Accepts keys to remove from runtime overrides:

```json
{
  "keys": ["PEXELS_API_KEY"]
}
```

Rules:

- clearing removes runtime overrides only,
- if an env value exists, the effective field may still show configured from `env`,
- response returns the same shape as `GET /api/config/settings`.

## Runtime Config Service

Add:

```text
backend/services/runtime_config_service.py
```

Responsibilities:

1. load `backend/runtime_config.local.json`,
2. write runtime overrides atomically,
3. clear runtime override keys,
4. expose typed field definitions,
5. compute effective values from runtime/env/default,
6. produce sanitized response models,
7. provide helper functions for backend config readers.

The service should avoid caching runtime config permanently. A page save should affect later backend reads without requiring API restart for fields marked `immediate`.

## Backend Integration Points

### `backend/config.py`

Should use runtime config service for:

- `CLIPFORGE_DATABASE_URL`
- `CLIPFORGE_REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `CLIPFORGE_CELERY_QUEUE`

These may still require restarts because existing database engines, Redis clients, and Celery app setup are created at import/startup time.

### `backend/services/asset_providers/config.py`

Should use runtime config service for:

- provider order,
- fixture enabled,
- Pexels enabled/key,
- YouTube enabled and advanced yt-dlp options.

These should affect future search/download calls because provider config is already read during provider execution.

### `backend/services/gpt_service.py`

Should use runtime config service for:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`

This should affect new service instantiations. If a future singleton caches the OpenAI client, that would need separate invalidation; this phase should document the current behavior.

## Frontend Design

Add:

```text
src/app/settings/page.tsx
src/components/settings/SettingsPage.tsx
src/lib/settingsApi.ts
```

The page should be a compact operational tool, not a marketing page.

### Page Header

Show:

- title: `运行设置`
- current mode label,
- save state: `已保存`, `有未保存修改`, `保存失败`.

### Field Rows

Each field row should show:

- label,
- source badge,
- restart badge,
- input control,
- clear action when a runtime override exists or the field is sensitive.

Sensitive fields:

- input value is always empty,
- placeholder: `输入新值以替换当前配置`,
- configured state is shown as a badge,
- clear button removes runtime override.

Boolean fields:

- use checkbox or toggle.

Provider order:

- use a preset selector plus custom text input if needed.

Infrastructure URLs:

- use text inputs,
- display restart requirement clearly.

### Save And Reset

The page should keep local draft state.

Actions:

- `保存修改`
- `放弃修改`
- per-field `清除`

After save or clear:

1. call the API,
2. replace local state with sanitized server response,
3. clear sensitive input drafts.

## Validation Rules

Minimal validation for this phase:

- provider order must only contain known providers: `fixture`, `pexels`, `youtube`,
- provider order cannot be empty,
- boolean fields must be booleans,
- URL-like infrastructure fields must be non-empty strings when provided,
- sensitive fields cannot be saved as blank strings through `PATCH`,
- unknown keys are rejected.

Do not over-validate external paths or URLs in this stage; many local development setups use valid but nonstandard values.

## Mode Summary

The settings API should compute a simple mode:

### `fixture_smoke`

When provider order starts with `fixture`.

Label:

- `fixture smoke/demo`

### `real_provider`

When provider order starts with `pexels` or excludes `fixture`, and required real-provider credentials are configured enough to try.

Label:

- `真实外部素材联调`

### `incomplete`

When selected mode is unlikely to work because required fields are missing, for example:

- provider order includes `pexels` but `PEXELS_API_KEY` is missing and YouTube is also disabled,
- all asset providers are disabled,
- `OPENAI_API_KEY` is missing for planning flows.

Label:

- `配置不完整`

This summary is advisory, not a hard blocker.

## Error Handling

Frontend:

- if settings load fails, show `设置服务暂时不可用`,
- if save fails, preserve drafts,
- if a field-level validation error returns, show it near the field,
- if clear fails, keep the previous UI state.

Backend:

- invalid field keys return HTTP 400,
- invalid value types return HTTP 400,
- malformed `runtime_config.local.json` should not crash the API; return a readable error and ignore the broken runtime layer until fixed,
- write failures return HTTP 500 with a safe message.

## Testing Strategy

Backend tests:

1. runtime config file is ignored by git via `.gitignore`,
2. runtime values override env/default values,
3. sensitive fields are never returned,
4. clearing runtime override falls back to env/default,
5. invalid provider order is rejected,
6. asset provider config reads runtime override,
7. GPT service reads runtime OpenAI config,
8. settings API returns grouped fields and mode summary.

Frontend contract tests:

1. `/settings` route exists,
2. settings page renders `运行设置`,
3. page includes the expected groups,
4. sensitive fields use replacement placeholders,
5. save and clear actions are present,
6. structural product page checks include `/settings`.

Manual verification:

1. open `/settings`,
2. enter and save `PEXELS_API_KEY`,
3. reload page and confirm only `已配置` is shown,
4. clear `PEXELS_API_KEY`,
5. switch provider order to `pexels,youtube`,
6. confirm mode summary updates,
7. confirm `backend/runtime_config.local.json` is not tracked by git.

## Implementation Boundaries

Expected files:

- Create `backend/services/runtime_config_service.py`
- Create `backend/api/config.py`
- Modify `backend/main.py`
- Modify `backend/config.py`
- Modify `backend/services/asset_providers/config.py`
- Modify `backend/services/gpt_service.py`
- Modify `.gitignore`
- Create `src/app/settings/page.tsx`
- Create `src/components/settings/SettingsPage.tsx`
- Create `src/lib/settingsApi.ts`
- Modify `src/components/layout/ProductShell.tsx` if navigation needs a settings entry
- Modify `scripts/check-product-pages.mjs`
- Modify `tests/test_agent_backend.py`

Avoid:

- auth/permission system,
- encrypted local secret storage,
- online provider test button,
- worker start/stop controls,
- config history,
- writing shell profiles,
- editing arbitrary files from the browser.

## Success Criteria

This stage is complete when:

1. `/settings` exists and renders an editable settings panel.
2. Settings can be saved to `backend/runtime_config.local.json`.
3. Sensitive fields can be set and cleared without ever being read back as plaintext.
4. Runtime config overrides provider and OpenAI config reads.
5. Infrastructure fields clearly show restart requirements.
6. `backend/runtime_config.local.json` is gitignored.
7. Build, product page checks, and relevant backend tests pass.

## Open Follow-Up

After this stage, the next settings-related step can be:

1. provider connectivity checks,
2. one-click fixture smoke from the UI,
3. worker/API health checks,
4. optional encryption or OS keychain integration for local secrets.

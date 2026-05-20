# Compat Surface

当前 `backend.services.*` 不再是开放式实现目录，当前 frozen compat surface 只剩 1 个有明确原因保留的兼容入口。

- `backend.services.asset_providers.pexels`
  - Pexels provider 的 patch-through shim。
  - 现阶段仍被测试用于下载目录、请求行为和 provider fallback 的 monkeypatch。

除这个模块外，其余 `backend.services.*` 都应继续收缩，优先改为直接依赖 `backend.app.*`、`backend.domain.*`、`backend.infrastructure.*` 或 `backend.compat.*` 的真实边界。

# Compat Surface

当前 `backend.services.*` 不再是开放式实现目录，只保留少量有明确原因的兼容入口。

- `backend.services.agent_service`
  - 旧的内存态 Agent API 入口。
  - 实际实现已经外移到 `backend.compat.agent_service`，这里保留旧导入路径，避免历史调用方直接断掉。

- `backend.services.search_service`
  - 搜索与下载链路的 patch-through shim。
  - 主要用于现有测试继续 monkeypatch `download_video`、`search_youtube_candidates`、`search_pexels_candidates`、`download_pexels_candidate`、`get_asset_provider_order`、`get_pexels_config`。

- `backend.services.planner_runtime_langchain`
  - LangChain planner runtime 的 patch-through shim。
  - 仍保留旧路径，支持 runtime 相关测试做 monkeypatch 和 fallback 验证。

- `backend.services.asset_providers.config`
  - provider 配置层的 patch-through shim。
  - 现阶段仍被测试用于配置覆盖和运行时开关验证。

- `backend.services.asset_providers.fixture`
  - fixture provider 的 patch-through shim。
  - 现阶段仍被测试用于 fixture 搜索、下载和探测逻辑的 monkeypatch。

- `backend.services.asset_providers.pexels`
  - Pexels provider 的 patch-through shim。
  - 现阶段仍被测试用于下载目录、请求行为和 provider fallback 的 monkeypatch。

除了以上模块，其余 `backend.services.*` 都应继续收缩，优先改为直接依赖 `backend.app.*`、`backend.domain.*`、`backend.infrastructure.*` 或 `backend.compat.*` 的真实边界。

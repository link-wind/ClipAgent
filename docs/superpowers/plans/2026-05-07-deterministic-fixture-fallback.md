# Deterministic Fixture Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ClipForge 增加一个 deterministic 本地 fixture provider，让本地 P0 验证和演示在外部素材平台不可用时仍能稳定走到 MP4 输出。

**Architecture:** 在现有 asset provider 架构中新增 `fixture` provider，读取 `fixtures/videos.json` 并将匹配到的本地素材复制到 `backend/downloads/...`，继续复用现有 `AssetCandidate`、`AssetDownload`、`search_and_download_agent_clips(...)` 与渲染输入契约。通过环境变量和 provider order 控制是否优先走 deterministic fixture，不新增前端控制面板或数据库结构。

**Tech Stack:** Python 3.12, FastAPI backend services, dataclass-based asset provider models, local JSON fixture library, `unittest`, Next.js build checks, existing README / `.env.example`.

---

## File Structure

- Create: `backend/services/asset_providers/fixture.py`
  - 负责读取 fixture library、匹配候选、复制素材并返回 `AssetDownload`。
- Modify: `backend/services/asset_providers/config.py`
  - 增加 fixture provider 配置和 provider order 允许值。
- Modify: `backend/services/search_service.py`
  - 接入 `fixture` provider 到现有 orchestration flow。
- Modify: `tests/test_agent_backend.py`
  - 为 fixture metadata、匹配、copy、provider fallback 行为补 TDD 覆盖。
- Modify: `.env.example`
  - 增加 `FIXTURE_PROVIDER_ENABLED` 和 `FIXTURE_LIBRARY_PATH`。
- Modify: `README.md`
  - 说明 deterministic fixture mode 的目的、用法、限制和推荐 provider order。
- Verify: `fixtures/videos.json`
  - 作为默认 fixture metadata 输入，不在本计划内重做内容结构。

不做前端 UI 开关，不做素材上传，不做数据库落库，不做语义搜索。

---

### Task 1: 锁定 fixture provider 配置与 metadata 读取契约

**Files:**
- Modify: `tests/test_agent_backend.py`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: 先写一个失败测试，要求 fixture provider 配置可从 env 解析**

在 `AgentExecutionContractTests` 里新增：

```python
    def test_fixture_provider_config_uses_defaults(self):
        from backend.services.asset_providers.config import get_fixture_config

        with patch.dict("os.environ", {}, clear=True):
            config = get_fixture_config()

        self.assertTrue(config.enabled)
        self.assertEqual(config.library_path, "fixtures/videos.json")
```

- [ ] **Step 2: 再写一个失败测试，要求 fixture metadata 能从默认 JSON 读出**

```python
    def test_fixture_library_loads_default_videos_json(self):
        from backend.services.asset_providers.fixture import load_fixture_library

        entries = load_fixture_library()

        self.assertGreaterEqual(len(entries), 1)
        self.assertEqual(entries[0]["id"], "vid_001")
        self.assertIn("videoUrl", entries[0])
```

- [ ] **Step 3: 运行这两个测试，确认先失败**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_provider_config_uses_defaults \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_library_loads_default_videos_json
```

Expected: FAIL，原因是 `get_fixture_config`、`load_fixture_library` 还不存在。

- [ ] **Step 4: 写最小实现，让配置和 metadata 读取转绿**

实现要求：

- 在 `backend/services/asset_providers/config.py` 中新增：

```python
@dataclass(frozen=True)
class FixtureProviderConfig:
    enabled: bool
    library_path: str


def get_fixture_config() -> FixtureProviderConfig:
    ...
```

- 在 `backend/services/asset_providers/fixture.py` 中新增：
  - `load_fixture_library()`
  - 默认读取 `fixtures/videos.json`

- [ ] **Step 5: 重跑刚才两个测试，确认通过**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_provider_config_uses_defaults \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_library_loads_default_videos_json
```

Expected: PASS。

- [ ] **Step 6: 提交配置与 metadata 读取骨架**

```bash
git add backend/services/asset_providers/config.py backend/services/asset_providers/fixture.py tests/test_agent_backend.py
git commit -m "feat: add fixture provider config and library loader"
```

### Task 2: 实现 fixture candidate 匹配

**Files:**
- Modify: `backend/services/asset_providers/fixture.py`
- Modify: `tests/test_agent_backend.py`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: 写一个失败测试，要求 scene keywords 能匹配到 fixture candidates**

```python
    def test_fixture_search_returns_normalized_candidates(self):
        from backend.services.asset_providers.fixture import search_fixture_candidates

        candidates = search_fixture_candidates(["城市", "车流"], max_results=2)

        self.assertGreaterEqual(len(candidates), 1)
        self.assertEqual(candidates[0].provider, "fixture")
        self.assertEqual(candidates[0].id, "vid_001")
        self.assertTrue(candidates[0].source_url.endswith(".mp4"))
```

- [ ] **Step 2: 再写一个失败测试，要求无匹配时返回空列表**

```python
    def test_fixture_search_returns_empty_list_when_no_match(self):
        from backend.services.asset_providers.fixture import search_fixture_candidates

        candidates = search_fixture_candidates(["火星", "机甲"], max_results=3)

        self.assertEqual(candidates, [])
```

- [ ] **Step 3: 运行测试，确认先失败**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_search_returns_normalized_candidates \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_search_returns_empty_list_when_no_match
```

Expected: FAIL。

- [ ] **Step 4: 实现 deterministic token overlap 匹配**

实现要求：

- 增加 helper：
  - `normalize_fixture_tokens(text: str) -> list[str]`
  - `score_fixture_entry(entry, keywords) -> int`
- `search_fixture_candidates(...)` 需要：
  - 读取 library
  - 用 `title + description + tags` 聚合 candidate tokens
  - 返回按分数排序的 `AssetCandidate`
  - 分数为 0 的候选直接过滤掉

- [ ] **Step 5: 重跑测试，确认通过**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_search_returns_normalized_candidates \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_search_returns_empty_list_when_no_match
```

Expected: PASS。

- [ ] **Step 6: 提交 candidate 匹配实现**

```bash
git add backend/services/asset_providers/fixture.py tests/test_agent_backend.py
git commit -m "feat: add fixture candidate matching"
```

### Task 3: 实现 fixture 素材 copy / download 契约

**Files:**
- Modify: `backend/services/asset_providers/fixture.py`
- Modify: `tests/test_agent_backend.py`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: 写一个失败测试，要求 fixture download 会把素材复制到 `backend/downloads/...`**

```python
    def test_fixture_download_copies_asset_into_backend_downloads(self):
        from backend.services.asset_providers.fixture import download_fixture_candidate, search_fixture_candidates

        candidate = search_fixture_candidates(["城市", "车流"], max_results=1)[0]
        download = download_fixture_candidate("session", candidate, 1, "session_1_fixture_1.mp4")

        self.assertTrue(download.local_path.endswith("backend/downloads/session_1_fixture_1.mp4"))
        self.assertEqual(download.public_url, "/downloads/session_1_fixture_1.mp4")
        self.assertIn("provider", download.metadata)
```

- [ ] **Step 2: 再写一个失败测试，要求缺失 fixture 文件时抛清晰错误**

```python
    def test_fixture_download_raises_clear_error_when_source_file_missing(self):
        from backend.services.asset_providers.fixture import download_fixture_candidate
        from backend.services.asset_providers.types import AssetCandidate

        candidate = AssetCandidate(
            provider="fixture",
            id="missing",
            title="missing",
            source_url="/fixtures/missing.mp4",
            download_url="/fixtures/missing.mp4",
            duration=10,
        )

        with self.assertRaisesRegex(RuntimeError, "本地素材文件不存在"):
            download_fixture_candidate("session", candidate, 1, "missing.mp4")
```

- [ ] **Step 3: 运行测试，确认先失败**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_download_copies_asset_into_backend_downloads \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_download_raises_clear_error_when_source_file_missing
```

Expected: FAIL。

- [ ] **Step 4: 实现 fixture file 复制**

实现要求：

- 使用 `shutil.copyfile`
- 解析 `videoUrl` 到 repo 内 fixture 文件路径
- 复制到 `backend/downloads/<output_filename>`
- 返回 `AssetDownload`
- 对缺失源文件抛明确 `RuntimeError`

- [ ] **Step 5: 重跑测试，确认通过**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_download_copies_asset_into_backend_downloads \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_download_raises_clear_error_when_source_file_missing
```

Expected: PASS。

- [ ] **Step 6: 提交 fixture copy 契约**

```bash
git add backend/services/asset_providers/fixture.py tests/test_agent_backend.py
git commit -m "feat: add fixture asset copy flow"
```

### Task 4: 接入 search orchestration

**Files:**
- Modify: `backend/services/asset_providers/config.py`
- Modify: `backend/services/search_service.py`
- Modify: `tests/test_agent_backend.py`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: 写一个失败测试，要求 `fixture` provider 可以完成 `search_and_download_agent_clips(...)`**

```python
    def test_agent_download_can_complete_with_fixture_provider(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service

        scene = PlanScene(
            id=1,
            description="城市演示镜头",
            keywords=["城市", "车流"],
            duration=6,
            searchQuery="城市 车流",
        )

        with patch.dict("os.environ", {"CLIPFORGE_ASSET_PROVIDER_ORDER": "fixture"}, clear=False):
            clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].sceneId, 1)
        self.assertEqual(clips[0].caption, "城市演示镜头")
        self.assertTrue(clips[0].localPath.endswith(".mp4"))
```

- [ ] **Step 2: 再写一个失败测试，要求 fixture 无匹配时会继续尝试下一个 provider**

```python
    def test_fixture_provider_falls_through_to_next_provider_when_no_match(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service
        from backend.services.asset_providers.types import AssetCandidate, AssetDownload

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )
        pexels_candidate = AssetCandidate(
            provider="pexels",
            id="101",
            title="Pexels video 101",
            source_url="https://www.pexels.com/video/demo-101/",
            download_url="https://videos.pexels.com/101.mp4",
            duration=14,
        )

        with patch.dict("os.environ", {"CLIPFORGE_ASSET_PROVIDER_ORDER": "fixture,pexels"}, clear=False), patch(
            "backend.services.search_service.search_pexels_candidates",
            return_value=[pexels_candidate],
        ), patch(
            "backend.services.search_service.download_pexels_candidate",
            return_value=AssetDownload(
                local_path="backend/downloads/session_3_pexels_1.mp4",
                public_url="/downloads/session_3_pexels_1.mp4",
                metadata=pexels_candidate.to_metadata(),
            ),
        ) as mock_download, patch(
            "backend.services.search_service.get_pexels_config",
        ) as mock_pexels_config:
            mock_pexels_config.return_value.enabled = True
            mock_pexels_config.return_value.api_key = "pexels-key"

            clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].sourceUrl, "https://www.pexels.com/video/demo-101/")
        self.assertEqual(mock_download.call_count, 1)
```

- [ ] **Step 3: 运行测试，确认先失败**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_download_can_complete_with_fixture_provider \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_provider_falls_through_to_next_provider_when_no_match
```

Expected: FAIL。

- [ ] **Step 4: 接入 `fixture` provider**

实现要求：

- `config.py`：
  - `DEFAULT_ASSET_PROVIDER_ORDER` 保持不变
  - `get_asset_provider_order()` 增加允许值 `fixture`
- `search_service.py`：
  - 引入 `search_fixture_candidates` / `download_fixture_candidate`
  - 在 provider loop 里识别 `fixture`
  - 行为与其他 provider 保持一致：有候选就尝试下载 / copy，无候选就继续下一个 provider

- [ ] **Step 5: 重跑测试，确认通过**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_download_can_complete_with_fixture_provider \
  tests.test_agent_backend.AgentExecutionContractTests.test_fixture_provider_falls_through_to_next_provider_when_no_match
```

Expected: PASS。

- [ ] **Step 6: 提交 orchestration 接入**

```bash
git add backend/services/asset_providers/config.py backend/services/search_service.py backend/services/asset_providers/fixture.py tests/test_agent_backend.py
git commit -m "feat: add deterministic fixture provider"
```

### Task 5: 更新 env / runbook 并做完整验证

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Verify: `tests/test_agent_backend.py`
- Verify: `scripts/check-product-pages.mjs`

- [ ] **Step 1: 更新 `.env.example`**

增加：

```bash
FIXTURE_PROVIDER_ENABLED=true
FIXTURE_LIBRARY_PATH=fixtures/videos.json
```

并把推荐 demo provider order 写成：

```bash
CLIPFORGE_ASSET_PROVIDER_ORDER=fixture,pexels,youtube
```

- [ ] **Step 2: 更新 `README.md`**

至少覆盖：

- deterministic fixture mode 的目的
- `FIXTURE_PROVIDER_ENABLED`
- `FIXTURE_LIBRARY_PATH`
- demo 推荐 provider order：`fixture,pexels,youtube`
- real run 推荐 provider order：`pexels,youtube`
- fixture mode 成功口径：能稳定走到 MP4

- [ ] **Step 3: 运行完整后端测试**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend
```

Expected: PASS。

- [ ] **Step 4: 运行前端生产构建和结构检查**

Run:

```bash
npm run build
node scripts/check-product-pages.mjs
```

Expected:

- build exit code 0
- `product page checks passed`

- [ ] **Step 5: 提交文档与 env 更新**

```bash
git add .env.example README.md tests/test_agent_backend.py backend/services/asset_providers/config.py backend/services/asset_providers/fixture.py backend/services/search_service.py
git commit -m "docs: add deterministic fixture fallback runbook"
```

---

## Self-Review

- 这份 plan 覆盖了 spec 的全部主线：fixture provider、本地 copy、provider order 接入、env、README、测试与验证。
- 范围刻意停在 backend provider，不会把工作膨胀到前端切换器或素材管理功能。
- 每个任务都按 TDD 拆成“先红后绿再提交”，符合当前仓库的推进方式。
- 与现有外部 provider 设计保持兼容，不需要改 public API 契约。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-07-deterministic-fixture-fallback.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

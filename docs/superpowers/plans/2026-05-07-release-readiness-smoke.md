# Release Readiness Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `master` 上建立一条基于 `fixture` 的最小 release-readiness smoke 基线，证明 ClipForge 的 API、worker、fixture provider 和渲染链路可以稳定产出 MP4，并在失败时给出清晰分类。

**Architecture:** 采用三层交付：先用后端契约测试锁定 deterministic fixture smoke 的关键行为；再新增一个 `scripts/` 下的集成 smoke runner，串起 API 创建、confirm、轮询和结果校验；最后更新 `README.md`，把 smoke/demo 模式和真实外部素材联调模式彻底分开说明。整个实现保持现有 API 契约和任务模型不变，不引入浏览器自动化。

**Tech Stack:** Python `unittest`, FastAPI, SQLAlchemy repositories, Celery worker, existing agent/task APIs, Node/Next.js build checks, existing `scripts/check-product-pages.mjs`, deterministic fixture provider.

---

## File Structure

- Modify: `tests/test_agent_backend.py`
  - 补最小 deterministic fixture smoke 契约，锁定 fixture-first 成功口径与结果路径。
- Create: `scripts/run_fixture_smoke.py`
  - 新增集成 smoke runner，调用现有 API 并轮询结果。
- Modify: `README.md`
  - 补 smoke runbook、模式分层、成功口径与失败分类。
- Verify: `backend/api/agent.py`
  - 只作为脚本接口来源，不预设修改。
- Verify: `backend/services/agent_execution_service.py`
  - 只作为 confirm / enqueue 现有链路参考，不预设修改。
- Verify: `backend/services/agent_task_read_service.py`
  - 只作为脚本读取任务详情和结果的参考，不预设修改。
- Verify: `tests/test_agent_api_p0.py`
  - 参考现有 API 风格和基础设施文档测试，不预设修改。
- Verify: `scripts/check-product-pages.mjs`
  - 保持现有前端结构验收。

---

### Task 1: 锁定 deterministic fixture smoke 的测试契约

**Files:**
- Modify: `tests/test_agent_backend.py`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: 添加一个失败测试，要求 fixture-first 成功 run 必须留下可校验的视频结果**

在 `FrontendClientContractTests` 之后、现有 fixture/provider 测试附近增加一个新的后端契约测试，形态参考：

```python
    def test_fixture_smoke_success_contract_produces_result_video_path(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        async def fake_search(session_id, scenes):
            return [
                {
                    "sceneId": scenes[0].id,
                    "sourceUrl": "/fixtures/vid_001.mp4",
                    "localPath": "backend/downloads/session_fixture_1.mp4",
                    "publicUrl": "/downloads/session_fixture_1.mp4",
                    "duration": 6.0,
                    "sourceDuration": 6.0,
                    "trimStart": 0.0,
                    "trimDuration": 6.0,
                }
            ]

        async def fake_render(session_id, clips, output_filename):
            return f"/output/{output_filename}"

        service = AgentService()
        session = service.create_session("做一个 fixture smoke 测试短片")
        service.confirm_session(session.id)

        updated = asyncio.run(service.run_confirmed_session(session.id, fake_search, fake_render))

        self.assertEqual(updated.status, AgentStatus.DONE)
        self.assertEqual(updated.videoUrl, f"/output/{session.id}.mp4")
        self.assertEqual(updated.currentStep, "完成")
        self.assertGreater(len(updated.clips), 0)
```

- [ ] **Step 2: 再添加一个失败测试，要求 README 必须区分 smoke 模式和真实外部素材联调模式**

在 `tests/test_agent_api_p0.py` 里的文档测试风格基础上，为 `tests/test_agent_backend.py` 新增一个文本契约测试：

```python
    def test_readme_distinguishes_fixture_smoke_mode_from_real_provider_mode(self):
        content = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Smoke / demo mode", content)
        self.assertIn("Real external-provider validation", content)
        self.assertIn("fixture,pexels,youtube", content)
        self.assertIn("pexels,youtube", content)
```

如果更贴当前 README 中文表达，也可以改成断言中文标题，但要确保 smoke 模式和真实外部模式是分开的。

- [ ] **Step 3: 运行新增测试，确认先失败**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentSessionTests.test_fixture_smoke_success_contract_produces_result_video_path \
  tests.test_agent_backend.FrontendClientContractTests.test_readme_distinguishes_fixture_smoke_mode_from_real_provider_mode
```

Expected: FAIL，原因是测试函数尚未存在，README 也还没有对应 smoke / real-provider 模式标题。

- [ ] **Step 4: 提交测试基线**

```bash
git add tests/test_agent_backend.py
git commit -m "test: lock release readiness smoke contract"
```

### Task 2: 补齐 smoke 契约并让测试转绿

**Files:**
- Modify: `tests/test_agent_backend.py`
- Modify: `README.md`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: 在 `tests/test_agent_backend.py` 中加入新的 fixture smoke 成功契约测试**

把 Task 1 Step 1 中定义的测试真正写入合适的测试类。优先放在已有 `run_confirmed_session` 测试附近，保持语义聚合。

- [ ] **Step 2: 在 `README.md` 中加入清晰的模式分层标题**

在 deterministic fixture mode 附近，显式补这类结构：

```md
### Operating modes

#### Smoke / demo mode

推荐配置：

```bash
FIXTURE_PROVIDER_ENABLED=true
FIXTURE_LIBRARY_PATH=fixtures/videos.json
CLIPFORGE_ASSET_PROVIDER_ORDER=fixture,pexels,youtube
```

这条链路用于 release-readiness smoke、本地演示和稳定出片验证。

#### Real external-provider validation

推荐配置：

```bash
CLIPFORGE_ASSET_PROVIDER_ORDER=pexels,youtube
```

这条链路用于验证真实外部素材搜索与下载，不作为稳定 smoke 基线。
```

保持原有 README 信息，只是把模式分层说得更明确。

- [ ] **Step 3: 运行 Task 1 的两个测试，确认转绿**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentSessionTests.test_fixture_smoke_success_contract_produces_result_video_path \
  tests.test_agent_backend.FrontendClientContractTests.test_readme_distinguishes_fixture_smoke_mode_from_real_provider_mode
```

Expected: PASS。

- [ ] **Step 4: 提交 smoke 契约补齐**

```bash
git add tests/test_agent_backend.py README.md
git commit -m "docs: define smoke and provider validation modes"
```

### Task 3: 添加集成 smoke runner 脚本

**Files:**
- Create: `scripts/run_fixture_smoke.py`
- Test: `scripts/run_fixture_smoke.py`

- [ ] **Step 1: 先写一个失败测试，锁定脚本入口和关键输出文案**

在 `tests/test_agent_backend.py` 新增一个轻量文本契约测试：

```python
    def test_fixture_smoke_script_exists_with_expected_cli_terms(self):
        content = (ROOT / "scripts" / "run_fixture_smoke.py").read_text(encoding="utf-8")

        self.assertIn("argparse", content)
        self.assertIn("http://127.0.0.1:8010", content)
        self.assertIn("/api/agent/sessions", content)
        self.assertIn("SMOKE OK", content)
        self.assertIn("SMOKE FAILED", content)
```

- [ ] **Step 2: 运行测试，确认脚本缺失导致失败**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_fixture_smoke_script_exists_with_expected_cli_terms
```

Expected: FAIL，原因是 `scripts/run_fixture_smoke.py` 尚不存在。

- [ ] **Step 3: 创建 `scripts/run_fixture_smoke.py`，先实现最小可读 CLI 骨架**

脚本至少应包含：

```python
#!/usr/bin/env python3
import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_API_ORIGIN = "http://127.0.0.1:8010"
DEFAULT_TIMEOUT_SECONDS = 90
DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_BRIEF = "做一个 30 秒的城市科技感短片，使用稳定 fixture 素材完成 smoke 验证。"


def parse_args():
    parser = argparse.ArgumentParser(description="Run ClipForge fixture smoke flow against local services.")
    parser.add_argument("--api-origin", default=DEFAULT_API_ORIGIN)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--brief", default=DEFAULT_BRIEF)
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"Starting fixture smoke against {args.api_origin}")
    print("SMOKE FAILED: not implemented")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

先让脚本文件存在，并带上之后需要的核心常量和输出词。

- [ ] **Step 4: 运行脚本契约测试，确认转绿**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_fixture_smoke_script_exists_with_expected_cli_terms
```

Expected: PASS。

- [ ] **Step 5: 提交脚本骨架**

```bash
git add scripts/run_fixture_smoke.py tests/test_agent_backend.py
git commit -m "feat: add fixture smoke runner skeleton"
```

### Task 4: 完成 smoke runner 的 API 流程和失败分类

**Files:**
- Modify: `scripts/run_fixture_smoke.py`
- Test: `scripts/run_fixture_smoke.py`

- [ ] **Step 1: 实现通用 JSON 请求辅助函数**

在脚本里加入：

```python
def request_json(method: str, url: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))
```

并在外层捕获 `HTTPError` / `URLError`，统一转成脚本自己的失败摘要。

- [ ] **Step 2: 实现创建 session、confirm session、读取 session / events / task 的流程**

脚本主流程建议：

```python
create_payload = request_json("POST", f"{api_origin}/api/agent/sessions", {"message": brief})
session_id = create_payload["id"]

confirmed = request_json("POST", f"{api_origin}/api/agent/sessions/{session_id}/confirm")
job_id = confirmed.get("activeJobId")

while time.time() < deadline:
    session_payload = request_json("GET", f"{api_origin}/api/agent/sessions/{session_id}")
    events_payload = request_json("GET", f"{api_origin}/api/agent/sessions/{session_id}/events")
    task_payload = request_json("GET", f"{api_origin}/api/agent/tasks/{job_id}") if job_id else None
    ...
```

轮询直到：
- session `status == "done"`
- session `status == "failed"`
- 超时

- [ ] **Step 3: 实现输出文件验证**

成功时，脚本至少检查：

```python
video_url = session_payload.get("videoUrl") or (task_payload or {}).get("videoUrl")
if not video_url:
    fail("result_missing", "session/task 已完成，但没有 videoUrl")

output_path = Path("backend/output") / f"{session_id}.mp4"
if not output_path.exists():
    fail("artifact_missing", f"输出文件不存在: {output_path}")
```

保持和当前 worker 的输出约定一致，不为脚本额外改 schema。

- [ ] **Step 4: 实现统一的失败分类输出**

脚本输出结构建议：

```python
def print_failure(kind: str, message: str, session_payload=None, task_payload=None, events=None):
    print(f"SMOKE FAILED [{kind}] {message}")
    if session_payload:
        print(f"session_status={session_payload.get('status')} current_step={session_payload.get('currentStep')}")
    if task_payload:
        print(f"task_status={task_payload.get('status')} task_step={task_payload.get('currentStep')}")
    if events:
        for item in events[-5:]:
            print(f"- {item.get('eventType')} {item.get('step')} {item.get('message')}")
```

建议至少覆盖这些 `kind`：
- `api_error`
- `timeout`
- `job_missing`
- `session_failed`
- `artifact_missing`

- [ ] **Step 5: 成功时输出清晰摘要**

成功输出建议：

```python
print("SMOKE OK")
print(f"session_id={session_id}")
print(f"job_id={job_id}")
print(f"video_url={video_url}")
print(f"output_path={output_path}")
```

- [ ] **Step 6: 本地跑一次脚本的 `--help`，确认 CLI 可用**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python scripts/run_fixture_smoke.py --help
```

Expected: exit code 0，并显示参数帮助。

- [ ] **Step 7: 提交脚本完整实现**

```bash
git add scripts/run_fixture_smoke.py
git commit -m "feat: add fixture smoke runner"
```

### Task 5: 更新 README smoke runbook

**Files:**
- Modify: `README.md`
- Test: `README.md`

- [ ] **Step 1: 在 README 中加入独立 smoke runbook 小节**

建议新增一节：

```md
### Release-readiness smoke

这条链路用于验证 ClipForge 主干工作流是否仍能稳定出片，不依赖外部素材 provider。

推荐环境变量：

```bash
export FIXTURE_PROVIDER_ENABLED=true
export FIXTURE_LIBRARY_PATH=fixtures/videos.json
export CLIPFORGE_ASSET_PROVIDER_ORDER=fixture,pexels,youtube
export CLIPFORGE_CELERY_QUEUE=clipforge-agent-smoke
export CELERY_BROKER_URL=redis://localhost:6379/1
export CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

启动 backend、worker、frontend 后，运行：

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python scripts/run_fixture_smoke.py --api-origin http://127.0.0.1:8010
```

成功口径：
- 输出 `SMOKE OK`
- 返回 `session_id`、`job_id`、`video_url`
- `backend/output/<session_id>.mp4` 存在
```

- [ ] **Step 2: 明确失败口径**

README 里同时写清：
- fixture smoke 成功只代表工作流和渲染主干健康
- 不代表真实外部 provider 也稳定
- `pexels,youtube` 仍属于真实外部素材联调模式

- [ ] **Step 3: 运行 README smoke 模式相关契约测试**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_readme_distinguishes_fixture_smoke_mode_from_real_provider_mode
```

Expected: PASS。

- [ ] **Step 4: 提交 README 更新**

```bash
git add README.md
git commit -m "docs: add release readiness smoke runbook"
```

### Task 6: 最终验收与交付总结

**Files:**
- Verify only

- [ ] **Step 1: 运行完整后端契约测试**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend
```

Expected: PASS。

- [ ] **Step 2: 运行前端生产构建**

Run:

```bash
npm run build
```

Expected: exit code 0。

- [ ] **Step 3: 运行产品页面结构检查**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: `product page checks passed`。

- [ ] **Step 4: 在本地服务已启动的前提下执行真实 fixture smoke**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python scripts/run_fixture_smoke.py --api-origin http://127.0.0.1:8010
```

Expected: 输出 `SMOKE OK`，并打印 `session_id`、`job_id`、`video_url`、`output_path`。

- [ ] **Step 5: 汇总结论**

最终总结必须明确回答：
- fixture smoke 基线是否已建立
- smoke 脚本成功/失败时如何判读
- README 是否已把 smoke 与真实 provider 模式区分清楚
- 下一步是否要继续做 CI 接入或浏览器级 smoke

---

## Self-Review

- 这个计划保持了 spec 的三层结构：测试层、脚本层、文档层。
- 范围没有扩到浏览器自动化或新的 UI 功能。
- 所有实现都基于现有 API 契约和 worker 输出约定，不要求新增 schema。
- 计划默认先用 TDD 锁契约，再补脚本和文档，符合当前仓库节奏。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-07-release-readiness-smoke.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

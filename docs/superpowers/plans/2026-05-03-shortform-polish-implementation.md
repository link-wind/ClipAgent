# Shortform Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ClipForge 的 9:16 智能短片增加轻量字幕、通用背景音乐，以及更清晰的前端进度和结果展示。

**Architecture:** 保持现有短片裁剪主链路不变，在 clip metadata 中补充 `caption`，由渲染层在逐段标准化时叠加字幕、在全片阶段混入默认 BGM；前端继续消费 session 快照和 events，只增强展示，不引入新的编辑交互。为了控制复杂度，本阶段只支持一套固定字幕样式和一条默认 BGM 资源。

**Tech Stack:** Python, FastAPI, Celery, ffmpeg-python, SQLAlchemy, Next.js, Zustand, unittest

---

## File Structure

### Files to create

- `backend/assets/audio/default_bgm.mp3`
  - 轻量通用背景音乐资源。

### Files to modify

- `backend/models/agent.py`
  - 扩展 `ClipInfo`，增加 `caption` 字段。
- `backend/services/search_service.py`
  - 为 clip 构造默认 `caption`。
- `backend/tasks/agent_tasks.py`
  - 持久化 clip artifact 时写入 `caption`，并在渲染阶段记录更细事件。
- `backend/services/agent_progress_service.py`
  - 复用现有事件记录方法，支持更细的渲染阶段消息。
- `backend/services/agent_read_service.py`
  - 从 artifact metadata 中读回 `caption`。
- `backend/services/render_service.py`
  - 在片段标准化时叠加字幕，在最终输出时混入默认 BGM。
- `src/lib/agentApi.ts`
  - 同步前端 `ClipInfo` 类型，增加 `caption / sourceDuration / trimStart / trimDuration`。
- `src/components/agent/ProgressPanel.tsx`
  - 优化渲染阶段文案和事件展示。
- `src/components/agent/ResultPanel.tsx`
  - 增加 clip 清单和字幕/裁剪信息展示。
- `src/components/agent/ResultPanel.module.css`
  - 为 clip 清单增加样式。
- `tests/test_agent_jobs.py`
  - 补字幕、BGM、metadata、事件增强相关回归测试。

### Files intentionally not changed in this phase

- `src/components/agent/AgentChat.tsx`
  - 本阶段不增加交互编辑。
- `src/stores/useAgentStore.ts`
  - 现有事件和 session 状态已足够承载展示增强。
- `backend/api/agent.py`
  - 不新增接口。

---

### Task 1: Extend ClipInfo and frontend type with caption metadata

**Files:**
- Modify: `backend/models/agent.py`
- Modify: `src/lib/agentApi.ts`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
class ClipCaptionContractTests(unittest.TestCase):
    def test_clip_info_supports_caption(self):
        from backend.models.agent import ClipInfo

        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/video",
            localPath="backend/downloads/demo.mp4",
            publicUrl="/downloads/demo.mp4",
            duration=6.0,
            sourceDuration=18.0,
            trimStart=4.2,
            trimDuration=6.0,
            caption="开场建立氛围",
        )

        self.assertEqual(clip.caption, "开场建立氛围")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `..\..\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.ClipCaptionContractTests.test_clip_info_supports_caption -v`  
Expected: FAIL with missing `caption`

- [ ] **Step 3: Write minimal implementation**

在 `backend/models/agent.py` 中扩展：

```python
class ClipInfo(BaseModel):
    sceneId: int
    sourceUrl: str
    localPath: str
    publicUrl: str
    startTime: float = 0.0
    duration: float = 6.0
    sourceDuration: float = 0.0
    trimStart: float = 0.0
    trimDuration: float = 6.0
    caption: str = ""
```

在 `src/lib/agentApi.ts` 中同步：

```ts
export interface ClipInfo {
  sceneId: number
  sourceUrl: string
  localPath: string
  publicUrl: string
  startTime: number
  duration: number
  sourceDuration: number
  trimStart: number
  trimDuration: number
  caption: string
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `..\..\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.ClipCaptionContractTests.test_clip_info_supports_caption -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/models/agent.py src/lib/agentApi.ts tests/test_agent_jobs.py
git commit -m "feat: extend clip metadata with captions"
```

---

### Task 2: Populate caption in search clips and persist it to artifacts

**Files:**
- Modify: `backend/services/search_service.py`
- Modify: `backend/tasks/agent_tasks.py`
- Modify: `backend/services/agent_read_service.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
class ClipCaptionPersistenceTests(unittest.TestCase):
    def test_search_and_download_agent_clips_uses_scene_description_as_caption(self):
        from backend.models.agent import PlanScene
        from backend.services.search_service import search_and_download_agent_clips

        async def run_test():
            scenes = [
                PlanScene(
                    id=1,
                    description="开场建立氛围",
                    keywords=["city"],
                    duration=6.0,
                    searchQuery="city motion",
                )
            ]

            with patch("backend.services.search_service.search_youtube") as mock_search, patch(
                "backend.services.search_service.download_video",
                new_callable=AsyncMock,
            ) as mock_download:
                mock_search.return_value = [
                    {
                        "id": "abc",
                        "title": "demo",
                        "url": "https://example.com/watch?v=abc",
                        "duration": 20.0,
                    }
                ]
                mock_download.return_value = "backend/downloads/demo.mp4"

                clips = await search_and_download_agent_clips("session-1", scenes)

            self.assertEqual(clips[0].caption, "开场建立氛围")

        asyncio.run(run_test())
```

再扩展持久化回归：

```python
self.assertEqual(clip_artifact.metadata_json["caption"], "开场建立氛围")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `..\..\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.ClipCaptionPersistenceTests -v`  
Expected: FAIL because `caption` is missing in search output and artifact metadata

- [ ] **Step 3: Write minimal implementation**

在 `backend/services/search_service.py` 构造 `AgentClipInfo(...)` 时增加：

```python
caption=scene.description,
```

在 `backend/tasks/agent_tasks.py` 持久化 clip artifact 时增加：

```python
metadata={
    "caption": clip.caption,
    "sourceDuration": clip.sourceDuration,
    "trimStart": clip.trimStart,
    "trimDuration": clip.trimDuration,
}
```

在 `backend/services/agent_read_service.py` 中读回：

```python
caption=str(metadata.get("caption", "") or ""),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `..\..\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.ClipCaptionPersistenceTests -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/search_service.py backend/tasks/agent_tasks.py backend/services/agent_read_service.py tests/test_agent_jobs.py
git commit -m "feat: persist captions in clip artifacts"
```

---

### Task 3: Add render command metadata for captions and background music

**Files:**
- Modify: `backend/services/render_service.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
class RenderPolishCommandTests(unittest.TestCase):
    def test_build_render_commands_includes_caption_and_bgm(self):
        from backend.models.agent import ClipInfo
        from backend.services.render_service import build_render_commands

        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/1",
            localPath="backend/downloads/1.mp4",
            publicUrl="/downloads/1.mp4",
            duration=6.0,
            sourceDuration=20.0,
            trimStart=4.9,
            trimDuration=6.0,
            caption="开场建立氛围",
        )

        commands = build_render_commands([clip], "backend/output/final.mp4")

        self.assertEqual(commands["segments"][0]["caption"], "开场建立氛围")
        self.assertIn("bgm", commands)
        self.assertTrue(commands["bgm"]["path"].endswith("default_bgm.mp3"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `..\..\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.RenderPolishCommandTests.test_build_render_commands_includes_caption_and_bgm -v`  
Expected: FAIL because render commands do not include caption or bgm metadata

- [ ] **Step 3: Write minimal implementation**

在 `backend/services/render_service.py` 中：

1. 增加常量：

```python
BGM_PATH = "backend/assets/audio/default_bgm.mp3"
```

2. 更新 `build_render_commands(...)`：

```python
return {
    "segments": [
        {
            "input": _clip_input_path(clip),
            "trimStart": _clip_trim_start(clip),
            "trimDuration": _clip_trim_duration(clip),
            "caption": getattr(clip, "caption", ""),
        }
        for clip in clips
    ],
    "output": {
        ...
    },
    "bgm": {
        "path": BGM_PATH,
        "volume": 0.18,
    },
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `..\..\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.RenderPolishCommandTests.test_build_render_commands_includes_caption_and_bgm -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/render_service.py tests/test_agent_jobs.py
git commit -m "test: describe caption and bgm render config"
```

---

### Task 4: Add subtitles and BGM mixing to render pipeline

**Files:**
- Create: `backend/assets/audio/default_bgm.mp3`
- Modify: `backend/services/render_service.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
class RenderOverlayContractTests(unittest.TestCase):
    def test_render_shortform_video_requires_bgm_asset(self):
        from backend.services.render_service import BGM_PATH

        self.assertTrue(os.path.exists(BGM_PATH), f"missing {BGM_PATH}")
```

以及一个最小行为测试：

```python
class RenderOverlayContractTests(unittest.TestCase):
    def test_render_commands_preserve_caption_text_for_overlay(self):
        from backend.models.agent import ClipInfo
        from backend.services.render_service import build_render_commands

        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/1",
            localPath="backend/downloads/1.mp4",
            publicUrl="/downloads/1.mp4",
            duration=6.0,
            sourceDuration=20.0,
            trimStart=1.0,
            trimDuration=6.0,
            caption="开场建立氛围",
        )

        commands = build_render_commands([clip], "backend/output/final.mp4")
        self.assertEqual(commands["segments"][0]["caption"], "开场建立氛围")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `..\..\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.RenderOverlayContractTests -v`  
Expected: FAIL because BGM asset does not exist yet

- [ ] **Step 3: Write minimal implementation**

1. 新增文件：

- `backend/assets/audio/default_bgm.mp3`

2. 在 `backend/services/render_service.py` 中：

- 在 `_render_segment(...)` 的视频流上添加 `drawtext`
- 使用 caption 全时长显示
- 在最终合并阶段引入 BGM 音轨

字幕示例实现方向：

```python
video_stream = video_stream.filter(
    "drawtext",
    text=caption,
    fontcolor="white",
    fontsize=42,
    x="(w-text_w)/2",
    y="h-(text_h*2)-48",
    box=1,
    boxcolor="black@0.45",
    boxborderw=18,
)
```

BGM 混音示例实现方向：

```python
bgm_input = ffmpeg.input(BGM_PATH, stream_loop=-1)
bgm_audio = (
    bgm_input.audio
    .filter("atrim", duration=total_duration)
    .filter("volume", 0.18)
    .filter("aresample", 44100)
)

mixed_audio = ffmpeg.filter(
    [main_audio, bgm_audio],
    "amix",
    inputs=2,
    duration="first",
    dropout_transition=0,
)
```

如果实现时需要先产出无 BGM 的标准化片段、再统一混音，优先选择更稳的方案。

- [ ] **Step 4: Run test to verify it passes**

Run: `..\..\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.RenderOverlayContractTests -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/assets/audio/default_bgm.mp3 backend/services/render_service.py tests/test_agent_jobs.py
git commit -m "feat: add subtitles and bgm to shortform render"
```

---

### Task 5: Emit finer rendering events for progress panel

**Files:**
- Modify: `backend/tasks/agent_tasks.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

在现有 `AgentExecutionWorkerTests.test_run_agent_job_persists_success_state_events_and_artifacts` 中扩展预期事件：

```python
self.assertIn("render_captioning", event_types)
self.assertIn("render_audio_mix", event_types)
```

或者明确成：

```python
messages = [row.message for row in event_repo.list_for_session(session_id)]
self.assertIn("正在合成字幕", messages)
self.assertIn("正在混合背景音乐", messages)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `..\..\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.AgentExecutionWorkerTests.test_run_agent_job_persists_success_state_events_and_artifacts -v`  
Expected: FAIL because these finer events are not recorded yet

- [ ] **Step 3: Write minimal implementation**

在 `backend/tasks/agent_tasks.py` 中，在 `mark_render_started(...)` 之后、`render_video(...)` 前后增加：

```python
progress_service.record_event(
    session_id=session_id,
    job_id=job_id,
    event_type="render_captioning",
    step="rendering",
    message="正在合成字幕",
    progress=82,
)
db.commit()

progress_service.record_event(
    session_id=session_id,
    job_id=job_id,
    event_type="render_audio_mix",
    step="rendering",
    message="正在混合背景音乐",
    progress=88,
)
db.commit()
```

不要新增新的 session 状态枚举，只补事件和消息。

- [ ] **Step 4: Run test to verify it passes**

Run: `..\..\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.AgentExecutionWorkerTests.test_run_agent_job_persists_success_state_events_and_artifacts -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tasks/agent_tasks.py tests/test_agent_jobs.py
git commit -m "feat: emit detailed rendering progress events"
```

---

### Task 6: Show richer progress and clip summary in the frontend

**Files:**
- Modify: `src/components/agent/ProgressPanel.tsx`
- Modify: `src/components/agent/ResultPanel.tsx`
- Modify: `src/components/agent/ResultPanel.module.css`
- Modify: `src/lib/agentApi.ts`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Add a lightweight frontend contract test**

在 `tests/test_agent_jobs.py` 中增加源码契约检查：

```python
class FrontendPolishContractTests(unittest.TestCase):
    def test_result_panel_references_caption_and_trim_fields(self):
        source = Path("src/components/agent/ResultPanel.tsx").read_text(encoding="utf-8")
        self.assertIn("caption", source)
        self.assertIn("trimStart", source)
        self.assertIn("trimDuration", source)

    def test_progress_panel_mentions_render_captioning_and_audio_mix(self):
        source = Path("src/components/agent/ProgressPanel.tsx").read_text(encoding="utf-8")
        self.assertIn("正在合成字幕", source)
        self.assertIn("正在混合背景音乐", source)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `..\..\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.FrontendPolishContractTests -v`  
Expected: FAIL because the frontend has not been updated yet

- [ ] **Step 3: Write minimal implementation**

在 `src/components/agent/ProgressPanel.tsx` 中：

- 保留进度条和大阶段
- 最近事件区优先显示最新 4-5 条事件
- 对 `render_captioning` / `render_audio_mix` 消息直接展示

在 `src/components/agent/ResultPanel.tsx` 中：

- 在 video 下方增加 clip 列表
- 每段显示：
  - `clip.caption`
  - `clip.duration`
  - `clip.sourceDuration`
  - `clip.trimStart`
  - `clip.trimDuration`

可按类似结构渲染：

```tsx
<ul>
  {session?.clips.map((clip) => (
    <li key={`${clip.sceneId}-${clip.publicUrl}`}>
      <strong>{clip.caption || `场景 ${clip.sceneId}`}</strong>
      <span>目标时长 {clip.duration.toFixed(1)}s</span>
      <span>原始时长 {clip.sourceDuration.toFixed(1)}s</span>
      <span>裁剪起点 {clip.trimStart.toFixed(1)}s</span>
      <span>裁剪时长 {clip.trimDuration.toFixed(1)}s</span>
    </li>
  ))}
</ul>
```

样式只做清晰和紧凑，不要额外营销化。

- [ ] **Step 4: Run test to verify it passes**

Run: `..\..\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.FrontendPolishContractTests -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/components/agent/ProgressPanel.tsx src/components/agent/ResultPanel.tsx src/components/agent/ResultPanel.module.css src/lib/agentApi.ts tests/test_agent_jobs.py
git commit -m "feat: show caption and trim details in agent ui"
```

---

### Task 7: Run end-to-end verification for polished shortform output

**Files:**
- Modify: `tests/test_agent_jobs.py`
- Modify: `docs/superpowers/specs/2026-05-03-shortform-polish-design.md`
- Modify: `docs/superpowers/plans/2026-05-03-shortform-polish-implementation.md`

- [ ] **Step 1: Run the focused regression suite**

Run: `..\..\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs -v`  
Expected: PASS

- [ ] **Step 2: Run a real worker-backed manual flow**

前置条件：

```powershell
docker compose up -d postgres redis
..\..\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
..\..\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8010
..\..\.venv\Scripts\python.exe -m celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO
```

如果同时运行多个 worktree，建议为当前工作区设置独立的 `CELERY_BROKER_URL` Redis DB 或 `CLIPFORGE_CELERY_QUEUE`，避免不同 worker 抢同一条任务。自定义队列名时，后端 API 进程和 worker 进程都要使用同一个环境变量值。

Run:

```powershell
..\..\.venv\Scripts\python.exe -c "import json, urllib.request; data=json.dumps({'message':'做一个带字幕和背景音乐的竖屏短片'}).encode(); req=urllib.request.Request('http://127.0.0.1:8010/api/agent/sessions', data=data, headers={'Content-Type':'application/json'}); print(urllib.request.urlopen(req).read().decode())"
```

记录 `session_id` 后执行：

```powershell
..\..\.venv\Scripts\python.exe -c "import urllib.request; session_id='<替换成上一步的 session_id>'; req=urllib.request.Request(f'http://127.0.0.1:8010/api/agent/sessions/{session_id}/confirm', data=b'', method='POST'); print(urllib.request.urlopen(req).read().decode())"
```

Expected: session 状态进入 `queued -> searching -> rendering -> done`

- [ ] **Step 3: Verify output still stays vertical and near target duration**

Run:

```powershell
ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 backend/output/<session_id>.mp4
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 backend/output/<session_id>.mp4
```

Expected:

- 分辨率仍为 `720,1280` 或同级竖屏比例
- 时长仍接近 30 秒

- [ ] **Step 4: Manually verify subtitles and BGM exist**

检查：

- 视频播放时能看到字幕
- 视频有背景音乐
- 前端结果面板能看到 clip 清单和字幕/裁剪信息

如果前端验证要补命令，可打开本地页面手动检查，不要求额外自动化。

- [ ] **Step 5: Commit**

```bash
git add backend/models/agent.py backend/services/search_service.py backend/tasks/agent_tasks.py backend/services/agent_read_service.py backend/services/render_service.py backend/assets/audio/default_bgm.mp3 src/lib/agentApi.ts src/components/agent/ProgressPanel.tsx src/components/agent/ResultPanel.tsx src/components/agent/ResultPanel.module.css tests/test_agent_jobs.py docs/superpowers/specs/2026-05-03-shortform-polish-design.md docs/superpowers/plans/2026-05-03-shortform-polish-implementation.md
git commit -m "feat: polish shortform output with subtitles and bgm"
```

---

## Self-Review

### Spec coverage

这个计划覆盖了 spec 中的全部目标：

- 字幕：Tasks 1-4
- BGM：Tasks 3-4
- 更细事件：Task 5
- 结果展示：Task 6
- 真实联调验证：Task 7

没有遗漏“保持 30 秒竖屏能力不退化”的要求。

### Placeholder scan

计划没有 `TBD`、`TODO`、"适当处理" 这类空描述。每个任务都指定了确切文件、测试命令和预期结果。

### Type consistency

全程统一使用：

- `caption`
- `sourceDuration`
- `trimStart`
- `trimDuration`

前后端 `ClipInfo`、artifact metadata 和结果展示保持同一套字段命名。

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-03-shortform-polish-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

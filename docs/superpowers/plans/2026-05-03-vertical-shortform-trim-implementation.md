# Vertical Shortform Trim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 ClipForge Agent 输出真正按场景时长裁剪的 9:16 竖屏短片，而不是把整段素材直接拼接成超长视频。

**Architecture:** 保持现有搜索、下载、Celery 执行和持久化链路不变，只在素材模型、搜索下载阶段和渲染阶段补齐“可剪辑元数据”和“标准化短片渲染”能力。搜索层负责生成 `sourceDuration / trimStart / trimDuration`，渲染层负责按这些元数据裁剪、竖屏化并合成最终短片。

**Tech Stack:** Python, FastAPI, Celery, SQLAlchemy, ffmpeg-python, yt-dlp, unittest

---

## File Structure

### Files to modify

- `backend/models/agent.py`
  - 扩展 `ClipInfo`，增加基础裁剪元数据字段。
- `backend/services/search_service.py`
  - 为下载完成的素材补充原始时长、默认裁剪起点和实际裁剪时长。
- `backend/services/render_service.py`
  - 用 `trim + scale + crop + fps + concat` 生成真正的竖屏短片。
- `backend/tasks/agent_tasks.py`
  - 持久化素材产物时把裁剪元数据写入 artifact metadata。
- `backend/services/agent_progress_service.py`
  - 复用现有 artifact metadata 写入，不需要大改，但要保证调用参数能透传。
- `backend/services/agent_read_service.py`
  - 从 artifact metadata 读回裁剪元数据，映射回 `ClipInfo`。
- `tests/test_agent_jobs.py`
  - 为裁剪元数据和渲染行为补回归测试。

### Files intentionally not changed in this phase

- `src/components/**`
  - 前端只消费已有会话结构，本阶段不做页面改造。
- `backend/api/**`
  - API 不需要新增端点。
- `backend/db/models.py`
  - 本阶段依赖 `agent_artifacts.metadata_json` 复用存储裁剪元数据，不新增列。

---

### Task 1: Extend ClipInfo with trim metadata

**Files:**
- Modify: `backend/models/agent.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
class ClipInfoContractTests(unittest.TestCase):
    def test_clip_info_supports_trim_metadata(self):
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
        )

        self.assertEqual(clip.sourceDuration, 18.0)
        self.assertEqual(clip.trimStart, 4.2)
        self.assertEqual(clip.trimDuration, 6.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.ClipInfoContractTests.test_clip_info_supports_trim_metadata -v`  
Expected: FAIL with `ValidationError` or unexpected keyword argument for the new fields

- [ ] **Step 3: Write minimal implementation**

在 `backend/models/agent.py` 中把 `ClipInfo` 改成：

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.ClipInfoContractTests.test_clip_info_supports_trim_metadata -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/models/agent.py tests/test_agent_jobs.py
git commit -m "feat: extend clip info with trim metadata"
```

---

### Task 2: Add pure trim calculation helpers in search_service

**Files:**
- Modify: `backend/services/search_service.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
class ClipTrimCalculationTests(unittest.TestCase):
    def test_calculate_trim_window_prefers_middle_front_for_long_source(self):
        from backend.services.search_service import calculate_trim_window

        trim_start, trim_duration = calculate_trim_window(
            source_duration=20.0,
            target_duration=6.0,
        )

        self.assertAlmostEqual(trim_start, 4.9)
        self.assertEqual(trim_duration, 6.0)

    def test_calculate_trim_window_uses_full_source_when_shorter_than_target(self):
        from backend.services.search_service import calculate_trim_window

        trim_start, trim_duration = calculate_trim_window(
            source_duration=4.5,
            target_duration=6.0,
        )

        self.assertEqual(trim_start, 0.0)
        self.assertEqual(trim_duration, 4.5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.ClipTrimCalculationTests -v`  
Expected: FAIL with missing `calculate_trim_window`

- [ ] **Step 3: Write minimal implementation**

在 `backend/services/search_service.py` 增加两个纯函数：

```python
def normalize_duration(value: object) -> float:
    # 统一时长值，避免 None 和负数
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, duration)


def calculate_trim_window(source_duration: float, target_duration: float) -> tuple[float, float]:
    # 为长素材计算默认裁剪区间
    source_duration = normalize_duration(source_duration)
    target_duration = normalize_duration(target_duration)

    if source_duration <= 0.0:
        return 0.0, 0.0
    if target_duration <= 0.0:
        return 0.0, source_duration
    if source_duration <= target_duration:
        return 0.0, source_duration

    available = source_duration - target_duration
    trim_start = max(0.0, available * 0.35)
    return trim_start, target_duration
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.ClipTrimCalculationTests -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/search_service.py tests/test_agent_jobs.py
git commit -m "feat: add clip trim calculation helpers"
```

---

### Task 3: Populate trim metadata when building agent clips

**Files:**
- Modify: `backend/services/search_service.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
class SearchClipAssemblyTests(unittest.TestCase):
    def test_search_and_download_agent_clips_populates_trim_metadata(self):
        from backend.models.agent import PlanScene
        from backend.services.search_service import search_and_download_agent_clips

        async def run_test():
            scenes = [
                PlanScene(
                    id=1,
                    description="开场",
                    keywords=["city"],
                    duration=6.0,
                    searchQuery="city motion",
                )
            ]

            with patch("backend.services.search_service.search_youtube") as mock_search, patch(
                "backend.services.search_service.download_video"
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

            self.assertEqual(len(clips), 1)
            self.assertEqual(clips[0].sourceDuration, 20.0)
            self.assertAlmostEqual(clips[0].trimStart, 4.9)
            self.assertEqual(clips[0].trimDuration, 6.0)

        asyncio.run(run_test())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.SearchClipAssemblyTests.test_search_and_download_agent_clips_populates_trim_metadata -v`  
Expected: FAIL because clip metadata is still missing or defaults to zeros

- [ ] **Step 3: Write minimal implementation**

更新 `search_and_download_agent_clips(...)` 中构造 `AgentClipInfo(...)` 的代码：

```python
source_duration = normalize_duration(selected_video.get("duration", 0))
trim_start, trim_duration = calculate_trim_window(source_duration, scene.duration)

clips.append(
    AgentClipInfo(
        sceneId=scene.id,
        sourceUrl=selected_video.get("url", ""),
        localPath=local_path,
        publicUrl=f"/downloads/{output_filename}",
        startTime=0,
        duration=scene.duration,
        sourceDuration=source_duration,
        trimStart=trim_start,
        trimDuration=trim_duration,
    )
)
```

如果 `selected_video["duration"]` 不可靠，就保底用 `scene.duration` 作为 `trimDuration`，但 `sourceDuration` 仍然保留真实或归一化后的值。

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.SearchClipAssemblyTests.test_search_and_download_agent_clips_populates_trim_metadata -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/search_service.py tests/test_agent_jobs.py
git commit -m "feat: populate trim metadata for agent clips"
```

---

### Task 4: Persist trim metadata into artifact metadata and read it back

**Files:**
- Modify: `backend/tasks/agent_tasks.py`
- Modify: `backend/services/agent_read_service.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
class ArtifactTrimMetadataTests(unittest.TestCase):
    def test_run_agent_job_persists_trim_metadata_in_artifacts(self):
        from backend.db.repositories import AgentArtifactRepository
        from backend.tasks.agent_tasks import run_agent_job

        session_id, job_id = self._create_queued_job()

        async def fake_search_runner(_session_id, _scenes):
            return [
                {
                    "sceneId": 1,
                    "sourceUrl": "https://example.com/1",
                    "localPath": "backend/downloads/1.mp4",
                    "publicUrl": "/downloads/1.mp4",
                    "duration": 6.0,
                    "sourceDuration": 20.0,
                    "trimStart": 4.9,
                    "trimDuration": 6.0,
                }
            ]

        async def fake_render_runner(_session_id, _clips, _filename):
            return "/output/final.mp4"

        with patch("backend.tasks.agent_tasks.SessionLocal", self.session_factory), patch(
            "backend.tasks.agent_tasks.search_and_download_agent_clips",
            fake_search_runner,
        ), patch(
            "backend.tasks.agent_tasks.render_video",
            fake_render_runner,
        ):
            run_agent_job(job_id)

        with self.session_factory() as db:
            artifact_repo = AgentArtifactRepository(db)
            artifacts = artifact_repo.list_for_session(session_id)

        clip_artifact = next(row for row in artifacts if row.artifact_type == "clip")
        self.assertEqual(clip_artifact.metadata_json["sourceDuration"], 20.0)
        self.assertEqual(clip_artifact.metadata_json["trimStart"], 4.9)
        self.assertEqual(clip_artifact.metadata_json["trimDuration"], 6.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.ArtifactTrimMetadataTests.test_run_agent_job_persists_trim_metadata_in_artifacts -v`  
Expected: FAIL because clip artifact metadata does not include the trim fields

- [ ] **Step 3: Write minimal implementation**

在 `backend/tasks/agent_tasks.py` 的 `progress_service.create_artifact(...)` 调用中，为 `artifact_type="clip"` 增加：

```python
metadata={
    "sourceDuration": clip.sourceDuration,
    "trimStart": clip.trimStart,
    "trimDuration": clip.trimDuration,
}
```

再在 `backend/services/agent_read_service.py` 中读取 clip artifact 时补上映射：

```python
metadata = row.metadata_json or {}

ClipInfo(
    sceneId=...,
    sourceUrl=row.source_url or "",
    localPath=row.local_path or "",
    publicUrl=row.public_url or "",
    duration=row.duration or 0.0,
    sourceDuration=float(metadata.get("sourceDuration", 0.0) or 0.0),
    trimStart=float(metadata.get("trimStart", 0.0) or 0.0),
    trimDuration=float(metadata.get("trimDuration", row.duration or 0.0) or 0.0),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.ArtifactTrimMetadataTests.test_run_agent_job_persists_trim_metadata_in_artifacts -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tasks/agent_tasks.py backend/services/agent_read_service.py tests/test_agent_jobs.py
git commit -m "feat: persist trim metadata in clip artifacts"
```

---

### Task 5: Add render helper that trims and normalizes one clip

**Files:**
- Modify: `backend/services/render_service.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
class RenderPreparationTests(unittest.TestCase):
    def test_prepare_render_clip_uses_trim_window_and_vertical_output(self):
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
        )

        commands = build_render_commands([clip], "backend/output/final.mp4")

        self.assertEqual(len(commands["segments"]), 1)
        self.assertIn("trimStart", commands["segments"][0])
        self.assertEqual(commands["segments"][0]["trimStart"], 4.9)
        self.assertEqual(commands["segments"][0]["trimDuration"], 6.0)
        self.assertEqual(commands["output"]["width"], 720)
        self.assertEqual(commands["output"]["height"], 1280)
        self.assertEqual(commands["output"]["fps"], 30)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.RenderPreparationTests.test_prepare_render_clip_uses_trim_window_and_vertical_output -v`  
Expected: FAIL with missing `build_render_commands`

- [ ] **Step 3: Write minimal implementation**

在 `backend/services/render_service.py` 增加一个纯配置函数，避免直接在测试里 mock FFmpeg 图对象：

```python
def build_render_commands(clips: List[RenderClip], output_path: str) -> dict:
    # 生成渲染阶段需要的结构化配置，方便测试
    return {
        "segments": [
            {
                "input": _clip_input_path(clip),
                "trimStart": getattr(clip, "trimStart", 0.0),
                "trimDuration": getattr(clip, "trimDuration", getattr(clip, "duration", 0.0)),
            }
            for clip in clips
        ],
        "output": {
            "path": output_path,
            "width": 720,
            "height": 1280,
            "fps": 30,
            "vcodec": "libx264",
            "acodec": "aac",
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.RenderPreparationTests.test_prepare_render_clip_uses_trim_window_and_vertical_output -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/render_service.py tests/test_agent_jobs.py
git commit -m "test: add render command contract for vertical short clips"
```

---

### Task 6: Replace whole-video concat with trimmed vertical segment rendering

**Files:**
- Modify: `backend/services/render_service.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
class RenderBehaviorTests(unittest.TestCase):
    def test_render_video_uses_trim_duration_instead_of_full_source(self):
        from backend.models.agent import ClipInfo
        from backend.services.render_service import build_render_commands

        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/1",
            localPath="backend/downloads/1.mp4",
            publicUrl="/downloads/1.mp4",
            duration=6.0,
            sourceDuration=120.0,
            trimStart=10.0,
            trimDuration=6.0,
        )

        commands = build_render_commands([clip], "backend/output/final.mp4")

        self.assertNotEqual(commands["segments"][0]["trimDuration"], clip.sourceDuration)
        self.assertEqual(commands["segments"][0]["trimDuration"], 6.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.RenderBehaviorTests.test_render_video_uses_trim_duration_instead_of_full_source -v`  
Expected: FAIL before `build_render_commands` and `render_video` both honor trim fields consistently

- [ ] **Step 3: Write minimal implementation**

把 `backend/services/render_service.py` 重构成：

1. 保留 `render_video(...)` 作为异步入口
2. 新增 `_normalize_trim_duration(clip)` 保底处理
3. 新增 `_build_vertical_segment(clip)`，核心逻辑为：

```python
video = ffmpeg.input(clip.localPath, ss=clip.trimStart, t=clip.trimDuration)
audio = video.audio
video_stream = (
    video.video
    .filter("scale", 720, 1280, force_original_aspect_ratio="increase")
    .filter("crop", 720, 1280)
    .filter("fps", fps=30)
)
audio_stream = audio.filter("aresample", 44100).filter("aformat", sample_fmts="fltp", channel_layouts="stereo")
```

4. 把每段标准化片段先输出到临时文件，例如 `backend/output/tmp_<session>_<scene>.mp4`
5. 再通过 concat demuxer 或标准化后的 concat filter 合并这些临时片段
6. 输出最终 `backend/output/<session>.mp4`

如果实现时发现 `ffmpeg.concat` 对标准化后的文件更稳，就优先使用中间文件方案，不要回到直接拼接原片段。

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.RenderPreparationTests tests.test_agent_jobs.RenderBehaviorTests -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/render_service.py tests/test_agent_jobs.py
git commit -m "feat: render trimmed vertical short clips"
```

---

### Task 7: Keep worker success flow green with trim-aware artifacts

**Files:**
- Modify: `tests/test_agent_jobs.py`
- Modify: `backend/services/agent_read_service.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Extend the existing worker success test with trim assertions**

在 `AgentExecutionWorkerTests.test_run_agent_job_persists_success_state_events_and_artifacts` 中，把 `fake_search_runner` 返回值改为包含：

```python
{
    "sceneId": scene.id,
    "sourceUrl": f"https://example.com/{scene.id}",
    "localPath": f"backend/downloads/{scene.id}.mp4",
    "publicUrl": f"/downloads/{scene.id}.mp4",
    "duration": scene.duration,
    "sourceDuration": scene.duration + 10,
    "trimStart": 1.5,
    "trimDuration": scene.duration,
}
```

并新增断言：

```python
self.assertEqual(session.clips[0].trimStart, 1.5)
self.assertEqual(session.clips[0].trimDuration, session.clips[0].duration)
self.assertGreater(session.clips[0].sourceDuration, session.clips[0].duration)
```

- [ ] **Step 2: Run the targeted worker success test and watch it fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.AgentExecutionWorkerTests.test_run_agent_job_persists_success_state_events_and_artifacts -v`  
Expected: FAIL because trim metadata is not yet fully round-tripped into `session.clips`

- [ ] **Step 3: Make the minimal implementation pass**

如果前一任务已经补齐 `agent_read_service.py`，这里只需要修正任何遗漏的映射，例如：

- `row.metadata_json` 为空时的默认值
- 最终视频 artifact 不应带场景 trim 字段
- `scene_id=0` 的视频 artifact 不能污染 clip 列表断言时的顺序判断

必要时在 `build_session_response(...)` 中把 clip artifact 和 video artifact 分开处理，例如：

```python
clip_rows = [row for row in artifact_rows if row.artifact_type == "clip"]
```

再把 `video` artifact 只用于 `videoUrl` 或附加产物，不要当作 `clips` 列表的一段场景素材。

- [ ] **Step 4: Run the targeted worker success test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.AgentExecutionWorkerTests.test_run_agent_job_persists_success_state_events_and_artifacts -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/agent_read_service.py tests/test_agent_jobs.py
git commit -m "fix: keep worker session clips trim-aware"
```

---

### Task 8: Run end-to-end verification for the shortform trim flow

**Files:**
- Modify: `tests/test_agent_jobs.py`
- Modify: `backend/services/search_service.py`
- Modify: `backend/services/render_service.py`
- Modify: `backend/tasks/agent_tasks.py`
- Modify: `backend/services/agent_read_service.py`
- Modify: `backend/models/agent.py`

- [ ] **Step 1: Run the focused backend regression suite**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs -v`  
Expected: PASS

- [ ] **Step 2: Run a real worker-backed manual flow**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import json, urllib.request; data=json.dumps({'message':'做一个竖屏智能短片'}).encode(); req=urllib.request.Request('http://127.0.0.1:8010/api/agent/sessions', data=data, headers={'Content-Type':'application/json'}); print(urllib.request.urlopen(req).read().decode())"
```

记录返回的 `session_id`，再执行：

```powershell
.\.venv\Scripts\python.exe -c "import urllib.request; session_id='<替换成上一步的 session_id>'; req=urllib.request.Request(f'http://127.0.0.1:8010/api/agent/sessions/{session_id}/confirm', data=b'', method='POST'); print(urllib.request.urlopen(req).read().decode())"
```

Expected: session 状态从 `queued` 进入 `searching / rendering / done`

- [ ] **Step 3: Verify the output video is vertical and near target duration**

Run:

```powershell
ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 backend/output/<session_id>.mp4
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 backend/output/<session_id>.mp4
```

Expected:

- 分辨率接近 `720,1280`
- 时长接近 `plan.targetDuration`，不再是多段长视频整段拼接后的超长结果

- [ ] **Step 4: Verify git status only contains intended source changes**

Run: `git status --short`  
Expected: 只包含本阶段源码、测试和文档改动；不要把 `.run-*.log`、`backend/output/*.mp4` 等运行产物纳入提交

- [ ] **Step 5: Commit**

```bash
git add backend/models/agent.py backend/services/search_service.py backend/services/render_service.py backend/tasks/agent_tasks.py backend/services/agent_read_service.py tests/test_agent_jobs.py docs/superpowers/specs/2026-05-03-vertical-shortform-trim-design.md docs/superpowers/plans/2026-05-03-vertical-shortform-trim-implementation.md
git commit -m "feat: generate vertical shortform clips with trim metadata"
```

---

## Self-Review

### Spec coverage

这个计划覆盖了 spec 的所有核心要求：

- `ClipInfo` 增强：Task 1
- 搜索阶段生成 `sourceDuration / trimStart / trimDuration`：Tasks 2-3
- artifact 持久化与读回：Task 4
- 9:16 竖屏渲染与按场景裁剪：Tasks 5-6
- 保持 worker 成功链路可用：Task 7
- 真实输出验证：Task 8

没有遗漏“近 30 秒竖屏成片”这一验收核心。

### Placeholder scan

计划中没有 `TBD`、`TODO`、"适当处理" 这类空洞描述。每个任务都指定了准确文件、测试命令和期望行为。

### Type consistency

全程统一使用以下字段名：

- `sourceDuration`
- `trimStart`
- `trimDuration`

并且明确这些字段既存在于 `ClipInfo`，也会通过 artifact `metadata_json` 往返持久化，不会出现前后命名不一致。

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-03-vertical-shortform-trim-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

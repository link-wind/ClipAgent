# ClipForge AI 自动剪辑 - 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 实现用户输入文案 → AI分析 → YouTube搜索素材 → 自动剪辑生成视频的全流程

**架构：** 前端Next.js + 后端FastAPI(Python)，通过REST + WebSocket通信

**技术栈：** Next.js 14, FastAPI, OpenAI GPT (中转站), yt-dlp, FFmpeg

---

## 文件结构

### 新建文件

```
backend/
├── main.py                      # FastAPI入口，挂载router
├── requirements.txt             # Python依赖
├── api/
│   ├── __init__.py
│   └── ai.py                   # AI相关路由（analyze/search/render/status）
├── services/
│   ├── __init__.py
│   ├── gpt_service.py          # GPT调用服务
│   ├── search_service.py       # yt-dlp搜索下载服务
│   └── render_service.py      # FFmpeg合成服务
├── models/
│   ├── __init__.py
│   └── task.py                 # 任务数据模型
├── utils/
│   ├── __init__.py
│   └── websocket.py           # WebSocket帮助类
├── downloads/                  # 临时下载目录（gitkeep）
└── output/                     # 输出视频目录（gitkeep）

src/
├── stores/
│   └── useAIServiceStore.ts    # 新增：AI任务状态管理
└── components/
    └── ai/
        ├── ScriptInput.tsx      # 新增：文案输入
        ├── TaskProgress.tsx     # 新增：任务进度
        └── SceneConfirm.tsx    # 新增：场景确认（可选）
```

### 修改文件

```
src/components/layout/AppShell.tsx      # 新增AI mode Tab
src/components/layout/Header.tsx          # 新增AI入口
src/components/common/RenderModal.tsx     # 改造为AI任务进度
src/stores/useTimelineStore.ts            # 添加mode切换
```

---

## Phase 1: 基础架构

### Task 1: 创建后端项目骨架

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/main.py`
- Create: `backend/api/__init__.py`
- Create: `backend/api/ai.py`
- Create: `backend/services/__init__.py`
- Create: `backend/services/gpt_service.py`
- Create: `backend/models/__init__.py`
- Create: `backend/models/task.py`
- Create: `backend/utils/__init__.py`
- Create: `backend/utils/websocket.py`
- Create: `backend/downloads/.gitkeep`
- Create: `backend/output/.gitkeep`

**Steps:**

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p backend/api backend/services backend/models backend/utils backend/downloads backend/output
touch backend/downloads/.gitkeep backend/output/.gitkeep
```

- [ ] **Step 2: 创建 requirements.txt**

```
fastapi==0.110.0
uvicorn[standard]==0.27.1
openai==1.12.0
yt-dlp==2024.3.10
ffmpeg-python==0.2.0
websockets==12.0
python-multipart==0.0.9
pydantic==2.6.1
aiofiles==23.2.1
```

- [ ] **Step 3: 创建 models/task.py**

```python
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

class TaskStatus(str, Enum):
    IDLE = "idle"
    ANALYZING = "analyzing"
    SCENES_READY = "scenes_ready"
    SEARCHING = "searching"
    RENDERING = "rendering"
    DONE = "done"
    FAILED = "failed"

class Scene(BaseModel):
    id: int
    description: str
    keywords: List[str]

class AnalyzeRequest(BaseModel):
    script: str

class AnalyzeResponse(BaseModel):
    scenes: List[Scene]

class SearchRequest(BaseModel):
    scenes: List[Scene]

class SearchResponse(BaseModel):
    taskId: str
    status: str

class ClipInfo(BaseModel):
    sceneId: int
    videoUrl: str
    startTime: float
    duration: float

class RenderRequest(BaseModel):
    taskId: str
    clips: List[ClipInfo]

class RenderResponse(BaseModel):
    taskId: str
    status: str

class TaskStatusResponse(BaseModel):
    status: str
    progress: int
    currentStep: str
    videoUrl: Optional[str] = None
```

- [ ] **Step 4: 创建 utils/websocket.py**

```python
from fastapi import WebSocket
from typing import Dict
import json

class WSManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[task_id] = websocket

    def disconnect(self, task_id: str):
        if task_id in self.connections:
            del self.connections[task_id]

    async def send_progress(self, task_id: str, progress: int, step: str, data: dict = None):
        if task_id in self.connections:
            message = {
                "type": "progress",
                "progress": progress,
                "step": step
            }
            if data:
                message.update(data)
            await self.connections[task_id].send_json(message)

ws_manager = WSManager()
```

- [ ] **Step 5: 创建 services/gpt_service.py**

```python
import os
from openai import OpenAI
from typing import List
from models.task import Scene

# 中转站配置
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
API_KEY = os.getenv("OPENAI_API_KEY", "")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

SYSTEM_PROMPT = """你是一个视频脚本分析专家。用户输入一段文案，你需要将其分解成多个场景。
每个场景应该能够通过关键词搜索到匹配的视频素材。
请以JSON格式返回场景列表，每个场景包含：
- description: 场景描述
- keywords: 搜索关键词数组（3-5个词）
"""

def analyze_script(script: str) -> List[Scene]:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"分析以下文案，分解成场景：\n{script}"}
        ],
        response_format={"type": "json_object"}
    )
    
    import json
    result = json.loads(response.choices[0].message.content)
    scenes = []
    for i, item in enumerate(result.get("scenes", [])):
        scenes.append(Scene(
            id=i+1,
            description=item.get("description", ""),
            keywords=item.get("keywords", [])
        ))
    return scenes
```

- [ ] **Step 6: 创建 api/ai.py**

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from models.task import *
from services.gpt_service import analyze_script
from utils.websocket import ws_manager
import uuid

router = APIRouter(prefix="/api/ai", tags=["ai"])

# 内存存储任务状态（生产环境用Redis）
tasks = {}

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    scenes = analyze_script(req.script)
    return AnalyzeResponse(scenes=scenes)

@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "searching",
        "scenes": req.scenes,
        "progress": 0
    }
    return SearchResponse(taskId=task_id, status="searching")

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_status(task_id: str):
    if task_id not in tasks:
        return TaskStatusResponse(status="failed", progress=0, currentStep="任务不存在")
    task = tasks[task_id]
    return TaskStatusResponse(
        status=task["status"],
        progress=task["progress"],
        currentStep=task.get("step", "")
    )

@router.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await ws_manager.connect(task_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(task_id)
```

- [ ] **Step 7: 创建 main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.ai import router as ai_router

app = FastAPI(title="ClipForge AI Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_router)

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "Phase 1: 创建后端项目骨架"
```

---

### Task 2: 前端新增 AI mode 切换

**Files:**
- Modify: `src/stores/useTimelineStore.ts`
- Create: `src/stores/useAIServiceStore.ts`
- Create: `src/components/ai/ScriptInput.tsx`
- Create: `src/components/ai/TaskProgress.tsx`

**Steps:**

- [ ] **Step 1: 创建 useAIServiceStore.ts**

```typescript
import { create } from 'zustand'

interface Scene {
  id: number
  description: string
  keywords: string[]
}

interface AIServiceStore {
  mode: 'manual' | 'ai'
  taskId: string | null
  status: 'idle' | 'analyzing' | 'scenes_ready' | 'searching' | 'rendering' | 'done' | 'failed'
  progress: number
  currentStep: string
  script: string
  scenes: Scene[]
  resultVideoUrl: string | null
  
  setMode: (mode: 'manual' | 'ai') => void
  setScript: (script: string) => void
  setStatus: (status: AIServiceStore['status']) => void
  setProgress: (progress: number, step: string) => void
  setScenes: (scenes: Scene[]) => void
  setResultVideoUrl: (url: string | null) => void
  reset: () => void
}

const initialState = {
  mode: 'manual' as const,
  taskId: null,
  status: 'idle' as const,
  progress: 0,
  currentStep: '',
  script: '',
  scenes: [],
  resultVideoUrl: null,
}

export const useAIServiceStore = create<AIServiceStore>((set) => ({
  ...initialState,
  
  setMode: (mode) => set({ mode }),
  setScript: (script) => set({ script }),
  setStatus: (status) => set({ status }),
  setProgress: (progress, currentStep) => set({ progress, currentStep }),
  setScenes: (scenes) => set({ scenes, status: 'scenes_ready' }),
  setResultVideoUrl: (url) => set({ resultVideoUrl: url, status: url ? 'done' : 'idle' }),
  reset: () => set(initialState),
}))
```

- [ ] **Step 2: 修改 useTimelineStore.ts 添加 mode**

在 store 中添加 `mode` 字段，AppShell 根据 mode 渲染不同界面

- [ ] **Step 3: 创建 ScriptInput.tsx**

```typescript
'use client'

import { useAIServiceStore } from '@/stores/useAIServiceStore'
import styles from './ScriptInput.module.css'

export function ScriptInput() {
  const { script, setScript, setStatus } = useAIServiceStore()
  
  const handleAnalyze = async () => {
    if (!script.trim()) return
    setStatus('analyzing')
    
    try {
      const res = await fetch('/api/ai/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script })
      })
      const data = await res.json()
      useAIServiceStore.getState().setScenes(data.scenes)
    } catch (err) {
      setStatus('failed')
    }
  }
  
  return (
    <div className={styles.container}>
      <textarea
        className={styles.textarea}
        value={script}
        onChange={(e) => setScript(e.target.value)}
        placeholder="输入文案脚本..."
      />
      <button onClick={handleAnalyze}>开始分析</button>
    </div>
  )
}
```

- [ ] **Step 4: 创建 TaskProgress.tsx**

```typescript
'use client'

import { useAIServiceStore } from '@/stores/useAIServiceStore'
import styles from './TaskProgress.module.css'

export function TaskProgress() {
  const { status, progress, currentStep, resultVideoUrl } = useAIServiceStore()
  
  if (status === 'idle') return null
  
  return (
    <div className={styles.container}>
      <div className={styles.progressBar}>
        <div className={styles.progressFill} style={{ width: `${progress}%` }} />
      </div>
      <p className={styles.step}>{currentStep}</p>
      {resultVideoUrl && (
        <a href={resultVideoUrl} download>下载视频</a>
      )}
    </div>
  )
}
```

- [ ] **Step 5: 修改 AppShell 支持 mode 切换**

根据 `useAIServiceStore.mode` 切换渲染 AI 界面或手动剪辑界面

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "Phase 1: 前端AI mode切换基础"
```

---

### Task 3: 前后端联调 GPT 分析

**Steps:**

- [ ] **Step 1: 设置环境变量**

```bash
# 前后端联调需要设置
export OPENAI_BASE_URL="你的中转站URL"
export OPENAI_API_KEY="你的API_KEY"
```

- [ ] **Step 2: 启动后端测试**

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

- [ ] **Step 3: 测试 analyze 接口**

```bash
curl -X POST http://localhost:8000/api/ai/analyze \
  -H "Content-Type: application/json" \
  -d '{"script": "今天阳光明媚，我们一起去公园散步，看到很多人在放风筝，孩子们在草地上奔跑嬉戏。"}'
```

- [ ] **Step 4: 联调前端**

在 Next.js 中配置代理到 `localhost:8000`

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "Phase 1: 前后端GPT分析联调完成"
```

---

## Phase 2: 素材搜索

### Task 4: 实现 yt-dlp 搜索下载服务

**Files:**
- Modify: `backend/services/search_service.py`
- Modify: `backend/api/ai.py`

**Steps:**

- [ ] **Step 1: 创建 services/search_service.py**

```python
import yt_dlp
import os
import asyncio
from typing import List
from models.task import Scene
from utils.websocket import ws_manager

DOWNLOADS_DIR = "backend/downloads"
OUTPUT_DIR = "backend/output"

def search_youtube(keywords: List[str], duration_range=(5, 30)):
    """搜索YouTube视频，返回视频信息"""
    query = " ".join(keywords)
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'default_search': f'ytsearch5:{query}',
        'format': 'best[height<=720]',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        results = ydl.extract_info(query, download=False)
        if not results or 'entries' not in results:
            return []
        return [
            {
                "id": e['id'],
                "title": e.get('title', ''),
                "url": e.get('url', e.get('webpage_url', '')),
                "duration": e.get('duration', 0),
                "thumbnail": e.get('thumbnail', '')
            }
            for e in results['entries'][:5]
            if e.get('duration', 0) >= duration_range[0] and e.get('duration', 0) <= duration_range[1]
        ]

async def download_video(task_id: str, video_info: dict, scene_id: int, output_filename: str):
    """下载单个视频"""
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    output_path = os.path.join(DOWNLOADS_DIR, output_filename)
    
    ydl_opts = {
        'format': 'best[height<=720]',
        'outtmpl': output_path,
        'quiet': True,
    }
    
    await ws_manager.send_progress(task_id, 0, f"正在下载素材 {scene_id}...")
    
    loop = asyncio.get_event_loop()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        await loop.run_in_executor(None, ydl.download, [video_info['url']])
    
    await ws_manager.send_progress(task_id, 100, f"素材 {scene_id} 下载完成")
    return output_path
```

- [ ] **Step 2: 修改 api/ai.py 添加搜索路由**

```python
from services.search_service import search_youtube, download_video
import asyncio

@router.post("/search")
async def search(req: SearchRequest):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "searching",
        "scenes": req.scenes,
        "progress": 0,
        "clips": []
    }
    
    # 异步执行搜索下载
    asyncio.create_task(run_search(task_id, req.scenes))
    
    return SearchResponse(taskId=task_id, status="searching")

async def run_search(task_id: str, scenes: List[Scene]):
    all_results = []
    for scene in scenes:
        results = search_youtube(scene.keywords)
        all_results.append({"scene": scene, "videos": results})
        
        # 保存搜索结果到任务
        if task_id in tasks:
            tasks[task_id]["search_results"] = all_results
    
    # 下载第一个匹配的视频
    clips = []
    for scene in scenes:
        scene_results = next((r for r in all_results if r["scene"].id == scene.id), {})
        videos = scene_results.get("videos", [])
        if videos:
            video = videos[0]
            filename = f"{task_id}_{scene.id}.mp4"
            try:
                path = await download_video(task_id, video, scene.id, filename)
                clips.append({
                    "sceneId": scene.id,
                    "videoUrl": path,
                    "startTime": 0,
                    "duration": video.get("duration", 10)
                })
            except Exception as e:
                print(f"Download failed for scene {scene.id}: {e}")
        
        # 更新进度
        progress = int((scenes.index(scene) + 1) / len(scenes) * 50)
        if task_id in tasks:
            tasks[task_id]["progress"] = progress
    
    if task_id in tasks:
        tasks[task_id]["status"] = "scenes_ready"
        tasks[task_id]["clips"] = clips
```

- [ ] **Step 3: 测试搜索功能**

```bash
curl -X POST http://localhost:8000/api/ai/search \
  -H "Content-Type: application/json" \
  -d '{"scenes": [{"id": 1, "description": "公园场景", "keywords": ["park", "sunny", "outdoor"]}]}'
```

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "Phase 2: 实现yt-dlp搜索下载服务"
```

---

## Phase 3: 视频合成

### Task 5: 实现 FFmpeg 拼接服务

**Files:**
- Create: `backend/services/render_service.py`
- Modify: `backend/api/ai.py`

**Steps:**

- [ ] **Step 1: 创建 services/render_service.py**

```python
import ffmpeg
import os
import uuid
from typing import List
from models.task import ClipInfo

OUTPUT_DIR = "backend/output"

def concat_clips(clips: List[ClipInfo], output_filename: str) -> str:
    """拼接多个视频片段"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    # 创建临时文件列表
    list_file = output_path + ".txt"
    with open(list_file, 'w') as f:
        for clip in clips:
            # 使用复杂滤镜进行裁剪和拼接
            f.write(f"file '{clip.videoUrl}'\n")
    
    try:
        # 使用concat协议拼接
        stream = ffmpeg.input(list_file, format='concat', safe=0)
        stream = ffmpeg.output(stream, output_path, c='copy')
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
    finally:
        os.remove(list_file)
    
    return output_path

def concat_with_trim(clips: List[ClipInfo], output_filename: str, task_id: str) -> str:
    """带裁剪的拼接"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    # 构建复杂滤镜命令
    inputs = []
    for i, clip in enumerate(clips):
        inputs.append(ffmpeg.input(clip.videoUrl))
    
    # 简单拼接（不裁剪）
    if len(inputs) == 1:
        inputs[0].output(output_path).run(overwrite_output=True, quiet=True)
    else:
        # 多文件拼接
        joined = ffmpeg.concat(*inputs, v=1, a=1)
        joined.output(output_path).run(overwrite_output=True, quiet=True)
    
    return output_path
```

- [ ] **Step 2: 修改 api/ai.py 添加 render 路由**

```python
from services.render_service import concat_with_trim

@router.post("/render", response_model=RenderResponse)
async def render(req: RenderRequest):
    task_id = req.taskId
    if task_id not in tasks:
        return RenderResponse(taskId=task_id, status="failed")
    
    tasks[task_id]["status"] = "rendering"
    asyncio.create_task(run_render(task_id, req.clips))
    
    return RenderResponse(taskId=task_id, status="rendering")

async def run_render(task_id: str, clips: List[ClipInfo]):
    try:
        await ws_manager.send_progress(task_id, 50, "正在合成视频...")
        
        output_filename = f"{task_id}.mp4"
        output_path = concat_with_trim(clips, output_filename, task_id)
        
        # 返回相对URL
        video_url = f"/output/{output_filename}"
        
        await ws_manager.send_progress(task_id, 100, "渲染完成", {"videoUrl": video_url})
        
        if task_id in tasks:
            tasks[task_id]["status"] = "done"
            tasks[task_id]["videoUrl"] = video_url
            
    except Exception as e:
        if task_id in tasks:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = str(e)
        await ws_manager.send_progress(task_id, 0, f"渲染失败: {str(e)}")
```

- [ ] **Step 3: 添加静态文件服务**

修改 `main.py` 添加 `StaticFiles` 挂载 `output` 目录

- [ ] **Step 4: 测试渲染功能**

```bash
# 先下载测试视频，然后测试拼接
curl -X POST http://localhost:8000/api/ai/render \
  -H "Content-Type: application/json" \
  -d '{"taskId": "test-uuid", "clips": [{"sceneId": 1, "videoUrl": "/downloads/xxx.mp4", "startTime": 0, "duration": 10}]}'
```

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "Phase 3: 实现FFmpeg视频合成服务"
```

---

## Phase 4: 体验优化

### Task 6: WebSocket 进度推送完善

**Steps:**

- [ ] **Step 1: 前端连接 WebSocket**

在 `TaskProgress.tsx` 中使用 `new WebSocket()` 连接 `/ws/ai/{taskId}`

- [ ] **Step 2: 显示实时进度**

更新 UI 显示下载进度、渲染进度

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "Phase 4: WebSocket进度推送"
```

---

### Task 7: 完整流程联调

**Steps:**

- [ ] **Step 1: 端到端测试**

输入文案 → AI分析 → 素材搜索 → 视频合成 → 预览下载

- [ ] **Step 2: 错误处理**

各阶段错误处理和重试

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "Phase 4: 完整流程联调完成"
```

---

## 验证检查清单

完成以上任务后，确认以下功能正常：

- [ ] 后端启动：`uvicorn main:app --reload --port 8000`
- [ ] GPT分析：`POST /api/ai/analyze` 返回场景列表
- [ ] 素材搜索：`POST /api/ai/search` 开始搜索下载
- [ ] WebSocket：`/ws/ai/{taskId}` 推送进度
- [ ] 视频渲染：`POST /api/ai/render` 生成最终视频
- [ ] 视频下载：`GET /output/{filename}` 可下载
- [ ] 前端AI mode：输入文案 → 查看进度 → 预览结果

# ClipForge AI 自动剪辑功能设计

**日期**：2026-05-02
**版本**：v1.0
**状态**：草稿

---

## 1. 概述

### 1.1 目标
将 ClipForge 从人工剪辑工具改造为 **AI 自动剪辑工具**：用户输入文案/脚本，AI 自动从 YouTube 搜索匹配素材并生成剪辑视频。

### 1.2 核心场景
```
用户输入文案/脚本 → AI分析内容 → YouTube搜索素材 → AI自动剪辑 → 生成视频
```

### 1.3 技术选型
| 组件 | 技术 |
|------|------|
| 前端 | Next.js 14 (现有) |
| LLM | OpenAI GPT API |
| 视频搜索 | yt-dlp (YouTube) |
| 视频合成 | FFmpeg (现有) + 后端 |
| 后端部署 | 传统服务器 (Docker) |

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (Next.js)                         │
│  ┌─────────┐  ┌─────────────┐  ┌──────────────────────────┐│
│  │ 文案输入 │  │  任务进度   │  │     视频预览 + 下载      ││
│  └────┬────┘  └──────┬──────┘  └───────────┬──────────────┘│
│       │              │                      │              │
│       └──────────────┼──────────────────────┘              │
│                      │                                     │
│              useAIServiceStore                             │
└──────────────────────┼─────────────────────────────────────┘
                       │ REST + WebSocket
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   后端 (FastAPI/Python)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  脚本分析    │  │  素材搜索    │  │   视频合成       │  │
│  │  (GPT API)   │→ │  (yt-dlp)   │→ │   (FFmpeg)       │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 前端职责
- 提供文案输入界面
- 显示AI任务进度（WebSocket）
- 预览和下载生成的视频
- 管理AI任务状态（新增 store）

### 2.3 后端职责
- 接收用户脚本，调用GPT分析场景
- 使用yt-dlp从YouTube搜索下载素材
- 使用FFmpeg拼接合成视频
- 通过WebSocket推送进度
- 返回最终视频URL

---

## 3. 核心流程

### 3.1 AI剪辑流程

```
1. 用户输入文案脚本
       ↓
2. 前端 POST /api/ai/analyze
       ↓
3. 后端 GPT 分析脚本，提取关键场景/概念
       ↓
4. 返回场景列表给前端确认（或自动继续）
       ↓
5. 前端 POST /api/ai/search（场景列表）
       ↓
6. 后端 yt-dlp 并行搜索下载YouTube片段
       ↓
7. WebSocket 推送下载进度
       ↓
8. 后端 GPT 确定片段顺序和时长
       ↓
9. 后端 FFmpeg 拼接生成最终视频
       ↓
10. WebSocket 推送渲染进度
       ↓
11. 前端获取视频URL，预览 + 下载
```

### 3.2 状态机

```
IDLE → ANALYZING → SCENES_READY → SEARCHING → RENDERING → DONE
                    ↓                           ↓
                SEARCHING                   FAILED
                    ↓                           ↓
                 FAILED                     IDLE (重试)
```

---

## 4. API 设计

### 4.1 REST API

#### POST /api/ai/analyze
**请求**：
```json
{
  "script": "今天天气真好，我们一起去公园玩吧"
}
```
**响应**：
```json
{
  "scenes": [
    {"id": 1, "description": "户外公园场景", "keywords": ["公园", "户外", "阳光"]},
    {"id": 2, "description": "轻松愉快的氛围", "keywords": ["愉快", "放松"]}
  ]
}
```

#### POST /api/ai/search
**请求**：
```json
{
  "scenes": [
    {"id": 1, "keywords": ["公园", "户外", "阳光"]},
    {"id": 2, "keywords": ["愉快", "放松"]}
  ]
}
```
**响应**：
```json
{
  "taskId": "uuid-xxx",
  "status": "searching"
}
```

#### POST /api/ai/render
**请求**：
```json
{
  "taskId": "uuid-xxx",
  "clips": [
    {"sceneId": 1, "videoUrl": "/downloads/xxx.mp4", "startTime": 10.5, "duration": 5.2},
    {"sceneId": 2, "videoUrl": "/downloads/yyy.mp4", "startTime": 30.0, "duration": 8.0}
  ]
}
```
**响应**：
```json
{
  "taskId": "uuid-xxx",
  "status": "rendering"
}
```

#### GET /api/ai/status/{taskId}
**响应**：
```json
{
  "status": "rendering",
  "progress": 65,
  "currentStep": "正在合成视频..."
}
```

#### GET /api/ai/result/{taskId}
**响应**：
```json
{
  "status": "done",
  "videoUrl": "/output/uuid-xxx.mp4",
  "duration": 45
}
```

### 4.2 WebSocket /ws/ai/{taskId}
**消息格式**：
```json
{
  "type": "progress",
  "progress": 50,
  "step": "正在下载素材 2/5..."
}
```

---

## 5. 前端改动

### 5.1 组件改动

| 组件 | 改动 |
|------|------|
| `AppShell` | 新增"AI剪辑"Tab，支持切换手动/AI模式 |
| `Header` | 新增AI剪辑入口按钮 |
| `RenderModal` | 改造为AI任务进度显示 |
| `PreviewBar` | 显示AI生成的视频预览 |

### 5.2 新增 Store

```ts
interface AIServiceStore {
  mode: 'manual' | 'ai'
  taskId: string | null
  status: 'idle' | 'analyzing' | 'scenes_ready' | 'searching' | 'rendering' | 'done' | 'failed'
  progress: number
  currentStep: string
  script: string
  scenes: Scene[]
  resultVideoUrl: string | null
  
  setMode(mode)
  setScript(script)
  analyzeScript()
  searchMaterials()
  // ...
}
```

### 5.3 新增页面/组件

| 文件 | 职责 |
|------|------|
| `components/ai/ScriptInput.tsx` | 文案输入框 |
| `components/ai/TaskProgress.tsx` | AI任务进度显示 |
| `components/ai/SceneConfirm.tsx` | 场景确认（可选） |

---

## 6. 后端实现

### 6.1 目录结构

```
backend/
├── main.py              # FastAPI 入口
├── api/
│   └── ai.py           # AI 相关路由
├── services/
│   ├── gpt_service.py  # GPT 调用
│   ├── search_service.py # yt-dlp 搜索下载
│   └── render_service.py # FFmpeg 合成
├── models/
│   └── task.py          # 任务模型
├── utils/
│   └── websocket.py    # WebSocket 帮助
├── downloads/          # 临时下载目录
└── output/             # 输出视频目录
```

### 6.2 依赖

```
fastapi
uvicorn
openai
yt-dlp
ffmpeg-python
websockets
python-multipart
```

---

## 7. 实现计划

### Phase 1: 基础架构
- [ ] 创建后端项目结构
- [ ] 实现 `/api/ai/analyze` 接口
- [ ] 前端新增 AI mode 切换
- [ ] 前后端联调 GPT 分析

### Phase 2: 素材搜索
- [ ] 实现 yt-dlp 搜索下载服务
- [ ] 实现 `/api/ai/search` 接口
- [ ] WebSocket 进度推送
- [ ] 前后端联调

### Phase 3: 视频合成
- [ ] 实现 FFmpeg 拼接服务
- [ ] 实现 `/api/ai/render` 接口
- [ ] 进度推送 + 结果返回
- [ ] 视频预览 + 下载

### Phase 4: 体验优化
- [ ] 场景确认（可选步骤）
- [ ] 错误处理优化
- [ ] 视频质量优化

---

## 8. 待确认事项

1. **YouTube API Key**：是否已有 yt-dlp 或需要配置？
2. **OpenAI API Key**：已有还是需要申请？
3. **服务器配置**：是否有可用的 Docker 环境？
4. **视频时长限制**：单次任务最长时间/片段数？

---

## 9. 风险与备选

| 风险 | 应对 |
|------|------|
| YouTube 下载不稳定 | 降级为 Pexels/Pixabay API |
| GPT 分析质量差 | 提供人工调整入口 |
| FFmpeg 合成慢 | 限制总时长或异步处理 |
| API 成本 | 考虑缓存 + 分级处理 |

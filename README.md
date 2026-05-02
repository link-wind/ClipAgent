# ClipForge Agent

对话式智能剪辑 Agent。用户输入视频目标，Agent 先生成剪辑方案；用户确认后，后端搜索公开视频素材、下载素材，并用 FFmpeg 渲染为 MP4。

## 技术栈

- Next.js 14 + React 18 + TypeScript
- Zustand
- FastAPI + Pydantic
- yt-dlp
- FFmpeg / ffmpeg-python

## 启动前端

```bash
npm install
npm run dev
```

前端默认运行在 <http://localhost:3000>，并将 `/api/agent/*` 代理到后端。

## 启动后端

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8010
```

如果使用项目虚拟环境：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8010
```

## 环境变量

- `OPENAI_API_KEY`：用于生成智能剪辑方案。
- `OPENAI_BASE_URL`：可选，兼容 OpenAI API 的代理地址。
- `CLIPFORGE_API_ORIGIN`：可选，Next.js 代理目标，默认 `http://127.0.0.1:8010`。

本机需要可执行的 FFmpeg，后端需要能访问公开视频平台，yt-dlp 才能完成真实素材搜索和下载。

如果 YouTube 下载出现 `Precondition check failed`、`HTTP Error 400`、`nsig extraction failed`、`n challenge solving failed`，通常是本地 yt-dlp 版本太旧、JavaScript 运行时不可用，或 YouTube 播放器规则变化。先更新后端依赖：

```bash
pip install -r backend/requirements.txt --upgrade
```

项目已加入 `yt-dlp-ejs` 和 `curl-cffi`，用于提升 YouTube JS 解析和网络客户端兼容性。

本机还需要能在命令行运行 `node --version`。如果日志出现 `GVS PO Token` 或 `Only images are available for download`，说明 YouTube 对当前视频或当前网络环境要求额外 Cookie/PO Token；这种情况下 Agent 会尝试其它候选视频，但 YouTube 仍可能整体不可用。稳定生产链路建议再接入 Pexels/Pixabay/本地素材池作为备用素材源。

## 当前工作流

1. 在首页对话框输入视频目标、风格、时长和素材偏好。
2. Agent 返回结构化剪辑计划。
3. 继续对话修改计划，或点击“确认并开始”。
4. 后端搜索和下载素材，使用本地素材路径渲染成片。
5. 前端展示执行进度、结果预览和下载入口。

旧的人工时间线、素材库、检查器和浏览器端 FFmpeg 页面已经从前端移除，项目入口聚焦在智能剪辑 Agent。

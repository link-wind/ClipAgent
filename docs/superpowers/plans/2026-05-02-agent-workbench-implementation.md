# Agent Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert ClipForge into a conversational smart-editing Agent workbench with confirmed execution, real video search/download, and a single user-facing AI workflow.

**Architecture:** Next.js renders one Agent workspace and proxies `/api/agent/*` to FastAPI. FastAPI owns in-memory Agent sessions, structured edit plans, search/download, and render orchestration. The first implementation uses polling for progress and keeps WebSocket as a later extension point.

**Tech Stack:** Next.js 14, React 18, TypeScript, Zustand, FastAPI, Pydantic v2, unittest, yt-dlp, ffmpeg-python.

---

## File Structure

- Create `backend/models/agent.py` for Agent session, plan, message, clip, status, and error models.
- Create `backend/services/agent_service.py` for session lifecycle, planning, message updates, confirmation, and status storage.
- Modify `backend/services/gpt_service.py` to return structured `EditPlan` JSON with deterministic fallback on missing API key.
- Modify `backend/services/search_service.py` to return `ClipInfo` objects with both `localPath` and `publicUrl`.
- Modify `backend/services/render_service.py` to render from local paths only.
- Create `backend/api/agent.py` for `/api/agent` routes.
- Modify `backend/main.py` to mount static paths consistently and include the new Agent router.
- Create `tests/test_agent_backend.py` for Python backend behavior.
- Modify `next.config.js` to add FastAPI rewrites.
- Create `src/lib/agentApi.ts` for front-end API calls.
- Create `src/stores/useAgentStore.ts` for Agent UI state.
- Create `src/components/agent/*` for the new workbench.
- Modify `src/app/page.tsx` to render only `AgentWorkspace`.
- Modify `src/app/globals.css` only if global layout fixes are needed.
- Create `.gitignore` to stop tracking generated outputs after cleanup.
- Modify `README.md` with Agent workbench setup instructions.

---

### Task 1: Repository Hygiene And Backend Import Regression

**Files:**
- Create: `.gitignore`
- Create: `tests/test_agent_backend.py`
- Modify: `backend/models/task.py`

- [ ] **Step 1: Write the failing import test**

Create `tests/test_agent_backend.py`:

```python
import importlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class BackendImportTests(unittest.TestCase):
    def test_backend_main_imports_without_model_name_errors(self):
        module = importlib.import_module("main")
        self.assertTrue(hasattr(module, "app"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend.BackendImportTests.test_backend_main_imports_without_model_name_errors -v
```

Expected: FAIL or ERROR with `NameError: name 'Dict' is not defined`.

- [ ] **Step 3: Fix the minimal import bug**

Modify `backend/models/task.py` import line:

```python
from typing import Dict, List, Optional
```

- [ ] **Step 4: Add `.gitignore`**

Create `.gitignore`:

```gitignore
.next/
node_modules/
.venv/
tsconfig.tsbuildinfo

backend/downloads/*
!backend/downloads/.gitkeep
backend/output/*
!backend/output/.gitkeep

.superpowers/
__pycache__/
*.py[cod]
.pytest_cache/
```

- [ ] **Step 5: Verify import test passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend.BackendImportTests.test_backend_main_imports_without_model_name_errors -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add .gitignore backend/models/task.py tests/test_agent_backend.py
git commit -m "test: add backend import regression"
```

---

### Task 2: Agent Models And Session Service

**Files:**
- Create: `backend/models/agent.py`
- Create: `backend/services/agent_service.py`
- Modify: `tests/test_agent_backend.py`

- [ ] **Step 1: Write failing model and session tests**

Append to `tests/test_agent_backend.py`:

```python
class AgentSessionTests(unittest.TestCase):
    def test_create_session_starts_idle_with_empty_messages(self):
        from models.agent import AgentStatus
        from services.agent_service import AgentService

        service = AgentService()
        session = service.create_session()

        self.assertEqual(session.status, AgentStatus.IDLE)
        self.assertEqual(session.messages, [])
        self.assertIsNone(session.plan)

    def test_create_session_with_prompt_generates_plan_ready_session(self):
        from models.agent import AgentStatus
        from services.agent_service import AgentService

        service = AgentService()
        session = service.create_session("做一个 30 秒科技产品短视频")

        self.assertEqual(session.status, AgentStatus.PLAN_READY)
        self.assertEqual(session.messages[0].role, "user")
        self.assertIsNotNone(session.plan)
        self.assertGreater(len(session.plan.scenes), 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend.AgentSessionTests -v
```

Expected: ERROR with `ModuleNotFoundError: No module named 'models.agent'`.

- [ ] **Step 3: Create Agent models**

Create `backend/models/agent.py`:

```python
from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    PLAN_READY = "plan_ready"
    SEARCHING = "searching"
    DOWNLOADING = "downloading"
    RENDERING = "rendering"
    DONE = "done"
    FAILED = "failed"


class AgentMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    createdAt: str


class PlanScene(BaseModel):
    id: int
    description: str
    keywords: List[str] = Field(default_factory=list)
    duration: float = 6.0
    searchQuery: str


class EditPlan(BaseModel):
    title: str
    targetDuration: float = 30.0
    style: str = "cinematic"
    scenes: List[PlanScene]


class ClipInfo(BaseModel):
    sceneId: int
    sourceUrl: str
    localPath: str
    publicUrl: str
    startTime: float = 0.0
    duration: float = 6.0


class AgentError(BaseModel):
    message: str
    retryableStep: Optional[str] = None


class AgentSession(BaseModel):
    id: str
    status: AgentStatus = AgentStatus.IDLE
    messages: List[AgentMessage] = Field(default_factory=list)
    plan: Optional[EditPlan] = None
    clips: List[ClipInfo] = Field(default_factory=list)
    videoUrl: Optional[str] = None
    error: Optional[AgentError] = None
    progress: float = 0.0
    currentStep: str = ""
```

- [ ] **Step 4: Create minimal Agent service with fallback planner**

Create `backend/services/agent_service.py`:

```python
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from models.agent import AgentMessage, AgentSession, AgentStatus, EditPlan, PlanScene


class AgentService:
    def __init__(self):
        self.sessions: Dict[str, AgentSession] = {}

    def create_session(self, prompt: Optional[str] = None) -> AgentSession:
        session = AgentSession(id=str(uuid.uuid4()))
        self.sessions[session.id] = session
        if prompt and prompt.strip():
            self.add_user_message(session.id, prompt)
            self._set_plan(session, self._fallback_plan(prompt))
        return session

    def get_session(self, session_id: str) -> AgentSession:
        return self.sessions[session_id]

    def add_user_message(self, session_id: str, content: str) -> AgentSession:
        session = self.sessions[session_id]
        session.messages.append(self._message("user", content))
        if session.plan is None:
            self._set_plan(session, self._fallback_plan(content))
        elif session.status == AgentStatus.PLAN_READY:
            self._set_plan(session, self._fallback_plan(content, title=session.plan.title))
        return session

    def _set_plan(self, session: AgentSession, plan: EditPlan) -> None:
        session.status = AgentStatus.PLAN_READY
        session.plan = plan
        session.progress = 20
        session.currentStep = "剪辑方案已生成"
        session.messages.append(self._message("assistant", "我已经生成剪辑方案，你可以继续修改或确认开始。"))

    def _message(self, role: str, content: str) -> AgentMessage:
        return AgentMessage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            createdAt=datetime.now(timezone.utc).isoformat(),
        )

    def _fallback_plan(self, prompt: str, title: str = "智能剪辑短片") -> EditPlan:
        return EditPlan(
            title=title,
            targetDuration=30,
            style="快节奏社媒短片",
            scenes=[
                PlanScene(id=1, description="开场建立氛围", keywords=["technology", "city", "motion"], duration=6, searchQuery="technology city motion"),
                PlanScene(id=2, description="展示核心功能或主题", keywords=["product", "interface", "detail"], duration=8, searchQuery="product interface detail"),
                PlanScene(id=3, description="呈现真实使用场景", keywords=["people", "work", "collaboration"], duration=10, searchQuery="people work collaboration"),
                PlanScene(id=4, description="收束到品牌和行动号召", keywords=["brand", "clean", "ending"], duration=6, searchQuery="clean brand ending"),
            ],
        )


agent_service = AgentService()
```

- [ ] **Step 5: Verify tests pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend.AgentSessionTests -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/models/agent.py backend/services/agent_service.py tests/test_agent_backend.py
git commit -m "feat: add agent session models"
```

---

### Task 3: Agent API Routes

**Files:**
- Create: `backend/api/agent.py`
- Modify: `backend/main.py`
- Modify: `tests/test_agent_backend.py`

- [ ] **Step 1: Write failing API tests**

Append to `tests/test_agent_backend.py`:

```python
class AgentApiTests(unittest.TestCase):
    def test_create_session_api_returns_plan_ready_session(self):
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        response = client.post("/api/agent/sessions", json={"message": "做一个科技短片"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "plan_ready")
        self.assertIn("plan", data)
        self.assertGreater(len(data["plan"]["scenes"]), 0)

    def test_add_message_updates_existing_session(self):
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        created = client.post("/api/agent/sessions", json={"message": "做一个科技短片"}).json()
        response = client.post(
            f"/api/agent/sessions/{created['id']}/messages",
            json={"message": "更商务一点"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "plan_ready")
        self.assertGreaterEqual(len(data["messages"]), 3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend.AgentApiTests -v
```

Expected: FAIL with 404 for `/api/agent/sessions`.

- [ ] **Step 3: Create Agent API router**

Create `backend/api/agent.py`:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.agent import AgentSession
from services.agent_service import agent_service


router = APIRouter()


class SessionCreateRequest(BaseModel):
    message: str | None = None


class MessageRequest(BaseModel):
    message: str


@router.post("/sessions", response_model=AgentSession)
async def create_session(request: SessionCreateRequest):
    return agent_service.create_session(request.message)


@router.get("/sessions/{session_id}", response_model=AgentSession)
async def get_session(session_id: str):
    try:
        return agent_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions/{session_id}/messages", response_model=AgentSession)
async def add_message(session_id: str, request: MessageRequest):
    try:
        return agent_service.add_user_message(session_id, request.message)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
```

- [ ] **Step 4: Mount the router**

Modify `backend/main.py` imports:

```python
from api.agent import router as agent_router
from api.ai import router as ai_router
```

Modify router includes:

```python
app.include_router(agent_router, prefix="/api/agent")
app.include_router(ai_router, prefix="/api/ai")
```

- [ ] **Step 5: Verify API tests pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend.AgentApiTests -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/api/agent.py backend/main.py tests/test_agent_backend.py
git commit -m "feat: add agent session api"
```

---

### Task 4: Search And Render Contract

**Files:**
- Modify: `backend/services/search_service.py`
- Modify: `backend/services/render_service.py`
- Modify: `backend/services/agent_service.py`
- Modify: `backend/api/agent.py`
- Modify: `tests/test_agent_backend.py`

- [ ] **Step 1: Write failing contract tests**

Append to `tests/test_agent_backend.py`:

```python
class AgentExecutionContractTests(unittest.TestCase):
    def test_clip_info_contains_local_and_public_paths(self):
        from models.agent import ClipInfo

        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/watch?v=1",
            localPath="D:/Code/ClipForge_v2/backend/downloads/example.mp4",
            publicUrl="/downloads/example.mp4",
            startTime=0,
            duration=6,
        )

        self.assertTrue(clip.localPath.endswith("example.mp4"))
        self.assertEqual(clip.publicUrl, "/downloads/example.mp4")

    def test_render_uses_local_path_inputs(self):
        from models.agent import ClipInfo
        from services.render_service import build_render_inputs

        clips = [
            ClipInfo(
                sceneId=1,
                sourceUrl="https://example.com/source",
                localPath="backend/downloads/a.mp4",
                publicUrl="/downloads/a.mp4",
                duration=6,
            )
        ]

        self.assertEqual(build_render_inputs(clips), ["backend/downloads/a.mp4"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend.AgentExecutionContractTests -v
```

Expected: ERROR because `build_render_inputs` does not exist.

- [ ] **Step 3: Add render input helper**

Modify `backend/services/render_service.py`:

```python
from models.agent import ClipInfo


def build_render_inputs(clips: List[ClipInfo]) -> List[str]:
    """返回 FFmpeg 使用的本地素材路径。"""
    return [clip.localPath for clip in clips]
```

Update `concat_clips_simple` to use `clip.localPath` instead of `clip.videoUrl`.

- [ ] **Step 4: Add Agent confirmation path**

Modify `backend/services/agent_service.py`:

```python
from models.agent import AgentError, ClipInfo


async def confirm_session(self, session_id: str) -> AgentSession:
    session = self.sessions[session_id]
    if session.plan is None:
        session.status = AgentStatus.FAILED
        session.error = AgentError(message="没有可执行的剪辑方案", retryableStep="planning")
        return session
    session.status = AgentStatus.SEARCHING
    session.progress = 30
    session.currentStep = "正在搜索素材"
    return session
```

If editing in class form, add this method inside `AgentService`.

- [ ] **Step 5: Add confirm API endpoint**

Modify `backend/api/agent.py`:

```python
@router.post("/sessions/{session_id}/confirm", response_model=AgentSession)
async def confirm_session(session_id: str):
    try:
        return await agent_service.confirm_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
```

- [ ] **Step 6: Verify contract tests pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend.AgentExecutionContractTests -v
```

Expected: PASS.

- [ ] **Step 7: Verify all backend tests pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add backend/services/search_service.py backend/services/render_service.py backend/services/agent_service.py backend/api/agent.py tests/test_agent_backend.py
git commit -m "feat: define agent execution contract"
```

---

### Task 5: Next Rewrites And Frontend API Client

**Files:**
- Modify: `next.config.js`
- Create: `src/lib/agentApi.ts`
- Create: `src/stores/useAgentStore.ts`

- [ ] **Step 1: Write frontend types and API client**

Create `src/lib/agentApi.ts`:

```typescript
export type AgentStatus =
  | 'idle'
  | 'planning'
  | 'plan_ready'
  | 'searching'
  | 'downloading'
  | 'rendering'
  | 'done'
  | 'failed';

export interface AgentMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  createdAt: string;
}

export interface PlanScene {
  id: number;
  description: string;
  keywords: string[];
  duration: number;
  searchQuery: string;
}

export interface EditPlan {
  title: string;
  targetDuration: number;
  style: string;
  scenes: PlanScene[];
}

export interface ClipInfo {
  sceneId: number;
  sourceUrl: string;
  localPath: string;
  publicUrl: string;
  startTime: number;
  duration: number;
}

export interface AgentSession {
  id: string;
  status: AgentStatus;
  messages: AgentMessage[];
  plan: EditPlan | null;
  clips: ClipInfo[];
  videoUrl: string | null;
  progress: number;
  currentStep: string;
  error: { message: string; retryableStep?: string | null } | null;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function createAgentSession(message: string): Promise<AgentSession> {
  return request<AgentSession>('/api/agent/sessions', {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}

export function sendAgentMessage(sessionId: string, message: string): Promise<AgentSession> {
  return request<AgentSession>(`/api/agent/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}

export function confirmAgentSession(sessionId: string): Promise<AgentSession> {
  return request<AgentSession>(`/api/agent/sessions/${sessionId}/confirm`, {
    method: 'POST',
  });
}

export function getAgentSession(sessionId: string): Promise<AgentSession> {
  return request<AgentSession>(`/api/agent/sessions/${sessionId}`);
}
```

- [ ] **Step 2: Create Agent store**

Create `src/stores/useAgentStore.ts`:

```typescript
import { create } from 'zustand';
import type { AgentSession } from '@/lib/agentApi';

interface AgentStore {
  session: AgentSession | null;
  isSubmitting: boolean;
  setSession: (session: AgentSession | null) => void;
  setSubmitting: (value: boolean) => void;
  reset: () => void;
}

export const useAgentStore = create<AgentStore>((set) => ({
  session: null,
  isSubmitting: false,
  setSession: (session) => set({ session }),
  setSubmitting: (isSubmitting) => set({ isSubmitting }),
  reset: () => set({ session: null, isSubmitting: false }),
}));
```

- [ ] **Step 3: Add Next rewrites**

Modify `next.config.js`:

```javascript
/** @type {import('next').NextConfig} */
const API_ORIGIN = process.env.CLIPFORGE_API_ORIGIN || 'http://127.0.0.1:8000';

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/agent/:path*',
        destination: `${API_ORIGIN}/api/agent/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
          { key: 'Cross-Origin-Embedder-Policy', value: 'require-corp' },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
```

- [ ] **Step 4: Verify TypeScript**

Run:

```powershell
npx tsc --noEmit
```

Expected: exit code 0.

- [ ] **Step 5: Commit**

```powershell
git add next.config.js src/lib/agentApi.ts src/stores/useAgentStore.ts
git commit -m "feat: add agent frontend client"
```

---

### Task 6: Agent Workbench UI

**Files:**
- Create: `src/components/agent/AgentWorkspace.tsx`
- Create: `src/components/agent/AgentWorkspace.module.css`
- Create: `src/components/agent/AgentChat.tsx`
- Create: `src/components/agent/AgentChat.module.css`
- Create: `src/components/agent/PlanPanel.tsx`
- Create: `src/components/agent/PlanPanel.module.css`
- Create: `src/components/agent/ProgressPanel.tsx`
- Create: `src/components/agent/ProgressPanel.module.css`
- Create: `src/components/agent/ResultPanel.tsx`
- Create: `src/components/agent/ResultPanel.module.css`
- Modify: `src/app/page.tsx`

- [ ] **Step 1: Create Agent workspace shell**

Create `src/components/agent/AgentWorkspace.tsx`:

```tsx
'use client';

import { useEffect } from 'react';
import AgentChat from './AgentChat';
import PlanPanel from './PlanPanel';
import ProgressPanel from './ProgressPanel';
import ResultPanel from './ResultPanel';
import styles from './AgentWorkspace.module.css';
import { getAgentSession } from '@/lib/agentApi';
import { useAgentStore } from '@/stores/useAgentStore';

export default function AgentWorkspace() {
  const { session, setSession } = useAgentStore();

  useEffect(() => {
    if (!session || session.status === 'idle' || session.status === 'plan_ready' || session.status === 'done' || session.status === 'failed') {
      return;
    }
    const timer = window.setInterval(async () => {
      const next = await getAgentSession(session.id);
      setSession(next);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [session, setSession]);

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div>
          <div className={styles.brand}>ClipForge Agent</div>
          <div className={styles.subtle}>对话式智能剪辑工作台</div>
        </div>
        <div className={styles.status}>{session?.currentStep || '等待需求'}</div>
      </header>
      <main className={styles.main}>
        <AgentChat />
        <aside className={styles.side}>
          <PlanPanel />
          <ProgressPanel />
          <ResultPanel />
        </aside>
      </main>
    </div>
  );
}
```

Create `src/components/agent/AgentWorkspace.module.css` with responsive two-column layout:

```css
.shell {
  min-height: 100vh;
  display: grid;
  grid-template-rows: 64px 1fr;
  background: #101216;
  color: #eef2f5;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  border-bottom: 1px solid #242a33;
  background: #151922;
}

.brand {
  font-size: 18px;
  font-weight: 700;
}

.subtle,
.status {
  color: #8fa0b5;
  font-size: 13px;
}

.main {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(420px, 1fr) 420px;
}

.side {
  min-height: 0;
  overflow: auto;
  border-left: 1px solid #242a33;
  background: #12161d;
}

@media (max-width: 960px) {
  .main {
    grid-template-columns: 1fr;
  }

  .side {
    border-left: 0;
    border-top: 1px solid #242a33;
  }
}
```

- [ ] **Step 2: Create chat component**

Create `src/components/agent/AgentChat.tsx`:

```tsx
'use client';

import { useState } from 'react';
import styles from './AgentChat.module.css';
import { confirmAgentSession, createAgentSession, sendAgentMessage } from '@/lib/agentApi';
import { useAgentStore } from '@/stores/useAgentStore';

export default function AgentChat() {
  const [text, setText] = useState('');
  const { session, isSubmitting, setSession, setSubmitting } = useAgentStore();
  const canConfirm = session?.status === 'plan_ready';

  const submit = async () => {
    if (!text.trim()) return;
    setSubmitting(true);
    try {
      const next = session
        ? await sendAgentMessage(session.id, text)
        : await createAgentSession(text);
      setSession(next);
      setText('');
    } finally {
      setSubmitting(false);
    }
  };

  const confirm = async () => {
    if (!session) return;
    setSubmitting(true);
    try {
      setSession(await confirmAgentSession(session.id));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className={styles.chat}>
      <div className={styles.messages}>
        {!session && (
          <div className={styles.empty}>描述你想要的视频，Agent 会先生成方案，确认后再开始搜索和渲染。</div>
        )}
        {session?.messages.map((message) => (
          <div key={message.id} className={`${styles.message} ${message.role === 'user' ? styles.user : ''}`}>
            <span className={styles.role}>{message.role === 'user' ? '你' : 'ClipForge Agent'}</span>
            <p>{message.content}</p>
          </div>
        ))}
      </div>
      <div className={styles.composer}>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="告诉 Agent 你想要的视频，或继续修改方案..."
          disabled={isSubmitting}
        />
        <div className={styles.actions}>
          <button type="button" onClick={submit} disabled={isSubmitting || !text.trim()}>
            发送
          </button>
          <button type="button" className={styles.primary} onClick={confirm} disabled={isSubmitting || !canConfirm}>
            确认并开始
          </button>
        </div>
      </div>
    </section>
  );
}
```

Create CSS with stable button sizes and no nested card styling:

```css
.chat {
  min-height: 0;
  display: grid;
  grid-template-rows: 1fr auto;
}

.messages {
  min-height: 0;
  overflow: auto;
  padding: 28px;
}

.empty,
.message {
  max-width: 760px;
  margin-bottom: 16px;
  padding: 16px 18px;
  border: 1px solid #2a303a;
  border-radius: 8px;
  background: #171c25;
  line-height: 1.6;
}

.user {
  margin-left: auto;
  background: #17352e;
  border-color: #245c4e;
}

.role {
  display: block;
  margin-bottom: 8px;
  color: #9db0c7;
  font-size: 12px;
}

.message p {
  margin: 0;
}

.composer {
  padding: 18px 28px;
  border-top: 1px solid #242a33;
  background: #151922;
}

.composer textarea {
  width: 100%;
  min-height: 96px;
  resize: vertical;
  border: 1px solid #2f3845;
  border-radius: 8px;
  background: #10141b;
  color: #eef2f5;
  padding: 14px;
  font: inherit;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
}

.actions button {
  min-width: 96px;
  min-height: 40px;
  border: 0;
  border-radius: 7px;
  color: #dce6f2;
  background: #252d38;
  font-weight: 700;
}

.actions .primary {
  color: #07110e;
  background: #35d39b;
}

.actions button:disabled {
  opacity: 0.45;
}
```

- [ ] **Step 3: Create right-side panels**

Create `PlanPanel.tsx`, `ProgressPanel.tsx`, and `ResultPanel.tsx` using `useAgentStore()` and render empty states when no session exists. Keep each panel in its own CSS module with `padding: 22px`, `border-bottom: 1px solid #242a33`, and card radius no larger than `8px`.

- [ ] **Step 4: Replace homepage entry**

Modify `src/app/page.tsx`:

```tsx
import AgentWorkspace from '@/components/agent/AgentWorkspace';

export default function HomePage() {
  return <AgentWorkspace />;
}
```

- [ ] **Step 5: Verify TypeScript**

Run:

```powershell
npx tsc --noEmit
```

Expected: exit code 0.

- [ ] **Step 6: Commit**

```powershell
git add src/app/page.tsx src/components/agent
git commit -m "feat: replace editor with agent workbench"
```

---

### Task 7: README And End-To-End Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Replace Phase 1 manual-editor copy with:

```markdown
# ClipForge Agent

对话式智能剪辑 Agent。用户输入视频目标，Agent 生成剪辑方案；用户确认后，后端搜索公开视频素材、下载并用 FFmpeg 渲染为 MP4。

## 启动

前端：

```bash
npm install
npm run dev
```

后端：

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

环境变量：

- `OPENAI_API_KEY`：用于生成剪辑方案。
- `OPENAI_BASE_URL`：可选，兼容 OpenAI API 的代理地址。
- `CLIPFORGE_API_ORIGIN`：可选，Next.js 代理目标，默认 `http://127.0.0.1:8000`。

本机还需要可执行的 FFmpeg。
```

- [ ] **Step 2: Run backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend -v
```

Expected: PASS.

- [ ] **Step 3: Run TypeScript check**

Run:

```powershell
npx tsc --noEmit
```

Expected: exit code 0.

- [ ] **Step 4: Try production build**

Run:

```powershell
npm run build
```

Expected: exit code 0. If sandbox returns `spawn EPERM`, report it as environment-blocked and include the exact error in the final status.

- [ ] **Step 5: Commit**

```powershell
git add README.md
git commit -m "docs: update agent workbench setup"
```

---

## Self-Review Checklist

- Every design requirement maps to at least one task.
- Back-end startup regression is covered before implementation.
- Agent API uses `/api/agent`, not `/api/ai`.
- Frontend no longer exposes artificial manual editor routes.
- Search/render path contract explicitly separates `localPath` and `publicUrl`.
- Generated files are ignored by `.gitignore`.
- Verification commands include backend tests, TypeScript, and build attempt.

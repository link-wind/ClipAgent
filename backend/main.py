import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.agent import router as agent_router
from backend.api.ai import router as ai_router
from backend.api.config import router as config_router
from backend.db import engine as _engine
from backend.utils.websocket import ws_manager


BACKEND_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = BACKEND_DIR / "downloads"
OUTPUT_DIR = BACKEND_DIR / "output"


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    yield


app = FastAPI(title="ClipForge API", lifespan=lifespan)

# 挂载 Agent 素材和渲染结果目录
app.mount("/downloads", StaticFiles(directory=str(DOWNLOADS_DIR)), name="downloads")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router, prefix="/api/agent")
app.include_router(ai_router, prefix="/api/ai")
app.include_router(config_router, prefix="/api/config")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.websocket("/ws/ai/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await ws_manager.connect(task_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await ws_manager.send_progress(task_id, 0.5, "Processing", {"received": data})
    except Exception:
        ws_manager.disconnect(task_id)

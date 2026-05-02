import uuid
import asyncio
from typing import Dict
from fastapi import APIRouter, HTTPException

from backend.models.task import (
    TaskStatus,
    AnalyzeRequest,
    AnalyzeResponse,
    SearchRequest,
    SearchResponse,
    TaskStatusResponse,
    TaskResultResponse,
    RenderRequest,
    RenderResponse,
    Scene,
)
from backend.services.gpt_service import gpt_service
from backend.services.search_service import search_and_download_all
from backend.services.render_service import render_video
from backend.utils.websocket import ws_manager

router = APIRouter()

tasks: Dict[str, dict] = {}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_script(request: AnalyzeRequest):
    try:
        scenes = await gpt_service.analyze_script(request.script)
        return AnalyzeResponse(scenes=scenes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResponse)
async def search_scenes(request: SearchRequest):
    task_id = str(uuid.uuid4())

    tasks[task_id] = {
        "status": TaskStatus.SEARCHING,
        "progress": 0.0,
        "currentStep": "Searching for videos...",
        "scenes": request.scenes,
        "clips": [],
        "videoUrl": None,
    }

    await ws_manager.send_progress(task_id, 0.1, "Searching started", {"taskId": task_id})

    # 异步启动搜索下载任务
    asyncio.create_task(_run_search_and_download(task_id, request.scenes))

    return SearchResponse(taskId=task_id, status=TaskStatus.SEARCHING)


async def _run_search_and_download(task_id: str, scenes: list):
    """后台运行搜索下载"""
    from backend.models.task import ClipInfo
    try:
        # 1. 搜索下载
        clips = await search_and_download_all(task_id, scenes, progress_start=10, progress_end=90)
        tasks[task_id]["clips"] = [clip.model_dump() for clip in clips]
        tasks[task_id]["status"] = TaskStatus.DONE
        tasks[task_id]["progress"] = 50.0
        tasks[task_id]["currentStep"] = "素材下载完成，开始合成..."
        await ws_manager.send_progress(task_id, 50, "素材下载完成，开始合成...", {"clips": [clip.model_dump() for clip in clips]})

        # 2. 自动开始渲染
        output_filename = f"{task_id}.mp4"
        video_url = await render_video(task_id, clips, output_filename)
        tasks[task_id]["videoUrl"] = video_url
        tasks[task_id]["status"] = TaskStatus.DONE
        tasks[task_id]["progress"] = 100.0
        tasks[task_id]["currentStep"] = "完成"
        await ws_manager.send_progress(task_id, 100, "完成", {"videoUrl": video_url})
    except Exception as e:
        tasks[task_id]["status"] = TaskStatus.FAILED
        tasks[task_id]["currentStep"] = f"处理失败: {e}"
        await ws_manager.send_progress(task_id, -1, f"处理失败: {e}", {})


@router.post("/render", response_model=RenderResponse)
async def render(req: RenderRequest):
    """
    接受片段列表，开始渲染任务
    返回 taskId 和状态
    """
    task_id = req.taskId

    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    # 更新任务状态为 RENDERING
    tasks[task_id]["status"] = TaskStatus.RENDERING
    tasks[task_id]["progress"] = 0.0
    tasks[task_id]["currentStep"] = "Starting render..."

    # 异步调用 render_video
    asyncio.create_task(_run_render(task_id, req.clips))

    return RenderResponse(taskId=task_id, status=TaskStatus.RENDERING)


async def _run_render(task_id: str, clips: list):
    """后台运行渲染"""
    from backend.models.task import ClipInfo
    try:
        clips_info = [ClipInfo(**c) for c in clips]
        output_filename = f"{task_id}.mp4"
        video_url = await render_video(task_id, clips_info, output_filename)
        tasks[task_id]["videoUrl"] = video_url
        tasks[task_id]["status"] = TaskStatus.DONE
        tasks[task_id]["progress"] = 100.0
        tasks[task_id]["currentStep"] = "Render completed"
    except Exception as e:
        tasks[task_id]["status"] = TaskStatus.FAILED
        tasks[task_id]["currentStep"] = f"Render failed: {e}"
        await ws_manager.send_progress(task_id, -1, f"Render failed: {e}", {})


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    return TaskStatusResponse(
        status=task["status"],
        progress=task["progress"],
        currentStep=task["currentStep"],
        videoUrl=task.get("videoUrl"),
    )


@router.get("/result/{task_id}", response_model=TaskResultResponse)
async def get_result(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    if task["status"] != TaskStatus.DONE:
        raise HTTPException(status_code=400, detail="Task not completed yet")

    return TaskResultResponse(taskId=task_id, clips=task.get("clips", []))

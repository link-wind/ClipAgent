import ffmpeg
import os
from typing import List, Union
from backend.models.agent import ClipInfo as AgentClipInfo
from backend.models.task import ClipInfo as TaskClipInfo
from backend.utils.websocket import ws_manager

OUTPUT_DIR = "backend/output"
RenderClip = Union[TaskClipInfo, AgentClipInfo]


def build_render_inputs(clips: List[RenderClip]) -> List[str]:
    """返回 FFmpeg 使用的本地素材路径。"""
    return [_clip_input_path(clip) for clip in clips]


def _clip_input_path(clip: RenderClip) -> str:
    """兼容新 Agent 本地路径和旧任务输入。"""
    if isinstance(clip, AgentClipInfo):
        return clip.localPath
    return clip.videoUrl


def check_ffmpeg():
    """检查FFmpeg是否可用"""
    try:
        ffmpeg.probe()
        return True
    except Exception:
        return False


def concat_clips_simple(clips: List[RenderClip], output_filename: str) -> str:
    """
    简单拼接：直接用 concat 协议拼接多个视频
    clips: 片段列表
    output_filename: 输出文件名
    返回: 相对URL路径 /output/{filename}
    """
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_path = os.path.join(OUTPUT_DIR, output_filename)

    # 如果只有一段视频，直接复制
    if len(clips) == 1:
        clip = clips[0]
        input_stream = ffmpeg.input(_clip_input_path(clip))
        ffmpeg.output(input_stream, output_path, c="copy").run(overwrite_output=True)
        return f"/output/{output_filename}"

    # 多段视频使用 concat 协议拼接
    inputs = []
    for clip in clips:
        inputs.append(ffmpeg.input(_clip_input_path(clip)))

    # 使用 concat 协议，v=1 表示视频，a=1 表示音频
    ffmpeg.concat(*inputs, v=1, a=1).output(output_path).run(overwrite_output=True)

    return f"/output/{output_filename}"


async def render_video(
    task_id: str,
    clips: List[RenderClip],
    output_filename: str
) -> str:
    """
    渲染视频并推送进度
    task_id: 任务ID
    clips: 片段列表
    output_filename: 输出文件名
    返回: 相对URL路径
    """
    # 1. 推送进度 50%，"正在合成视频..."
    await ws_manager.send_progress(task_id, 50, "正在合成视频...", {})

    # 2. 调用 concat_clips_simple
    video_url = concat_clips_simple(clips, output_filename)

    # 3. 推送进度 100%，"渲染完成"
    await ws_manager.send_progress(task_id, 100, "渲染完成", {"videoUrl": video_url})

    # 4. 返回视频URL
    return video_url

import os
import tempfile
from pathlib import Path
from typing import List, Union

import ffmpeg

from backend.models.agent import ClipInfo as AgentClipInfo
from backend.models.task import ClipInfo as TaskClipInfo
from backend.utils.websocket import ws_manager

OUTPUT_DIR = "backend/output"
VERTICAL_WIDTH = 720
VERTICAL_HEIGHT = 1280
OUTPUT_FPS = 30
RenderClip = Union[TaskClipInfo, AgentClipInfo]


def build_render_commands(clips: List[RenderClip], output_path: str) -> dict:
    """生成可测试的渲染配置。"""
    return {
        "segments": [
            {
                "input": _clip_input_path(clip),
                "trimStart": _clip_trim_start(clip),
                "trimDuration": _clip_trim_duration(clip),
            }
            for clip in clips
        ],
        "output": {
            "path": output_path,
            "width": VERTICAL_WIDTH,
            "height": VERTICAL_HEIGHT,
            "fps": OUTPUT_FPS,
            "vcodec": "libx264",
            "acodec": "aac",
        },
    }


def build_render_inputs(clips: List[RenderClip]) -> List[str]:
    """返回 FFmpeg 使用的本地素材路径。"""
    return [_clip_input_path(clip) for clip in clips]


def _clip_input_path(clip: RenderClip) -> str:
    """兼容新 Agent 本地路径和旧任务输入。"""
    if isinstance(clip, AgentClipInfo):
        return clip.localPath
    return clip.videoUrl


def _clip_trim_start(clip: RenderClip) -> float:
    """读取片段裁剪起点。"""
    return max(0.0, float(getattr(clip, "trimStart", 0.0) or 0.0))


def _clip_trim_duration(clip: RenderClip) -> float:
    """读取片段裁剪时长。"""
    trim_duration = float(getattr(clip, "trimDuration", getattr(clip, "duration", 0.0)) or 0.0)
    return max(0.0, trim_duration)


def check_ffmpeg():
    """检查 FFmpeg 是否可用。"""
    try:
        ffmpeg.probe(__file__)
    except ffmpeg.Error:
        return True
    except Exception:
        return False
    return True


def _ensure_output_dir() -> None:
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _render_segment(clip: RenderClip, segment_path: str) -> None:
    # 生成标准化竖屏片段
    input_path = _clip_input_path(clip)
    trim_start = _clip_trim_start(clip)
    trim_duration = _clip_trim_duration(clip)
    if trim_duration <= 0.0:
        raise RuntimeError(f"片段时长无效: {input_path}")
    if not os.path.exists(input_path):
        raise FileNotFoundError(input_path)

    source = ffmpeg.input(input_path, ss=trim_start, t=trim_duration)
    video_stream = (
        source.video
        .filter("scale", VERTICAL_WIDTH, VERTICAL_HEIGHT, force_original_aspect_ratio="increase")
        .filter("crop", VERTICAL_WIDTH, VERTICAL_HEIGHT)
        .filter("fps", fps=OUTPUT_FPS)
        .filter("setsar", "1")
    )
    audio_stream = (
        source.audio
        .filter("aresample", 44100)
        .filter("aformat", sample_fmts="fltp", channel_layouts="stereo")
    )
    (
        ffmpeg.output(
            video_stream,
            audio_stream,
            segment_path,
            vcodec="libx264",
            acodec="aac",
            pix_fmt="yuv420p",
            movflags="+faststart",
            video_bitrate="2200k",
            audio_bitrate="128k",
            r=OUTPUT_FPS,
        )
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )


def _concat_segments(segment_paths: List[str], output_path: str) -> None:
    # 用 concat demuxer 合并标准化片段
    if not segment_paths:
        raise RuntimeError("没有可渲染的有效片段")

    list_file = Path(output_path).with_suffix(".txt")
    list_file.write_text(
        "".join(f"file '{Path(path).resolve().as_posix()}'\n" for path in segment_paths),
        encoding="utf-8",
    )
    try:
        (
            ffmpeg.input(str(list_file), format="concat", safe=0)
            .output(
                output_path,
                c="copy",
                movflags="+faststart",
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    finally:
        if list_file.exists():
            list_file.unlink()


def render_shortform_video(clips: List[RenderClip], output_filename: str) -> str:
    """渲染竖屏短片并返回公开路径。"""
    _ensure_output_dir()
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    segment_paths: List[str] = []

    with tempfile.TemporaryDirectory(dir=OUTPUT_DIR) as temp_dir:
        for index, clip in enumerate(clips, start=1):
            segment_path = os.path.join(temp_dir, f"segment_{index:02d}.mp4")
            _render_segment(clip, segment_path)
            segment_paths.append(segment_path)
        _concat_segments(segment_paths, output_path)

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
    await ws_manager.send_progress(task_id, 50, "正在合成视频...", {})
    video_url = render_shortform_video(clips, output_filename)
    await ws_manager.send_progress(task_id, 100, "渲染完成", {"videoUrl": video_url})
    return video_url

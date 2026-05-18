import os
import tempfile
from pathlib import Path
from typing import Callable, List, Union

import ffmpeg

from backend.models.agent import ClipInfo as AgentClipInfo
from backend.models.task import ClipInfo as TaskClipInfo
from backend.utils.websocket import ws_manager

OUTPUT_DIR = "backend/output"
ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
BGM_PATH = str((ASSETS_DIR / "audio" / "default_bgm.mp3").resolve())
BGM_VOLUME = 0.18
VERTICAL_WIDTH = 720
VERTICAL_HEIGHT = 1280
OUTPUT_FPS = 30
RenderClip = Union[TaskClipInfo, AgentClipInfo]
RenderProgressCallback = Callable[[str, str, float], None]


def build_render_commands(clips: List[RenderClip], output_path: str) -> dict:
    """生成可测试的渲染配置。"""
    return {
        "segments": [
            {
                "input": _clip_input_path(clip),
                "caption": _clip_caption(clip),
                "trimStart": _clip_trim_start(clip),
                "trimDuration": _clip_trim_duration(clip),
            }
            for clip in clips
        ],
        "bgm": {
            "path": BGM_PATH,
            "volume": BGM_VOLUME,
        },
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


def _clip_caption(clip: RenderClip) -> str:
    """统一字幕字段类型。"""
    return str(getattr(clip, "caption", "") or "")


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


def _resolve_caption_font() -> str | None:
    """优先选择可用的中文字幕字体。"""
    env_font = os.environ.get("CLIPFORGE_CAPTION_FONT", "").strip()
    if env_font and Path(env_font).exists():
        return env_font

    font_candidates = [
        # 仓库内字体资源优先作为可迁移兜底
        ASSETS_DIR / "fonts" / "NotoSansCJK-Regular.ttc",
        ASSETS_DIR / "fonts" / "NotoSansCJK-Regular.otf",
        ASSETS_DIR / "fonts" / "SourceHanSansSC-Regular.otf",
        ASSETS_DIR / "fonts" / "SourceHanSansCN-Regular.otf",
        # Windows 常见中文字体
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyh.ttc",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyhbd.ttc",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "simhei.ttf",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "simsun.ttc",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arialuni.ttf",
        # Linux 常见字体位置
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
        Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
        Path("/usr/share/fonts/truetype/arphic/ukai.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        Path("/usr/local/share/fonts/NotoSansCJK-Regular.ttc"),
    ]
    for candidate in font_candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _apply_caption(video_stream, caption: str, segment_path: str):
    """为片段叠加字幕。"""
    font_path = _resolve_caption_font()
    if font_path is None:
        return video_stream, None

    caption_path = Path(segment_path).with_suffix(".caption.txt")
    caption_path.write_text(caption, encoding="utf-8")
    drawtext_kwargs = {
        "textfile": str(caption_path),
        "reload": 0,
        "fontsize": 42,
        "fontcolor": "white",
        "bordercolor": "black",
        "borderw": 4,
        "line_spacing": 10,
        "x": "(w-text_w)/2",
        "y": "h-text_h-96",
    }
    drawtext_kwargs["fontfile"] = font_path
    return video_stream.filter("drawtext", **drawtext_kwargs), caption_path


def _input_has_audio(input_path: str) -> bool:
    """探测输入是否包含音轨。"""
    try:
        probe = ffmpeg.probe(input_path)
    except Exception:
        return False
    return any(stream.get("codec_type") == "audio" for stream in probe.get("streams", []))


def _probe_media_duration(input_path: str) -> float | None:
    """读取媒体总时长，失败时返回空。"""
    try:
        probe = ffmpeg.probe(input_path)
    except Exception:
        return None

    format_info = probe.get("format", {})
    raw_duration = format_info.get("duration")
    if raw_duration in (None, ""):
        return None

    try:
        duration = float(raw_duration)
    except (TypeError, ValueError):
        return None
    return duration if duration > 0 else None


def _build_audio_stream(source, input_path: str, duration: float):
    """为片段生成可编码音轨。"""
    if _input_has_audio(input_path):
        audio_source = source.audio
    else:
        audio_source = ffmpeg.input(
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            f="lavfi",
            t=duration,
        ).audio
    return (
        audio_source
        .filter("aresample", 44100)
        .filter("aformat", sample_fmts="fltp", channel_layouts="stereo")
    )


def _render_segment(segment: dict, segment_path: str) -> None:
    # 生成标准化竖屏片段
    input_path = segment["input"]
    trim_start = max(0.0, float(segment.get("trimStart", 0.0) or 0.0))
    trim_duration = max(0.0, float(segment.get("trimDuration", 0.0) or 0.0))
    caption = str(segment.get("caption", "") or "")
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
    caption_path: Path | None = None
    if caption.strip():
        video_stream, caption_path = _apply_caption(video_stream, caption, segment_path)
    audio_stream = _build_audio_stream(source, input_path, trim_duration)
    try:
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
    finally:
        if caption_path is not None and caption_path.exists():
            caption_path.unlink()


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


def _mix_background_music(input_path: str, output_path: str, bgm: dict) -> None:
    """为成片混入默认 BGM。"""
    bgm_path = str(bgm["path"])
    if not os.path.exists(bgm_path):
        raise FileNotFoundError(bgm_path)

    base_video = ffmpeg.input(input_path)
    has_base_audio = _input_has_audio(input_path)
    base_duration = _probe_media_duration(input_path)
    bgm_audio = (
        ffmpeg.input(bgm_path, stream_loop=-1)
        .audio
        .filter("aresample", 44100)
        .filter("aformat", sample_fmts="fltp", channel_layouts="stereo")
        .filter("volume", bgm.get("volume", BGM_VOLUME))
    )
    output_audio = bgm_audio
    if has_base_audio:
        output_audio = ffmpeg.filter(
            [base_video.audio, bgm_audio],
            "amix",
            inputs=2,
            duration="first",
            dropout_transition=0,
        )
    elif base_duration is not None:
        output_audio = bgm_audio.filter("atrim", duration=base_duration)
    (
        ffmpeg.output(
            base_video.video,
            output_audio,
            output_path,
            vcodec="copy",
            acodec="aac",
            movflags="+faststart",
        )
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )


def render_shortform_video(
    clips: List[RenderClip],
    output_filename: str,
    progress_callback: RenderProgressCallback | None = None,
) -> str:
    """渲染竖屏短片并返回公开路径。"""
    _ensure_output_dir()
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    render_commands = build_render_commands(clips, output_path)
    segment_paths: List[str] = []

    with tempfile.TemporaryDirectory(dir=OUTPUT_DIR) as temp_dir:
        if progress_callback is not None:
            # 开始逐段渲染前通知字幕合成阶段
            progress_callback("render_captioning", "正在合成字幕", 82)
        for index, segment in enumerate(render_commands["segments"], start=1):
            segment_path = os.path.join(temp_dir, f"segment_{index:02d}.mp4")
            _render_segment(segment, segment_path)
            segment_paths.append(segment_path)
        concat_path = os.path.join(temp_dir, "concat.mp4")
        _concat_segments(segment_paths, concat_path)
        if progress_callback is not None:
            # 进入背景音乐混合前通知音频阶段
            progress_callback("render_audio_mix", "正在混合背景音乐", 88)
        _mix_background_music(concat_path, output_path, render_commands["bgm"])

    return f"/output/{output_filename}"


async def render_video(
    task_id: str,
    clips: List[RenderClip],
    output_filename: str,
    progress_callback: RenderProgressCallback | None = None,
) -> str:
    """
    渲染视频并推送进度
    task_id: 任务ID
    clips: 片段列表
    output_filename: 输出文件名
    返回: 相对URL路径
    """
    await ws_manager.send_progress(task_id, 50, "正在合成视频...", {})
    video_url = render_shortform_video(clips, output_filename, progress_callback=progress_callback)
    await ws_manager.send_progress(task_id, 100, "渲染完成", {"videoUrl": video_url})
    return video_url

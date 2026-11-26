"""FFmpeg 9:16 vertical clip renderer with blurred background or center crop."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def render_vertical_clip(
    source_video: Path,
    ass_subtitles: Path,
    output_video: Path,
    start_sec: float,
    end_sec: float,
    crop_mode: str = "blur",
) -> Path:
    """Cut [start_sec, end_sec], convert to 1080x1920, normalize audio, and burn captions."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "FFmpeg is not installed or not on PATH. "
            "Install it on Windows with: winget install Gyan.FFmpeg"
        )

    duration = max(1.0, end_sec - start_sec)
    output_video.parent.mkdir(parents=True, exist_ok=True)

    # Escape path for FFmpeg subtitles filter on Windows/Linux
    sub_escaped = str(ass_subtitles.resolve()).replace("\\", "/").replace(":", "\\:")

    if crop_mode == "fill":
        video_filter = (
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1,ass='{sub_escaped}'"
        )
    else:
        # Blurred 9:16 background + crisp centered 16:9 foreground
        video_filter = (
            f"[0:v]split=2[bg][fg];"
            f"[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,boxblur=25:5[bg_blur];"
            f"[fg]scale=1080:-2:force_original_aspect_ratio=decrease[fg_scaled];"
            f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2,setsar=1,ass='{sub_escaped}'"
        )

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start_sec:.2f}",
        "-i",
        str(source_video),
        "-t",
        f"{duration:.2f}",
        "-filter_complex" if crop_mode != "fill" else "-vf",
        video_filter,
        "-af",
        "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_video),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed ({result.returncode}):\n{result.stderr[-1500:]}")
    return output_video


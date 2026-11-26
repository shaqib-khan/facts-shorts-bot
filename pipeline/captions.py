"""Generate word-burst ASS subtitles for 9:16 YouTube Shorts."""

from __future__ import annotations

from pathlib import Path

from pipeline.fetcher import TranscriptSegment

ASS_HEADER = """[Script Info]
Title: YouTube Shorts Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,74,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,60,60,340,1
Style: Hook,Arial,68,&H0000E5FF,&H00FFFFFF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,6,2,8,60,60,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _fmt_ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _escape_ass(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def build_ass_subtitles(
    segments: list[TranscriptSegment],
    clip_start: float,
    clip_end: float,
    out_path: Path,
    hook_text: str = "",
    words_per_burst: int = 3,
) -> Path:
    """Slice transcript segments to [clip_start, clip_end] and write 2-3 word ASS bursts."""
    events: list[str] = []

    if hook_text:
        hook_end = min(3.5, max(1.5, clip_end - clip_start))
        events.append(
            f"Dialogue: 1,0:00:00.00,{_fmt_ass_time(hook_end)},Hook,,0,0,0,,{_escape_ass(hook_text.upper())}"
        )

    for seg in segments:
        if seg.end <= clip_start or seg.start >= clip_end:
            continue

        rel_start = max(0.0, seg.start - clip_start)
        rel_end = min(clip_end - clip_start, seg.end - clip_start)
        words = seg.text.split()
        if not words or rel_end <= rel_start:
            continue

        chunks = [words[i : i + words_per_burst] for i in range(0, len(words), words_per_burst)]
        chunk_dur = (rel_end - rel_start) / len(chunks)
        for idx, chunk in enumerate(chunks):
            c_start = rel_start + idx * chunk_dur
            c_end = rel_start + (idx + 1) * chunk_dur
            phrase = _escape_ass(" ".join(chunk).upper())
            events.append(
                f"Dialogue: 0,{_fmt_ass_time(c_start)},{_fmt_ass_time(c_end)},Default,,0,0,0,,{phrase}"
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(ASS_HEADER + "\n".join(events) + "\n", encoding="utf-8")
    return out_path


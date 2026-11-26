"""AI-powered highlight selection for Facts, Science & History clips."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from pipeline.config import PipelineConfig
from pipeline.fetcher import SourceVideo, TranscriptSegment

HOOK_KEYWORDS = (
    "did you know",
    "scientists",
    "discovered",
    "actually",
    "million years",
    "billion",
    "ancient",
    "secret",
    "never",
    "impossible",
    "strange",
    "weird",
    "history",
    "universe",
    "quantum",
)


@dataclass
class ClipPlan:
    """Selected highlight window and YouTube metadata."""

    start_sec: float
    end_sec: float
    hook: str
    yt_title: str
    yt_description: str
    tags: list[str]


def _format_transcript_for_llm(segments: list[TranscriptSegment], max_chars: int = 16000) -> str:
    lines: list[str] = []
    total = 0
    for seg in segments:
        line = f"[{seg.start:.1f}-{seg.end:.1f}] {seg.text}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)


def _fallback_highlight(source: SourceVideo, config: PipelineConfig) -> ClipPlan:
    """Score transcript windows by fact/science hook keywords, or pick a clean mid-video slice."""
    target_len = min(45.0, float(config.clip_max_sec))
    if source.duration > 0:
        max_start = max(0.0, source.duration - target_len)
    else:
        max_start = 0.0

    best_start = min(max_start, max(10.0, source.duration * 0.2))
    best_score = -1

    if source.segments:
        for i, seg in enumerate(source.segments):
            if seg.start > max_start and max_start > 0:
                break
            window_text = " ".join(
                s.text.lower()
                for s in source.segments[i : i + 12]
                if s.end - seg.start <= target_len
            )
            score = sum(2 for kw in HOOK_KEYWORDS if kw in window_text) + min(len(window_text) // 80, 3)
            if score > best_score:
                best_score = score
                best_start = seg.start

    end_sec = best_start + target_len
    if source.duration > 0:
        end_sec = min(end_sec, source.duration)

    clean_title = re.sub(r"\s+", " ", source.title).strip()[:75]
    return ClipPlan(
        start_sec=round(best_start, 2),
        end_sec=round(end_sec, 2),
        hook="WAIT UNTIL THE END",
        yt_title=f"{clean_title} #shorts",
        yt_description=(
            f"Clipped from: {source.title} ({source.channel})\n"
            f"Original video: {source.url}\n\n"
            "#shorts #facts #science #history #didyouknow"
        ),
        tags=["shorts", "facts", "science", "history", "education"],
    )


def select_highlight(source: SourceVideo, config: PipelineConfig) -> ClipPlan:
    """Use an OpenAI-compatible LLM to pick the best Facts/Science/History clip, with fallback."""
    if not config.llm_api_key or not source.segments:
        return _fallback_highlight(source, config)

    transcript_text = _format_transcript_for_llm(source.segments)
    prompt = f"""You are a viral YouTube Shorts editor specializing in Facts, Science, and History.
Given the timestamped transcript below from "{source.title}" by {source.channel} (duration: {source.duration:.0f}s),
select ONE self-contained segment between {config.clip_min_sec} and {config.clip_max_sec} seconds long that:
1. Starts on a strong curiosity hook, surprising fact, or historical turning point.
2. Ends cleanly on a complete thought or punchline.

Return ONLY valid JSON with these exact keys:
{{
  "start_sec": <number>,
  "end_sec": <number>,
  "hook": "<3-6 word uppercase visual hook>",
  "yt_title": "<catchy title under 85 chars ending with #shorts>",
  "tags": ["facts", "science", "history", "shorts"]
}}

Transcript:
{transcript_text}
"""

    try:
        resp = httpx.post(
            f"{config.llm_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
            },
            timeout=45.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return _fallback_highlight(source, config)

        data = json.loads(match.group(0))
        start = float(data["start_sec"])
        end = float(data["end_sec"])
        dur = end - start
        if dur < config.clip_min_sec or dur > config.clip_max_sec + 5:
            end = start + min(45.0, float(config.clip_max_sec))
        if source.duration > 0:
            end = min(end, source.duration)
            start = max(0.0, min(start, max(0.0, end - config.clip_min_sec)))

        yt_title = str(data.get("yt_title", source.title))[:95]
        if "#shorts" not in yt_title.lower():
            yt_title = f"{yt_title[:85]} #shorts"

        tags = [str(t) for t in data.get("tags", ["facts", "science", "history", "shorts"])][:10]
        return ClipPlan(
            start_sec=round(start, 2),
            end_sec=round(end, 2),
            hook=str(data.get("hook", "MIND-BLOWING FACT")).upper()[:40],
            yt_title=yt_title,
            yt_description=(
                f"Clipped from: {source.title} ({source.channel})\n"
                f"Original video: {source.url}\n\n"
                "#shorts #facts #science #history #didyouknow"
            ),
            tags=tags,
        )
    except Exception:
        return _fallback_highlight(source, config)


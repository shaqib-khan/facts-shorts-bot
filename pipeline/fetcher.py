"""Fetch source videos and transcripts using yt-dlp."""

from __future__ import annotations

import html
import random
import re
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

from pipeline.config import DEFAULT_QUERIES, PipelineConfig
from pipeline.history import is_processed


@dataclass
class TranscriptSegment:
    """A single timestamped caption line."""

    start: float
    end: float
    text: str


@dataclass
class SourceVideo:
    """Metadata and local paths for a fetched source video."""

    video_id: str
    title: str
    url: str
    channel: str
    duration: float
    video_path: Path | None
    segments: list[TranscriptSegment]


def _parse_vtt_timestamp(ts: str) -> float:
    """Convert HH:MM:SS.mmm or MM:SS.mmm to seconds."""
    parts = ts.strip().replace(",", ".").split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(parts[0])


def parse_vtt(vtt_path: Path) -> list[TranscriptSegment]:
    """Parse a WebVTT subtitle file into clean, deduplicated segments."""
    if not vtt_path.exists():
        return []

    raw_lines = vtt_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    time_re = re.compile(r"(\d{1,2}:?\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:?\d{2}:\d{2}[.,]\d{3})")
    tag_re = re.compile(r"<[^>]+>")

    segments: list[TranscriptSegment] = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i].strip()
        match = time_re.search(line)
        if not match:
            i += 1
            continue

        start = _parse_vtt_timestamp(match.group(1))
        end = _parse_vtt_timestamp(match.group(2))
        i += 1
        text_parts: list[str] = []
        while i < len(raw_lines) and raw_lines[i].strip():
            cleaned = tag_re.sub("", raw_lines[i]).strip()
            cleaned = html.unescape(cleaned)
            if cleaned:
                text_parts.append(cleaned)
            i += 1

        text = " ".join(text_parts).strip()
        text = re.sub(r"\s+", " ", text)
        if not text or end <= start:
            continue

        # YouTube auto-captions often repeat the previous line as a rolling window
        if segments and text == segments[-1].text:
            segments[-1].end = max(segments[-1].end, end)
            continue
        if segments and text.startswith(segments[-1].text) and len(text) > len(segments[-1].text):
            text = text[len(segments[-1].text):].strip()
            if not text:
                continue

        segments.append(TranscriptSegment(start=start, end=end, text=text))
    return segments


def pick_candidate_url(
    config: PipelineConfig,
    url: str | None = None,
    query: str | None = None,
) -> dict:
    """Resolve a direct URL or search YouTube for an unprocessed Facts/Science/History video."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }

    if url:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if "entries" in info:
            entries = [e for e in info["entries"] if e and not is_processed(config.history_file, e.get("id", ""))]
            if not entries:
                raise RuntimeError("No unprocessed videos found in the provided playlist/channel.")
            chosen = entries[0]
            return {"id": chosen["id"], "url": chosen.get("url") or f"https://www.youtube.com/watch?v={chosen['id']}"}
        return {"id": info["id"], "url": info.get("webpage_url") or url}

    search_query = query or random.choice(DEFAULT_QUERIES)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        results = ydl.extract_info(f"ytsearch10:{search_query}", download=False)

    entries = results.get("entries", []) if results else []
    for entry in entries:
        if not entry:
            continue
        vid = entry.get("id", "")
        dur = entry.get("duration") or 0
        if not vid or is_processed(config.history_file, vid):
            continue
        if dur and (dur < config.min_source_sec or dur > config.max_source_sec):
            continue
        return {
            "id": vid,
            "url": entry.get("url") or f"https://www.youtube.com/watch?v={vid}",
        }

    raise RuntimeError(f"No suitable unprocessed videos found for query: {search_query!r}")


def fetch_source_video(
    run_dir: Path,
    config: PipelineConfig,
    url: str | None = None,
    query: str | None = None,
    download_video: bool = True,
) -> SourceVideo:
    """Download a source video (optional for dry-run) and its English subtitles."""
    run_dir.mkdir(parents=True, exist_ok=True)
    candidate = pick_candidate_url(config, url=url, query=query)
    target_url = candidate["url"]

    base_opts = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": str(run_dir / "source.%(ext)s"),
    }

    with yt_dlp.YoutubeDL({**base_opts, "skip_download": True}) as ydl:
        info = ydl.extract_info(target_url, download=False)

    # Fetch English subtitles best-effort (YouTube may rate-limit subtitle endpoints with HTTP 429)
    sub_opts = {
        **base_opts,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-US", "en-GB"],
        "subtitlesformat": "vtt",
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(sub_opts) as ydl:
            ydl.download([target_url])
    except yt_dlp.utils.DownloadError as exc:
        print(f"      [warn] Subtitle download skipped ({exc}); continuing without captions.")

    if download_video:
        dl_opts = {
            **base_opts,
            "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
            "merge_output_format": "mp4",
        }
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            ydl.download([target_url])

    video_id = info["id"]
    video_path = run_dir / "source.mp4"
    if not video_path.exists():
        # Fallback if yt-dlp saved another extension
        mp4s = list(run_dir.glob("source.*"))
        media = [p for p in mp4s if p.suffix.lower() in {".mp4", ".mkv", ".webm"}]
        video_path = media[0] if media else None

    vtt_files = sorted(run_dir.glob("source*.vtt"))
    segments = parse_vtt(vtt_files[0]) if vtt_files else []

    return SourceVideo(
        video_id=video_id,
        title=info.get("title", "Untitled"),
        url=info.get("webpage_url", target_url),
        channel=info.get("uploader", "Unknown Creator"),
        duration=float(info.get("duration") or 0),
        video_path=video_path if download_video else None,
        segments=segments,
    )


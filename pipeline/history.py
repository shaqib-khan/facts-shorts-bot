"""Track processed source videos so daily runs never duplicate clips."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def load_history(path: Path) -> dict:
    """Load processed video history from JSON."""
    if not path.exists():
        return {"processed_ids": [], "clips": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"processed_ids": [], "clips": []}


def save_history(path: Path, data: dict) -> None:
    """Persist processed video history to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def is_processed(path: Path, video_id: str) -> bool:
    """Return True if a source video ID has already been clipped."""
    data = load_history(path)
    return video_id in set(data.get("processed_ids", []))


def mark_processed(path: Path, video_id: str, title: str, yt_video_id: str | None = None) -> None:
    """Record a processed source video and optional uploaded YouTube clip ID."""
    data = load_history(path)
    ids = data.setdefault("processed_ids", [])
    if video_id not in ids:
        ids.append(video_id)
    data.setdefault("clips", []).append(
        {
            "source_id": video_id,
            "source_title": title,
            "uploaded_id": yt_video_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    save_history(path, data)


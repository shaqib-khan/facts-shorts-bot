"""Configuration and Facts/Science/History topic presets."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DEFAULT_QUERIES: list[str] = [
    "amazing science facts explained",
    "mind blowing space discoveries documentary",
    "ancient history mysteries uncovered",
    "weird biology facts you didn't know",
    "physics paradoxes explained simply",
    "forgotten historical turning points",
    "deep ocean discoveries science",
]


@dataclass
class PipelineConfig:
    """Runtime configuration loaded from environment variables."""

    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", "").strip())
    llm_base_url: str = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").strip().rstrip("/")
    )
    llm_model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL", "llama-3.3-70b-versatile").strip()
    )
    clip_min_sec: int = field(default_factory=lambda: int(os.getenv("CLIP_MIN_SEC", "25")))
    clip_max_sec: int = field(default_factory=lambda: int(os.getenv("CLIP_MAX_SEC", "55")))
    min_source_sec: int = field(default_factory=lambda: int(os.getenv("MIN_SOURCE_SEC", "90")))
    max_source_sec: int = field(default_factory=lambda: int(os.getenv("MAX_SOURCE_SEC", "2700")))
    output_dir: Path = field(default_factory=lambda: Path(os.getenv("OUTPUT_DIR", "output")))
    yt_category_id: str = field(default_factory=lambda: os.getenv("YT_CATEGORY_ID", "28"))  # Science & Tech

    @property
    def history_file(self) -> Path:
        return self.output_dir / "history" / "processed.json"

    @property
    def runs_dir(self) -> Path:
        return self.output_dir / "runs"


"""CLI orchestrator: fetch video -> select highlight -> render 9:16 Short -> upload."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running directly via `python scripts/run_pipeline.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.captions import build_ass_subtitles
from pipeline.config import PipelineConfig
from pipeline.fetcher import fetch_source_video
from pipeline.highlights import select_highlight
from pipeline.history import mark_processed
from pipeline.renderer import render_vertical_clip
from pipeline.youtube_upload import upload_short


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-fetch, clip & upload Facts/Science/History Shorts.")
    parser.add_argument("--url", type=str, default=None, help="Specific YouTube video, playlist, or channel URL.")
    parser.add_argument("--query", type=str, default=None, help="YouTube search query (defaults to random preset).")
    parser.add_argument(
        "--crop-mode",
        choices=["blur", "fill"],
        default="blur",
        help="'blur' keeps 16:9 centered over blurred background; 'fill' crops full-bleed 9:16.",
    )
    parser.add_argument("--upload", action="store_true", help="Upload the rendered Short to YouTube.")
    parser.add_argument(
        "--privacy",
        choices=["private", "unlisted", "public"],
        default="private",
        help="YouTube privacy status when --upload is set.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch metadata + subtitles and plan highlight without downloading video or rendering.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = PipelineConfig()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = config.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Fetching source video (dry_run={args.dry_run})...")
    source = fetch_source_video(
        run_dir=run_dir,
        config=config,
        url=args.url or None,
        query=args.query or None,
        download_video=not args.dry_run,
    )
    print(f"      Selected: {source.title} ({source.video_id}, {len(source.segments)} caption segments)")

    print("[2/4] Selecting Facts/Science/History highlight...")
    plan = select_highlight(source, config)
    print(f"      Window: {plan.start_sec:.1f}s -> {plan.end_sec:.1f}s | Hook: {plan.hook}")
    print(f"      Title : {plan.yt_title}")

    ass_path = run_dir / "captions.ass"
    build_ass_subtitles(
        segments=source.segments,
        clip_start=plan.start_sec,
        clip_end=plan.end_sec,
        out_path=ass_path,
        hook_text=plan.hook,
    )

    plan_file = run_dir / "clip_plan.json"
    plan_file.write_text(
        json.dumps(
            {
                "source_id": source.video_id,
                "source_title": source.title,
                "source_url": source.url,
                "start_sec": plan.start_sec,
                "end_sec": plan.end_sec,
                "hook": plan.hook,
                "yt_title": plan.yt_title,
                "tags": plan.tags,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if args.dry_run:
        print(f"[DRY RUN] Saved captions & plan to {run_dir}")
        return 0

    if not source.video_path or not source.video_path.exists():
        raise RuntimeError("Source video file was not downloaded.")

    print(f"[3/4] Rendering 9:16 Short (crop_mode={args.crop_mode})...")
    output_mp4 = run_dir / "short_final.mp4"
    render_vertical_clip(
        source_video=source.video_path,
        ass_subtitles=ass_path,
        output_video=output_mp4,
        start_sec=plan.start_sec,
        end_sec=plan.end_sec,
        crop_mode=args.crop_mode,
    )
    print(f"      Rendered: {output_mp4}")

    uploaded_id = None
    if args.upload:
        print(f"[4/4] Uploading to YouTube (privacy={args.privacy})...")
        uploaded_id = upload_short(
            video_path=output_mp4,
            title=plan.yt_title,
            description=plan.yt_description,
            tags=plan.tags,
            category_id=config.yt_category_id,
            privacy_status=args.privacy,
        )
        print(f"      Uploaded! https://youtube.com/shorts/{uploaded_id}")
    else:
        print("[4/4] Skipping upload (pass --upload to publish to YouTube).")

    mark_processed(config.history_file, source.video_id, source.title, yt_video_id=uploaded_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


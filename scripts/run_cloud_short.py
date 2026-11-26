"""Cloud-safe Short generator CLI: Script -> Edge TTS -> AI Images -> FFmpeg -> YouTube."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.cloud_short import (
    fetch_scene_images,
    generate_cloud_plan,
    mark_cloud_topic,
    render_cloud_short,
    synthesize_voice,
)
from pipeline.config import PipelineConfig
from pipeline.youtube_upload import upload_short


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and upload a Facts/Science/History Short in the cloud.")
    parser.add_argument("--upload", action="store_true", help="Upload rendered Short to YouTube.")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default="public")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = PipelineConfig()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = config.runs_dir / f"cloud_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print("[1/4] Selecting Facts/Science/History script...")
    plan = generate_cloud_plan(config)
    print(f"      Topic: {plan.topic_id} | Title: {plan.title}")

    print("[2/4] Synthesizing Edge TTS voiceover...")
    voice_mp3 = run_dir / "voice.mp3"
    segments = synthesize_voice(plan.narration, voice_mp3)

    print(f"[3/4] Fetching {len(plan.scenes)} scene visuals & rendering 9:16 Short...")
    images = fetch_scene_images(plan.scenes, run_dir)
    output_mp4 = run_dir / "short_final.mp4"
    render_cloud_short(images, voice_mp3, segments, plan.hook, output_mp4)
    print(f"      Rendered: {output_mp4}")

    if args.upload:
        print(f"[4/4] Uploading to YouTube (privacy={args.privacy})...")
        yt_id = upload_short(
            video_path=output_mp4,
            title=plan.title,
            description=f"{plan.narration}\n\n#shorts #facts #science #history #didyouknow",
            tags=["shorts", "facts", "science", "history", "didyouknow"],
            category_id=config.yt_category_id,
            privacy_status=args.privacy,
        )
        print(f"      Uploaded! https://youtube.com/shorts/{yt_id}")
    else:
        print("[4/4] Skipping upload (pass --upload to publish).")

    mark_cloud_topic(config.history_file, plan.topic_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


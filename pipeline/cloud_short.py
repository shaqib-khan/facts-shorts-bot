"""Cloud-native Facts, Science & History Short generator (no YouTube download needed)."""

from __future__ import annotations

import asyncio
import json
import random
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import edge_tts
import httpx
from PIL import Image, ImageDraw

from pipeline.captions import build_ass_subtitles
from pipeline.config import PipelineConfig
from pipeline.fetcher import TranscriptSegment

BUILT_IN_TOPICS: list[dict] = [
    {
        "id": "venus_day_longer_than_year",
        "title": "A Day on Venus Is Longer Than Its Entire Year #shorts",
        "hook": "WAIT FOR THIS SPACE FACT",
        "narration": (
            "On Venus, a single day is actually longer than an entire year. "
            "Venus takes 243 Earth days to spin once on its axis, but only 225 Earth days to orbit the Sun. "
            "Even stranger, Venus spins backward compared to almost every other planet, "
            "meaning the Sun rises in the west and sets in the east."
        ),
        "scenes": [
            "cinematic planet Venus glowing golden clouds in deep space, vertical 9:16",
            "dramatic view of the Sun rising over alien rocky horizon on Venus, vertical",
            "solar system planetary orbit visualization glowing trails dark space, vertical",
            "retrograde spinning planet arrows glowing cosmic art, vertical",
        ],
    },
    {
        "id": "cleopatra_closer_to_iphone",
        "title": "Cleopatra Lived Closer to the iPhone Than the Pyramids #shorts",
        "hook": "THIS TIMELINE BREAKS BRAINS",
        "narration": (
            "Cleopatra lived closer in time to the invention of the iPhone than to the building of the Great Pyramid. "
            "The Great Pyramid of Giza was built around 2560 BC. "
            "Cleopatra ruled Egypt around 30 BC, more than two thousand five hundred years later. "
            "That means the pyramids were already ancient ruins to Cleopatra."
        ),
        "scenes": [
            "majestic Great Pyramid of Giza at sunset golden desert cinematic, vertical",
            "ancient Egyptian queen Cleopatra palace torchlight historical art, vertical",
            "glowing modern smartphone hologram over ancient desert sands, vertical",
            "ancient weathered stone hieroglyphs dramatic lighting, vertical",
        ],
    },
    {
        "id": "oxford_older_than_aztecs",
        "title": "Oxford University Is Older Than the Aztec Empire #shorts",
        "hook": "HISTORY TIMELINE SHOCK",
        "narration": (
            "Oxford University is hundreds of years older than the Aztec Empire. "
            "Teaching at Oxford began around the year 1096, and it grew rapidly by 1167. "
            "Meanwhile, the Aztec Empire wasn't founded until 1428 in central Mexico. "
            "By the time the Aztecs built their capital, Oxford had already been educating students for over three centuries."
        ),
        "scenes": [
            "historic Oxford University stone spires misty morning cinematic, vertical",
            "medieval scholars reading manuscripts by candlelight library, vertical",
            "ancient Aztec stone temple Tenochtitlan lush jungle sunlight, vertical",
            "grand ancient stone clock and hourglass historical timeline art, vertical",
        ],
    },
    {
        "id": "sharks_older_than_trees",
        "title": "Sharks Are Older Than Trees AND Saturn's Rings #shorts",
        "hook": "OLDER THAN TREES",
        "narration": (
            "Sharks have been swimming in Earth's oceans longer than trees have existed on land. "
            "Fossil evidence shows sharks appeared over 400 million years ago, while the first trees evolved around 350 million years ago. "
            "Even more mind-blowing, sharks are likely older than Saturn's iconic rings, which formed less than 100 million years ago."
        ),
        "scenes": [
            "ancient prehistoric shark swimming in deep blue ocean sunbeams, vertical",
            "lush prehistoric forest giant ferns misty dawn cinematic, vertical",
            "planet Saturn with glowing icy rings in deep space, vertical",
            "dramatic great white shark silhouette underwater rays of light, vertical",
        ],
    },
    {
        "id": "neutron_star_spoon",
        "title": "One Teaspoon of a Neutron Star Weighs 4 Billion Tons #shorts",
        "hook": "HEAVIEST MATTER IN SPACE",
        "narration": (
            "A single teaspoon of neutron star matter would weigh about four billion tons on Earth. "
            "When a massive star explodes in a supernova, its core collapses so tightly that protons and electrons crush into pure neutrons. "
            "An entire star heavier than our Sun gets squeezed into a sphere the size of a city."
        ),
        "scenes": [
            "glowing blue neutron star spinning in deep space pulsar beams, vertical",
            "massive colorful supernova explosion shockwave in cosmos, vertical",
            "tiny glowing ultra-dense sphere floating over a dark city skyline, vertical",
            "cosmic gravitational waves warping spacetime dark stars, vertical",
        ],
    },
    {
        "id": "bananas_radioactive",
        "title": "Why Bananas Are Naturally Radioactive #shorts",
        "hook": "SCIENTIFICALLY RADIOACTIVE",
        "narration": (
            "Bananas are slightly radioactive, and scientists actually use them as an informal unit of radiation. "
            "Every banana contains potassium, and a tiny fraction of it is potassium-40, a naturally radioactive isotope. "
            "Don't worry though—you would need to eat about ten million bananas at once to get radiation poisoning."
        ),
        "scenes": [
            "glowing yellow banana with subtle blue atomic energy aura dark background, vertical",
            "scientific laboratory Geiger counter glowing green screen, vertical",
            "3d glowing potassium atom orbitals physics visualization, vertical",
            "giant mountain of bright yellow bananas surreal cinematic lighting, vertical",
        ],
    },
]


@dataclass
class CloudShortPlan:
    """Generated script and scene prompts for a cloud Short."""

    topic_id: str
    title: str
    hook: str
    narration: str
    scenes: list[str]


def _load_used_topics(history_file: Path) -> set[str]:
    if not history_file.exists():
        return set()
    try:
        data = json.loads(history_file.read_text(encoding="utf-8"))
        return set(data.get("cloud_topics", []))
    except (json.JSONDecodeError, OSError):
        return set()


def mark_cloud_topic(history_file: Path, topic_id: str) -> None:
    """Record a generated cloud topic ID so it isn't repeated."""
    data: dict = {}
    if history_file.exists():
        try:
            data = json.loads(history_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    topics = data.setdefault("cloud_topics", [])
    if topic_id not in topics:
        topics.append(topic_id)
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def generate_cloud_plan(config: PipelineConfig) -> CloudShortPlan:
    """Generate a Facts/Science/History Short plan via LLM if configured, else built-in pool."""
    used = _load_used_topics(config.history_file)

    if config.llm_api_key:
        prompt = (
            "Write a viral 35-second YouTube Short script about a mind-blowing Science, History, or Space fact. "
            "Return ONLY valid JSON with keys: "
            '{"title": "<under 85 chars ending with #shorts>", '
            '"hook": "<3-5 word uppercase hook>", '
            '"narration": "<75-95 words plain spoken English, no emojis or brackets>", '
            '"scenes": ["<4 vivid vertical image prompts>"]}'
        )
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
                    "temperature": 0.7,
                },
                timeout=40.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                title = str(data["title"])[:95]
                if "#shorts" not in title.lower():
                    title = f"{title[:85]} #shorts"
                return CloudShortPlan(
                    topic_id=f"llm_{abs(hash(title)) % 1000000}",
                    title=title,
                    hook=str(data.get("hook", "MIND-BLOWING FACT")).upper()[:35],
                    narration=str(data["narration"]).strip(),
                    scenes=[str(s) for s in data.get("scenes", [])][:4] or BUILT_IN_TOPICS[0]["scenes"],
                )
        except Exception:
            pass

    available = [t for t in BUILT_IN_TOPICS if t["id"] not in used] or BUILT_IN_TOPICS
    chosen = random.choice(available)
    return CloudShortPlan(
        topic_id=chosen["id"],
        title=chosen["title"],
        hook=chosen["hook"],
        narration=chosen["narration"],
        scenes=chosen["scenes"],
    )


async def _tts_async(text: str, voice: str, out_mp3: Path) -> list[TranscriptSegment]:
    communicate = edge_tts.Communicate(text, voice)
    audio_chunks: list[bytes] = []
    word_events: list[tuple[float, float, str]] = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
        elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
            start = chunk["offset"] / 10_000_000.0
            dur = chunk["duration"] / 10_000_000.0
            word_events.append((start, start + max(0.08, dur), chunk["text"]))

    out_mp3.write_bytes(b"".join(audio_chunks))

    if word_events:
        return [TranscriptSegment(start=s, end=e, text=t) for s, e, t in word_events]

    # Fallback: estimate timing proportionally if boundary events weren't emitted
    words = text.split()
    total_dur = max(10.0, len(words) * 0.42)
    step = total_dur / max(1, len(words))
    return [
        TranscriptSegment(start=i * step, end=(i + 1) * step, text=w)
        for i, w in enumerate(words)
    ]


def synthesize_voice(text: str, out_mp3: Path, voice: str = "en-US-ChristopherNeural") -> list[TranscriptSegment]:
    """Synthesize Edge TTS MP3 and return timestamped segments."""
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    return asyncio.run(_tts_async(text, voice, out_mp3))


def _make_fallback_image(out_path: Path, idx: int) -> None:
    colors = [(14, 22, 48), (28, 16, 52), (12, 36, 44), (38, 18, 32)]
    img = Image.new("RGB", (768, 1360), colors[idx % len(colors)])
    draw = ImageDraw.Draw(img)
    for y in range(0, 1360, 8):
        shade = int(15 + (y / 1360) * 35)
        draw.line([(0, y), (768, y)], fill=(shade, shade + 10, shade + 35), width=8)
    img.save(out_path, format="JPEG", quality=90)


def fetch_scene_images(scenes: list[str], run_dir: Path) -> list[Path]:
    """Download vertical AI images via Pollinations.ai with local gradient fallback."""
    paths: list[Path] = []
    for idx, prompt in enumerate(scenes):
        out_img = run_dir / f"scene_{idx}.jpg"
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=768&height=1360&nologo=true"
        try:
            resp = httpx.get(url, timeout=45.0, follow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 5000:
                out_img.write_bytes(resp.content)
                paths.append(out_img)
                continue
        except Exception:
            pass
        _make_fallback_image(out_img, idx)
        paths.append(out_img)
    return paths


def _get_audio_duration(audio_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(res.stdout.strip())


def render_cloud_short(
    images: list[Path],
    audio_path: Path,
    segments: list[TranscriptSegment],
    hook: str,
    output_video: Path,
) -> Path:
    """Render 1080x1920 vertical Short from scene images, Edge TTS audio, and ASS captions."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is not installed on PATH.")

    duration = _get_audio_duration(audio_path) + 0.6
    ass_path = output_video.parent / "captions.ass"
    build_ass_subtitles(
        segments=segments,
        clip_start=0.0,
        clip_end=duration,
        out_path=ass_path,
        hook_text=hook,
        words_per_burst=3,
    )

    per_scene = duration / len(images)
    inputs: list[str] = []
    filters: list[str] = []
    for i, img in enumerate(images):
        inputs.extend(["-loop", "1", "-t", f"{per_scene:.2f}", "-i", str(img)])
        frames = max(30, int(per_scene * 30))
        filters.append(
            f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,zoompan=z='min(zoom+0.0008,1.12)':d={frames}:s=1080x1920:fps=30,setsar=1[v{i}]"
        )

    concat_inputs = "".join(f"[v{i}]" for i in range(len(images)))
    sub_escaped = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:")
    filters.append(f"{concat_inputs}concat=n={len(images)}:v=1:a=0,ass='{sub_escaped}'[vout]")

    audio_idx = len(images)
    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-i",
        str(audio_path),
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[vout]",
        "-map",
        f"{audio_idx}:a",
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
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_video),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg failed ({res.returncode}):\n{res.stderr[-1500:]}")
    return output_video


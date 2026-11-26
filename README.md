# Auto-Clip YouTube Shorts Pipeline (Facts, Science & History)

Automated pipeline that **fetches source videos**, **selects viral Facts/Science/History highlights**, **renders 9:16 vertical Shorts with word-burst captions**, and **uploads to YouTube**—locally or daily via **GitHub Actions**.

## Architecture

- `scripts/run_pipeline.py` — CLI orchestrator
- `pipeline/fetcher.py` — Searches or fetches videos + English WebVTT captions via `yt-dlp`
- `pipeline/highlights.py` — AI highlight & hook selector (Groq / OpenAI / Gemini / Ollama, with keyword fallback)
- `pipeline/captions.py` — 2–3 word burst `.ass` subtitle generator + top hook banner
- `pipeline/renderer.py` — FFmpeg 9:16 (`1080×1920`) renderer (`blur` or `fill` crop mode) + `loudnorm` audio
- `pipeline/youtube_upload.py` — YouTube Data API v3 uploader
- `pipeline/history.py` — Tracks processed video IDs so daily runs never repeat a video
- `.github/workflows/daily_clip.yml` — Daily `10:00 UTC` GitHub Actions autopilot

## Local Setup (Windows)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env

# Install FFmpeg (required for rendering):
winget install Gyan.FFmpeg
```

## Usage

```powershell
# 1. Dry run (fetch metadata + subtitles + AI highlight plan without downloading video):
python scripts/run_pipeline.py --dry-run

# 2. Fetch, clip & render locally (no upload):
python scripts/run_pipeline.py --query "mind blowing space discoveries"

# 3. Clip a specific video URL and upload as unlisted:
python scripts/run_pipeline.py --url "https://www.youtube.com/watch?v=..." --upload --privacy unlisted
```

## One-Time YouTube Upload Auth

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/) and enable **YouTube Data API v3**.
2. Create an **OAuth 2.0 Client ID** (Desktop App), download the JSON, and save it as `secrets/client_secret.json`.
3. Run:
   ```powershell
   python scripts/youtube_auth.py
   ```
4. Copy the printed `YT_CLIENT_ID`, `YT_CLIENT_SECRET_VALUE`, and `YT_REFRESH_TOKEN` into **GitHub Repo → Settings → Secrets and variables → Actions** (along with `LLM_API_KEY`).


"""Upload rendered Shorts to YouTube via YouTube Data API v3."""

from __future__ import annotations

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_credentials() -> Credentials:
    """Load OAuth credentials from env vars (CI) or secrets/youtube_token.json (local)."""
    client_id = os.getenv("YT_CLIENT_ID", "").strip()
    client_secret = os.getenv("YT_CLIENT_SECRET_VALUE", "").strip()
    refresh_token = os.getenv("YT_REFRESH_TOKEN", "").strip()

    if client_id and client_secret and refresh_token:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return creds

    token_path = Path("secrets/youtube_token.json")
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds

    raise RuntimeError(
        "Missing YouTube OAuth credentials. Run `python scripts/youtube_auth.py` locally "
        "or set YT_CLIENT_ID, YT_CLIENT_SECRET_VALUE, and YT_REFRESH_TOKEN."
    )


def upload_short(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    category_id: str = "28",
    privacy_status: str = "private",
) -> str:
    """Upload a video to YouTube and return the uploaded video ID."""
    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:15],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()

    return response["id"]


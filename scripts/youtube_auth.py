"""One-time YouTube OAuth setup. Saves secrets/youtube_token.json and prints GitHub Secrets."""

from __future__ import annotations

import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = Path("secrets/client_secret.json")
TOKEN_OUTPUT_FILE = Path("secrets/youtube_token.json")


def main() -> None:
    if not CLIENT_SECRET_FILE.exists():
        raise SystemExit(
            f"Missing {CLIENT_SECRET_FILE}. Download your Desktop App OAuth JSON from "
            "Google Cloud Console and save it there first."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    TOKEN_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_OUTPUT_FILE.write_text(creds.to_json(), encoding="utf-8")

    data = json.loads(creds.to_json())
    print(f"\nSaved token to {TOKEN_OUTPUT_FILE}\n")
    print("Add these to GitHub Repository -> Settings -> Secrets -> Actions:")
    print(f"  YT_CLIENT_ID           = {data.get('client_id')}")
    print(f"  YT_CLIENT_SECRET_VALUE = {data.get('client_secret')}")
    print(f"  YT_REFRESH_TOKEN       = {data.get('refresh_token')}")


if __name__ == "__main__":
    main()


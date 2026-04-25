"""One-time Google Calendar OAuth flow.

Run this once to generate data/secrets/gcal_token.json.
After that, the heartbeat will refresh the token automatically.

Prerequisites:
  1. Go to https://console.cloud.google.com/
  2. Create a project (or select one)
  3. Enable "Google Calendar API"
  4. Go to APIs & Services > Credentials > Create Credentials > OAuth client ID
  5. Application type: Desktop app
  6. Download the JSON file and save it as: data/secrets/gcal_credentials.json

Usage:
  .claude\\venv\\Scripts\\python.exe .claude\\scripts\\gcal_auth.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SECRETS_DIR = Path(__file__).parent.parent.parent / "data" / "secrets"
CREDENTIALS_PATH = SECRETS_DIR / "gcal_credentials.json"
TOKEN_PATH = SECRETS_DIR / "gcal_token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def main() -> None:
    if not CREDENTIALS_PATH.exists():
        print(f"""
ERROR: credentials file not found at:
  {CREDENTIALS_PATH}

Steps to create it:
  1. Go to https://console.cloud.google.com/
  2. Create or select a project
  3. Enable "Google Calendar API"
  4. APIs & Services > Credentials > Create Credentials > OAuth client ID
  5. Application type: Desktop app  (name: "Second Brain")
  6. Download JSON and save to:
     {CREDENTIALS_PATH}
  7. Re-run this script
""")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: google-auth-oauthlib not installed. Run:")
        print("  .claude\\venv\\Scripts\\pip.exe install google-auth-oauthlib")
        sys.exit(1)

    SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)

    TOKEN_PATH.write_text(creds.to_json())
    print(f"\nSuccess! Token saved to: {TOKEN_PATH}")
    print("The heartbeat will now pull your Google Calendar events.")

    # Quick test
    try:
        from googleapiclient.discovery import build
        service = build("calendar", "v3", credentials=creds)
        now = __import__("datetime").datetime.utcnow().isoformat() + "Z"
        events = service.events().list(
            calendarId="primary", timeMin=now,
            maxResults=3, singleEvents=True, orderBy="startTime"
        ).execute().get("items", [])
        print(f"\nTest pull: {len(events)} upcoming event(s) found on primary calendar.")
    except Exception as e:
        print(f"\nTest pull failed (auth succeeded, check API quota): {e}")


if __name__ == "__main__":
    main()

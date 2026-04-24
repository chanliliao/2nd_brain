"""
Google Calendar Integration
============================

Fetches upcoming and today's calendar events from Google Calendar via the
Calendar API v3. Shares an OAuth token with the Gmail integration - both use
the same token file at data/secrets/gmail_token.json.

IMPORTANT - Shared OAuth scopes:
  The SCOPES list below includes calendar.readonly in addition to the two Gmail
  scopes. If the user authenticated via gmail.py before calendar.readonly was
  added to those scopes, the stored token will be missing the calendar scope
  and every Calendar API call will return a 403. In that case delete the token
  file and re-run the Gmail auth flow so all three scopes are granted together.

Usage (CLI):
  python gcal.py upcoming            # next 24 hours (default)
  python gcal.py upcoming --hours 48 # next 48 hours
  python gcal.py today               # all events today
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import datetime
from datetime import timezone
import os

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOKEN_PATH = Path(__file__).parent.parent.parent / "data" / "secrets" / "gmail_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.readonly",
]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class GCalConfig:
    client_id: str
    client_secret: str
    token_path: Path = field(default_factory=lambda: TOKEN_PATH)

    @classmethod
    def from_env(cls) -> "GCalConfig":
        """Load config from environment variables.

        Reads GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET - intentionally the same
        variables as the Gmail integration because both share one OAuth app.

        Raises:
            ValueError: If either required variable is missing.
        """
        load_dotenv()
        client_id = os.getenv("GMAIL_CLIENT_ID")
        client_secret = os.getenv("GMAIL_CLIENT_SECRET")
        if not client_id:
            raise ValueError("GMAIL_CLIENT_ID environment variable is required")
        if not client_secret:
            raise ValueError("GMAIL_CLIENT_SECRET environment variable is required")
        return cls(client_id=client_id, client_secret=client_secret)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_service(config: GCalConfig):
    """Build and return an authenticated Calendar API v3 service.

    Reuses the Gmail OAuth token file.  The token must have been obtained with
    a scope list that includes calendar.readonly (see module docstring).

    Raises:
        RuntimeError: If the token file is missing (user must run gmail auth
                      first so the shared token is created).
    """
    token_path = config.token_path
    if not token_path.exists():
        raise RuntimeError(
            "Run gmail auth first - Calendar shares the Gmail OAuth token"
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Refresh the token if expired and a refresh token is available.
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Persist the refreshed token.
        token_path.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def _event_to_dict(event: dict) -> dict:
    """Normalise a raw Calendar API event into the standard dict format."""
    start_raw = event.get("start", {})
    end_raw = event.get("end", {})

    # All-day events use 'date'; timed events use 'dateTime'.
    start = start_raw.get("dateTime", start_raw.get("date", ""))
    end = end_raw.get("dateTime", end_raw.get("date", ""))

    return {
        "id": event.get("id", ""),
        "summary": event.get("summary", ""),
        "start": start,
        "end": end,
        "location": event.get("location", ""),
        "description": event.get("description", ""),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upcoming(config: GCalConfig, hours: int = 24) -> list[dict]:
    """Return events in the next *hours* hours (default 24).

    Args:
        config: Authenticated GCalConfig instance.
        hours:  Number of hours to look ahead.

    Returns:
        List of event dicts with keys: id, summary, start, end, location,
        description.
    """
    service = _get_service(config)

    now = datetime.datetime.now(timezone.utc).replace(tzinfo=None)
    time_min = now.isoformat() + "Z"
    time_max = (now + datetime.timedelta(hours=hours)).isoformat() + "Z"

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    return [_event_to_dict(e) for e in result.get("items", [])]


def today_events(config: GCalConfig) -> list[dict]:
    """Return all events for today (local midnight to local end-of-day).

    Returns:
        List of event dicts with keys: id, summary, start, end, location,
        description.
    """
    service = _get_service(config)

    now_local = datetime.datetime.now()
    start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now_local.replace(hour=23, minute=59, second=59, microsecond=0)

    # Convert local times to UTC ISO-8601 strings.
    utc_offset = datetime.datetime.now(timezone.utc).replace(tzinfo=None) - now_local
    time_min = (start_of_day + utc_offset).isoformat() + "Z"
    time_max = (end_of_day + utc_offset).isoformat() + "Z"

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    return [_event_to_dict(e) for e in result.get("items", [])]


def format_context(events: list[dict]) -> str:
    """Return a plain-text summary of *events* for LLM context injection.

    Format:

        CALENDAR (3 events):
        - 2026-04-23T09:00:00 - Standup [Room 3B]
        - 2026-04-23T14:00:00 - 1:1 with Manager
        - 2026-04-23T17:00:00 - Team retrospective [Zoom]

    The location bracket is omitted when the location field is empty.
    """
    n = len(events)
    lines = [f"CALENDAR ({n} events):"]
    for event in events:
        start = event.get("start", "")
        summary = event.get("summary", "")
        location = event.get("location", "")
        if location:
            lines.append(f"- {start} — {summary} [{location}]")
        else:
            lines.append(f"- {start} — {summary}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------

def cli_dispatch(args: list[str]) -> None:
    """Dispatch CLI sub-commands.

    Sub-commands:
        upcoming [--hours N]   Print events in the next N hours (default 24).
        today                  Print all events for today.
    """
    if not args:
        _print_usage()
        return

    command = args[0]

    if command == "upcoming":
        hours = 24
        # Parse optional --hours N
        remaining = args[1:]
        i = 0
        while i < len(remaining):
            if remaining[i] == "--hours" and i + 1 < len(remaining):
                try:
                    hours = int(remaining[i + 1])
                except ValueError:
                    print(f"Invalid value for --hours: {remaining[i + 1]}")
                    return
                i += 2
            else:
                i += 1

        config = GCalConfig.from_env()
        events = upcoming(config, hours=hours)
        print(format_context(events))

    elif command == "today":
        config = GCalConfig.from_env()
        events = today_events(config)
        print(format_context(events))

    else:
        _print_usage()


def _print_usage() -> None:
    print("Usage: gcal.py <command> [options]")
    print()
    print("Commands:")
    print("  upcoming [--hours N]   Show events in the next N hours (default 24)")
    print("  today                  Show all events for today")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    cli_dispatch(sys.argv[1:])

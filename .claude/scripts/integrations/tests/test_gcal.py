"""
Tests for the Google Calendar integration (gcal.py).

All tests mock the Calendar API service — no real API calls are made.
"""

import datetime
from datetime import timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

import sys, os
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))  # .claude/scripts

from integrations.gcal import (
    GCalConfig,
    format_context,
    upcoming,
    today_events,
    _event_to_dict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(tmp_path: Path) -> GCalConfig:
    """Return a GCalConfig pointing at a fake token file."""
    token_file = tmp_path / "gcal_token.json"
    # Write a minimal token so the file exists (content is mocked away).
    token_file.write_text('{"token": "fake"}')
    return GCalConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        token_path=token_file,
    )


def _make_event(
    summary: str = "Test Event",
    start: str = "2026-04-23T09:00:00Z",
    end: str = "2026-04-23T10:00:00Z",
    location: str = "",
    description: str = "",
    event_id: str = "evt123",
) -> dict:
    """Return a minimal Calendar API event dict."""
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        "location": location,
        "description": description,
    }


# ---------------------------------------------------------------------------
# format_context tests
# ---------------------------------------------------------------------------

class TestFormatContext:
    def test_format_context_empty(self):
        """Empty event list returns a graceful header string, not an error."""
        result = format_context([])
        assert "CALENDAR (0 events)" in result
        # Should not raise and should be a non-empty string
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_context_with_location(self):
        """Event with a location includes the bracket notation."""
        events = [
            {
                "id": "1",
                "summary": "Standup",
                "start": "2026-04-23T09:00:00Z",
                "end": "2026-04-23T09:30:00Z",
                "location": "Room 3B",
                "description": "",
            }
        ]
        result = format_context(events)
        assert "Standup" in result
        assert "[Room 3B]" in result
        assert "CALENDAR (1 events)" in result

    def test_format_context_no_location(self):
        """Event without a location omits the bracket part entirely."""
        events = [
            {
                "id": "2",
                "summary": "Planning",
                "start": "2026-04-23T14:00:00Z",
                "end": "2026-04-23T15:00:00Z",
                "location": "",
                "description": "",
            }
        ]
        result = format_context(events)
        assert "Planning" in result
        assert "[" not in result
        assert "]" not in result


# ---------------------------------------------------------------------------
# upcoming() tests
# ---------------------------------------------------------------------------

class TestUpcoming:
    @patch("integrations.gcal.Credentials.from_authorized_user_file")
    @patch("integrations.gcal.build")
    def test_upcoming_uses_correct_time_range(
        self, mock_build, mock_creds_from_file, tmp_path
    ):
        """upcoming() passes timeMin=now and timeMax=now+hours to the API."""
        # Set up mock credentials (include calendar.readonly scope)
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
        mock_creds_from_file.return_value = mock_creds

        # Set up mock service
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events_resource = MagicMock()
        mock_service.events.return_value = mock_events_resource

        mock_list = MagicMock()
        mock_events_resource.list.return_value = mock_list
        mock_list.execute.return_value = {"items": []}

        config = _make_config(tmp_path)
        hours = 24

        # Record the time just before calling upcoming()
        before = datetime.datetime.now(timezone.utc).replace(tzinfo=None)
        upcoming(config, hours=hours)
        after = datetime.datetime.now(timezone.utc).replace(tzinfo=None)

        # Verify the API was called
        assert mock_events_resource.list.called

        call_kwargs = mock_events_resource.list.call_args.kwargs
        assert call_kwargs["calendarId"] == "primary"
        assert call_kwargs["singleEvents"] is True
        assert call_kwargs["orderBy"] == "startTime"

        # Parse the ISO strings passed to the API
        time_min_str = call_kwargs["timeMin"]
        time_max_str = call_kwargs["timeMax"]
        assert time_min_str.endswith("Z")
        assert time_max_str.endswith("Z")

        time_min = datetime.datetime.fromisoformat(time_min_str.rstrip("Z"))
        time_max = datetime.datetime.fromisoformat(time_max_str.rstrip("Z"))

        # timeMin should be approximately now
        assert before <= time_min <= after

        # timeMax should be approximately now + hours
        expected_max_low = before + datetime.timedelta(hours=hours)
        expected_max_high = after + datetime.timedelta(hours=hours)
        assert expected_max_low <= time_max <= expected_max_high

        # The window should be exactly `hours` hours wide
        delta = time_max - time_min
        assert abs(delta.total_seconds() - hours * 3600) < 2  # within 2 seconds


# ---------------------------------------------------------------------------
# today_events() tests
# ---------------------------------------------------------------------------

class TestTodayEvents:
    @patch("integrations.gcal.Credentials.from_authorized_user_file")
    @patch("integrations.gcal.build")
    def test_today_events_covers_full_day(
        self, mock_build, mock_creds_from_file, tmp_path
    ):
        """today_events() passes timeMin=start of today and timeMax=end of today."""
        # Set up mock credentials (include calendar.readonly scope)
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
        mock_creds_from_file.return_value = mock_creds

        # Set up mock service
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events_resource = MagicMock()
        mock_service.events.return_value = mock_events_resource

        mock_list = MagicMock()
        mock_events_resource.list.return_value = mock_list
        mock_list.execute.return_value = {"items": []}

        config = _make_config(tmp_path)
        today_events(config)

        assert mock_events_resource.list.called

        call_kwargs = mock_events_resource.list.call_args.kwargs
        time_min_str = call_kwargs["timeMin"]
        time_max_str = call_kwargs["timeMax"]

        assert time_min_str.endswith("Z")
        assert time_max_str.endswith("Z")

        time_min = datetime.datetime.fromisoformat(time_min_str.rstrip("Z"))
        time_max = datetime.datetime.fromisoformat(time_max_str.rstrip("Z"))

        # Convert UTC back to local for comparison (DST-safe)
        local_aware = datetime.datetime.now(datetime.timezone.utc).astimezone()
        utc_delta = local_aware.utcoffset()
        local_min = time_min + utc_delta
        local_max = time_max + utc_delta

        # local_min should be midnight (00:00:00) today
        today = datetime.datetime.now().date()
        expected_start = datetime.datetime(today.year, today.month, today.day, 0, 0, 0)
        expected_end = datetime.datetime(today.year, today.month, today.day, 23, 59, 59)

        assert abs((local_min - expected_start).total_seconds()) < 2
        assert abs((local_max - expected_end).total_seconds()) < 2

        # The window should span approximately 24 hours
        delta = time_max - time_min
        # 23h 59m 59s = 86399 seconds
        assert 86390 <= delta.total_seconds() <= 86410

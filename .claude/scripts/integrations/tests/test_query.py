"""Tests for query.py — unified CLI dispatcher."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # .claude/scripts

from integrations.query import main


def test_gmail_routes_to_gmail_dispatch():
    """Verify that 'gmail' command routes to gmail.cli_dispatch."""
    with patch("integrations.gmail.cli_dispatch") as mock_dispatch:
        main(["gmail", "unread"])
        mock_dispatch.assert_called_once_with(["unread"])


def test_calendar_routes_to_gcal_dispatch():
    """Verify that 'calendar' maps to gcal registry entry."""
    with patch("integrations.gcal.cli_dispatch") as mock_dispatch:
        main(["calendar", "today"])
        mock_dispatch.assert_called_once_with(["today"])


def test_github_routes_to_github_dispatch():
    """Verify that 'github' command routes to github.cli_dispatch."""
    with patch("integrations.github.cli_dispatch") as mock_dispatch:
        main(["github", "prs"])
        mock_dispatch.assert_called_once_with(["prs"])


def test_unknown_integration_exits_1(capsys):
    """Verify that unknown integration name exits with code 1."""
    with pytest.raises(SystemExit) as exc_info:
        main(["unknown"])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Error: Unknown integration 'unknown'" in captured.err


def test_dispatch_exception_prints_error_and_exits_1(capsys):
    """Verify that an exception from cli_dispatch is caught and exits with code 1."""
    with patch("integrations.gmail.cli_dispatch", side_effect=RuntimeError("auth failed")):
        with pytest.raises(SystemExit) as exc_info:
            main(["gmail", "unread"])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "auth failed" in captured.err


def test_debug_flag_reraises_exception():
    """Verify that --debug causes exceptions to propagate instead of exit 1."""
    with patch("integrations.gmail.cli_dispatch", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            main(["gmail", "--debug", "unread"])


def test_no_args_prints_usage(capsys):
    """Verify that no args prints usage without crashing."""
    main([])
    captured = capsys.readouterr()
    assert "Usage:" in captured.out
    assert "Registered integrations:" in captured.out


def test_help_command_prints_usage(capsys):
    """Verify that 'help' command prints usage."""
    main(["help"])
    captured = capsys.readouterr()
    assert "Usage:" in captured.out
    assert "Registered integrations:" in captured.out


def test_multiple_args_passed_through():
    """Verify that multiple args are passed to cli_dispatch."""
    with patch("integrations.gmail.cli_dispatch") as mock_dispatch:
        main(["gmail", "thread", "abc123"])
        mock_dispatch.assert_called_once_with(["thread", "abc123"])


def test_dispatch_with_flags():
    """Verify that flags are passed through correctly."""
    with patch("integrations.gmail.cli_dispatch") as mock_dispatch:
        main(["gmail", "unread", "--since", "2026-04-20"])
        mock_dispatch.assert_called_once_with(["unread", "--since", "2026-04-20"])


def test_calendar_upcoming_with_hours():
    """Verify calendar integration with flags."""
    with patch("integrations.gcal.cli_dispatch") as mock_dispatch:
        main(["calendar", "upcoming", "--hours", "48"])
        mock_dispatch.assert_called_once_with(["upcoming", "--hours", "48"])

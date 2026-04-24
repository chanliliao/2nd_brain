"""Tests for gmail.py — mocked, no real API calls."""
import base64
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # .claude/scripts

from integrations.gmail import (
    format_context,
    needs_reply,
    list_unread,
    get_thread,
    _decode_body,
)


# --- needs_reply ---

def test_needs_reply_question_mark_in_snippet():
    assert needs_reply({"snippet": "Can you send me the file?", "subject": ""}) is True


def test_needs_reply_question_mark_in_subject():
    assert needs_reply({"snippet": "please see below", "subject": "Can we meet?"}) is True


def test_needs_reply_no_question():
    assert needs_reply({"snippet": "Thanks, talk soon.", "subject": "Re: Project"}) is False


def test_needs_reply_empty():
    assert needs_reply({}) is False


# --- format_context ---

def test_format_context_empty():
    result = format_context([])
    assert "UNREAD GMAIL (0 threads)" in result


def test_format_context_single_thread():
    threads = [{
        "id": "abc123",
        "subject": "Job opportunity",
        "from": "recruiter@acme.com",
        "date": "Thu, 23 Apr 2026",
        "snippet": "We have a role for you",
        "needs_reply": False,
    }]
    result = format_context(threads)
    assert "UNREAD GMAIL (1 threads)" in result
    assert "Job opportunity" in result
    assert "recruiter@acme.com" in result
    assert "We have a role for you" in result


def test_format_context_needs_reply_flag():
    threads = [{
        "id": "x1",
        "subject": "Interview?",
        "from": "hr@corp.com",
        "date": "Today",
        "snippet": "Are you available?",
        "needs_reply": True,
    }]
    result = format_context(threads)
    assert "NEEDS REPLY" in result


# --- list_unread (mocked service) ---

def _make_mock_service(messages, msg_detail):
    """Build a mock Gmail service that returns given messages list and detail."""
    svc = MagicMock()
    users = svc.users.return_value
    msgs = users.messages.return_value

    list_exec = MagicMock()
    list_exec.execute.return_value = {"messages": messages}
    msgs.list.return_value = list_exec

    get_exec = MagicMock()
    get_exec.execute.return_value = msg_detail
    msgs.get.return_value = get_exec

    return svc


def test_list_unread_builds_correct_query():
    """Verify is:unread in:inbox is in the query string."""
    fake_msg = {
        "id": "m1",
        "snippet": "hello",
        "payload": {"headers": [
            {"name": "Subject", "value": "Test"},
            {"name": "From", "value": "a@b.com"},
            {"name": "Date", "value": "Mon"},
        ]},
    }
    svc = _make_mock_service([{"id": "m1"}], fake_msg)

    from integrations.gmail import GmailConfig
    config = GmailConfig(client_id="x", client_secret="y")

    with patch("integrations.gmail._get_service", return_value=svc):
        results = list_unread(config)

    call_kwargs = svc.users().messages().list.call_args
    query_used = call_kwargs[1]["q"]
    assert "is:unread" in query_used
    assert "in:inbox" in query_used
    assert len(results) == 1
    assert results[0]["subject"] == "Test"


def test_list_unread_with_since():
    """Verify after:YYYY/MM/DD is appended when since is passed."""
    svc = _make_mock_service([], {})
    from integrations.gmail import GmailConfig
    config = GmailConfig(client_id="x", client_secret="y")

    with patch("integrations.gmail._get_service", return_value=svc):
        list_unread(config, since="2026-04-01")

    call_kwargs = svc.users().messages().list.call_args
    assert "after:2026/04/01" in call_kwargs[1]["q"]


# --- get_thread (mocked service) ---

def test_get_thread_decodes_base64():
    """Verify base64url-encoded body is decoded to plain text."""
    body_text = "Hello from the thread body!"
    encoded = base64.urlsafe_b64encode(body_text.encode()).decode()

    fake_thread = {
        "messages": [{
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "Subject", "value": "Hi"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Date", "value": "Tue"},
                ],
                "body": {"data": encoded},
                "parts": [],
            },
            "snippet": "Hello from",
        }]
    }

    svc = MagicMock()
    svc.users().threads().get().execute.return_value = fake_thread

    from integrations.gmail import GmailConfig
    config = GmailConfig(client_id="x", client_secret="y")

    with patch("integrations.gmail._get_service", return_value=svc):
        result = get_thread(config, "thread123")

    assert result["id"] == "thread123"
    assert len(result["messages"]) == 1
    assert body_text in result["messages"][0]["body"]

"""Snapshot builder and differ for heartbeat idempotency.

build_snapshot() captures current integration state as a hashable dict.
diff_snapshot() returns only what changed since the last run.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT_FALLBACK = Path(__file__).parent.parent
STATE_PATH = _PROJECT_ROOT_FALLBACK / "data" / "state" / "heartbeat-state.json"


def build_snapshot(
    gmail_threads: list[dict],
    github_prs: list[dict],
    calendar_events: list[dict],
) -> dict:
    """Return a JSON-serialisable snapshot of current integration state."""
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "gmail": {
            t["id"]: t.get("needs_reply", False)
            for t in gmail_threads
            if "id" in t
        },
        "github": {
            f"{pr['repo']}#{pr['number']}": pr.get("title", "")
            for pr in github_prs
            if "repo" in pr and "number" in pr
        },
        "calendar": [
            e.get("id", e.get("summary", ""))
            for e in calendar_events
            if "error" not in e
        ],
    }


def load_state(state_path: Path = STATE_PATH) -> dict:
    """Load previous snapshot from disk. Returns {} on missing/corrupt file."""
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(snapshot: dict, state_path: Path = STATE_PATH) -> None:
    """Persist snapshot to disk, creating parent dirs as needed."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


def diff_snapshot(old: dict, new: dict) -> dict:
    """Return a dict describing what changed between old and new snapshots.

    Returns empty dict if nothing notable changed (safe to skip notification).
    Returns {"first_run": True} on the very first run (no prior state).
    """
    if not old:
        return {"first_run": True}

    changes: dict = {}

    # Gmail: new thread IDs or threads that flipped to needs_reply=True
    old_gmail: dict = old.get("gmail", {})
    new_gmail: dict = new.get("gmail", {})
    new_thread_ids = [tid for tid in new_gmail if tid not in old_gmail]
    newly_needs_reply = [
        tid
        for tid, needs in new_gmail.items()
        if needs and not old_gmail.get(tid)
    ]
    if new_thread_ids or newly_needs_reply:
        changes["gmail"] = {
            "new_threads": new_thread_ids,
            "newly_needs_reply": newly_needs_reply,
        }

    # GitHub: new PR keys
    old_prs: dict = old.get("github", {})
    new_prs: dict = new.get("github", {})
    new_pr_keys = [k for k in new_prs if k not in old_prs]
    if new_pr_keys:
        changes["github"] = {"new_prs": new_pr_keys}

    # Calendar: new event IDs/summaries
    old_cal = set(old.get("calendar", []))
    new_cal = set(new.get("calendar", []))
    new_events = list(new_cal - old_cal)
    if new_events:
        changes["calendar"] = {"new_events": new_events}

    return changes

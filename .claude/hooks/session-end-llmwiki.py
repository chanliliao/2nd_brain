#!/usr/bin/env python3
"""SessionEnd hook: persist today's session summary as an llmwiki page."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from hooks.shared import get_today_daily_path  # type: ignore


def _extract_session_summary(daily_path: Path) -> str | None:
    """Return the content under '## Session Summary' in the daily log, or None."""
    try:
        text = daily_path.read_text(encoding="utf-8")
    except OSError:
        return None

    marker = "\n## Session Summary\n"
    start = text.find(marker)
    if start == -1:
        # Try at file start
        if text.startswith("## Session Summary\n"):
            start = 0
            content_start = len("## Session Summary\n")
        else:
            return None
    else:
        content_start = start + len(marker)

    # Everything until the next ## heading (or EOF)
    rest = text[content_start:]
    end = rest.find("\n## ")
    if end != -1:
        rest = rest[:end]
    return rest.strip() or None


def _wiki_page_content(summary: str, today: date) -> str:
    date_str = today.isoformat()
    return (
        f"---\n"
        f"title: Session {date_str}\n"
        f"created: {date_str}\n"
        f"updated: {date_str}\n"
        f"tags: [session, daily]\n"
        f"---\n\n"
        f"{summary}\n"
    )


def main() -> None:
    # Consume stdin (hook metadata) — we don't need it
    try:
        sys.stdin.read()
    except Exception:
        pass

    today = date.today()
    date_str = today.isoformat()
    daily_path = get_today_daily_path()

    summary = _extract_session_summary(daily_path)
    if not summary:
        sys.exit(0)

    page_path = f"sessions/{date_str}.md"
    content = _wiki_page_content(summary, today)

    # llmwiki write reads from stdin (shell=True needed on Windows for .cmd wrapper)
    result = subprocess.run(
        f'llmwiki write "{page_path}"',
        input=content,
        text=True,
        capture_output=True,
        shell=True,
    )
    if result.returncode != 0:
        print(f"[llmwiki] write failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(0)  # Non-blocking: don't fail the session

    # Add to index
    short_summary = summary.split("\n")[0][:80]
    subprocess.run(
        f'llmwiki index add "{page_path}" "Session {date_str}: {short_summary}"',
        capture_output=True,
        shell=True,
    )

    # Append to activity log
    subprocess.run(
        f'llmwiki log append session "Session summary written: {date_str}"',
        capture_output=True,
        shell=True,
    )


if __name__ == "__main__":
    main()

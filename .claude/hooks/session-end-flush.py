#!/usr/bin/env python3
"""SessionEnd hook: write session summary to daily log."""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from hooks.shared import (
    extract_facts_with_haiku,
    append_to_daily_log,
    find_session_jsonl,
    truncate_to_tokens,
    get_today_daily_path,
)

SUMMARY_PROMPT = """From this Claude Code session transcript, write a concise session summary covering ALL of:
- What was worked on (project name, feature, or task)
- Key decisions or approaches chosen
- Files created or modified (list them)
- What was completed vs what's still in progress
- Any blockers or open questions
- NEW PROJECTS or ideas discussed (e.g. "Discussed building X", "Initiated Y project")
- Things Henry asked Claude to create, initiate, or set up
- Goals or intentions Henry stated about future work
- People, tools, or services mentioned as important

Write in first person past tense (Henry's perspective). Max 300 words. Be specific — capture project names, tool names, and intent even if not yet implemented."""

MAX_TRANSCRIPT_CHARS = 15000


def read_transcript(path: Path) -> str:
    """Read and concatenate messages from a JSONL session file, including tool results."""
    lines = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # Actual Claude Code JSONL format: role/content nested in entry["message"]
            msg = entry.get("message")
            if isinstance(msg, dict):
                role = msg.get("role", "")
                if role in ("assistant", "user"):
                    content = msg.get("content", "")
                    if isinstance(content, str) and content.strip():
                        lines.append(f"[{role}]: {content[:500]}")
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = block.get("text", "")
                                if text.strip():
                                    lines.append(f"[{role}]: {text[:500]}")
                continue

            # Fallback: flat format (role at top level)
            role = entry.get("role", "")
            entry_type = entry.get("type", "")
            if role in ("assistant", "user"):
                content = entry.get("content", "")
                if isinstance(content, str):
                    lines.append(f"[{role}]: {content[:500]}")
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            lines.append(f"[{role}]: {block.get('text', '')[:500]}")
            elif role == "tool" or entry_type == "tool_result":
                content = entry.get("content", "")
                if isinstance(content, str) and len(content) < 200:
                    lines.append(f"[tool_result]: {content[:200]}")

    except (OSError, UnicodeDecodeError):
        return ""
    return "\n".join(lines)


def already_has_session_summary() -> bool:
    """Return True if today's daily log already contains a claude session header."""
    daily_path = get_today_daily_path()
    if not daily_path.exists():
        return False
    try:
        existing = daily_path.read_text(encoding="utf-8")
    except OSError:
        return False
    today = datetime.date.today().isoformat()
    marker = f"## {today}-claude"
    return marker in existing


def main() -> None:
    # Read hook input from stdin (Claude Code passes JSON metadata)
    transcript_path: Path | None = None
    try:
        hook_input = json.loads(sys.stdin.read())
        raw_path = hook_input.get("transcript_path")
        if raw_path:
            transcript_path = Path(raw_path)
    except (json.JSONDecodeError, ValueError):
        pass

    # Fall back to find_session_jsonl() if no path in hook input
    if transcript_path is None or not transcript_path.exists():
        transcript_path = find_session_jsonl()

    if transcript_path is None or not transcript_path.exists():
        return  # Nothing to summarise, exit silently

    # Deduplicate: skip if a Session Summary section already exists
    if already_has_session_summary():
        return

    transcript_text = read_transcript(transcript_path)
    if not transcript_text.strip():
        return

    transcript_text = truncate_to_tokens(transcript_text, max_chars=MAX_TRANSCRIPT_CHARS)
    summary = extract_facts_with_haiku(transcript_text, SUMMARY_PROMPT)

    if summary.strip():
        today = datetime.date.today().isoformat()
        append_to_daily_log(summary, section_header=f"## {today}-claude")


if __name__ == "__main__":
    main()

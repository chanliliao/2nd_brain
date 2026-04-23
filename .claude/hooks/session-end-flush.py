#!/usr/bin/env python3
"""SessionEnd hook: write session summary to daily log."""
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

SUMMARY_PROMPT = """From this Claude Code session transcript, write a concise session summary:
- What was worked on (project name, feature, or task)
- Key decisions or approaches chosen
- Files created or modified (list them)
- What was completed vs what's still in progress
- Any blockers or open questions

Write in first person past tense (Henry's perspective). Max 200 words. Be specific."""

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

            role = entry.get("role", "")
            entry_type = entry.get("type", "")

            # Extract text from assistant and user messages
            if role in ("assistant", "user"):
                content = entry.get("content", "")
                if isinstance(content, str):
                    lines.append(f"[{role}]: {content[:500]}")
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            lines.append(f"[{role}]: {block.get('text', '')[:500]}")

            # Extract short tool result entries for context about what was done
            elif role == "tool" or entry_type == "tool_result":
                content = entry.get("content", "")
                if isinstance(content, str) and len(content) < 200:
                    lines.append(f"[tool_result]: {content[:200]}")

    except (OSError, UnicodeDecodeError):
        return ""
    return "\n".join(lines)


def already_has_session_summary() -> bool:
    """Return True if today's daily log already contains a Session Summary section."""
    daily_path = get_today_daily_path()
    if not daily_path.exists():
        return False
    try:
        existing = daily_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return (
        "\n## Session Summary\n" in existing
        or existing.startswith("## Session Summary\n")
    )


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
        append_to_daily_log(summary, section_header="## Session Summary")


if __name__ == "__main__":
    main()

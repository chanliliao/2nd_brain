#!/usr/bin/env python3
"""PreCompact hook: extract facts from transcript before context is compressed."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from hooks.shared import (
    extract_facts_with_haiku,
    append_to_daily_log,
    find_session_jsonl,
    truncate_to_tokens,
)

EXTRACTION_PROMPT = """From this Claude Code session transcript, extract:
- Key decisions made (architecture, approach, tool choices)
- Problems solved and how they were solved
- Files created or significantly modified
- Important facts learned
- Blockers encountered

Format as a concise bullet list. Omit small talk and routine tool calls. Max 300 words."""

MAX_TRANSCRIPT_CHARS = 12000  # feed at most 12k chars to Haiku


def read_transcript(path: Path) -> str:
    """Read and concatenate assistant messages from a JSONL session file."""
    lines = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            # Extract text from assistant and user messages
            role = entry.get("role", "")
            if role not in ("assistant", "user"):
                continue
            content = entry.get("content", "")
            if isinstance(content, str):
                lines.append(f"[{role}]: {content[:500]}")
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        lines.append(f"[{role}]: {block.get('text', '')[:500]}")
    except (OSError, UnicodeDecodeError):
        return ""
    return "\n".join(lines)


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
        return  # Nothing to extract, exit silently

    transcript_text = read_transcript(transcript_path)
    if not transcript_text.strip():
        return

    transcript_text = truncate_to_tokens(transcript_text, max_chars=MAX_TRANSCRIPT_CHARS)
    facts = extract_facts_with_haiku(transcript_text, EXTRACTION_PROMPT)

    if facts.strip():
        append_to_daily_log(facts, section_header="## Pre-Compact Extraction")


if __name__ == "__main__":
    main()

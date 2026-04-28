"""
SessionStart hook — injects vault context into every new Claude Code session.

Claude Code reads stdout from this script and prepends it to the session context.
Exit 0 always so a vault-missing or read error never blocks the session.
"""

import sys
from pathlib import Path

# Make shared.py importable: add the .claude/ directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))
from hooks.shared import get_vault_path, get_recent_daily_logs, truncate_to_tokens

MAX_TOTAL_CHARS = 8000
MEMORY_MAX_CHARS = 3000
DAILY_MAX_CHARS = 800
LESSONS_MAX_CHARS = 1500
LESSONS_COUNT = 5


def read_vault_file(vault: Path, filename: str) -> str:
    """Read a vault file, returning '[not found]' if it doesn't exist."""
    p = vault / filename
    try:
        return p.read_text(encoding="utf-8").strip()
    except (OSError, FileNotFoundError):
        return "[not found]"


def build_recent_activity(n: int) -> str:
    """Build the recent_activity section from the last n daily logs."""
    logs = get_recent_daily_logs(n)
    if not logs:
        return ""
    parts = []
    for date, content in logs:
        truncated = truncate_to_tokens(content, max_chars=DAILY_MAX_CHARS)
        parts.append(f"### {date}\n{truncated}")
    return "\n\n".join(parts)


def build_lessons(vault: Path) -> str:
    """Read the 5 most recent approved mistake files and return a condensed block."""
    debugging_dir = vault / "Memory" / "debugging"
    if not debugging_dir.exists():
        return ""
    files = sorted(debugging_dir.glob("*_mistake_*.md"), reverse=True)[:LESSONS_COUNT]
    if not files:
        return ""
    parts = []
    total = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8").strip()
            # Strip YAML frontmatter if present
            if text.startswith("---"):
                end = text.find("---", 3)
                if end != -1:
                    text = text[end + 3:].strip()
            if text and total + len(text) <= LESSONS_MAX_CHARS:
                parts.append(f"- {text}")
                total += len(text)
        except OSError:
            continue
    return "\n".join(parts)


def assemble_block(soul: str, user: str, memory: str, activity: str, lessons: str) -> str:
    lines = [
        "<memory>",
        "<identity>",
        soul,
        "</identity>",
        "",
        "<profile>",
        user,
        "</profile>",
        "",
        "<facts>",
        memory,
        "</facts>",
        "",
        "<recent_activity>",
        activity,
        "</recent_activity>",
    ]
    if lessons:
        lines += [
            "",
            "<lessons>",
            lessons,
            "</lessons>",
        ]
    lines.append("</memory>")
    return "\n".join(lines)


def main() -> None:
    # If the vault is missing, exit silently — never block a session.
    try:
        vault = get_vault_path()
    except Exception:
        return

    soul = read_vault_file(vault, "SOUL.md")
    user = read_vault_file(vault, "USER.md")

    memory_raw = read_vault_file(vault, "MEMORY.md")
    if memory_raw == "[not found]":
        memory = "[not found]"
    else:
        memory = truncate_to_tokens(memory_raw, max_chars=MEMORY_MAX_CHARS)

    lessons = build_lessons(vault)

    # First attempt: 3 recent daily logs
    activity = build_recent_activity(3)
    block = assemble_block(soul, user, memory, activity, lessons)

    # Budget enforcement: trim recent_activity first, then facts
    if len(block) > MAX_TOTAL_CHARS:
        activity = build_recent_activity(1)
        block = assemble_block(soul, user, memory, activity, lessons)

    if len(block) > MAX_TOTAL_CHARS:
        # Further trim facts to recover remaining headroom
        overhead = len(block) - MAX_TOTAL_CHARS
        new_facts_len = max(200, MEMORY_MAX_CHARS - overhead)
        memory = truncate_to_tokens(memory_raw if memory_raw != "[not found]" else "[not found]",
                                    max_chars=new_facts_len)
        block = assemble_block(soul, user, memory, activity, lessons)

    print(block)


if __name__ == "__main__":
    main()

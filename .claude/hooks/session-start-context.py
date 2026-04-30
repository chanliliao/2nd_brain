"""
SessionStart hook — injects vault context into every new Claude Code session.

Claude Code reads stdout from this script and prepends it to the session context.
Exit 0 always so a vault-missing or read error never blocks the session.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from hooks.shared import get_vault_path, get_recent_daily_logs, truncate_to_tokens

MAX_TOTAL_CHARS = 8000
DAILY_MAX_CHARS = 800
RULES_MAX_CHARS = 3000
PROJECTS_MAX_CHARS = 800


def read_vault_file(vault: Path, filename: str) -> str:
    p = vault / filename
    try:
        return p.read_text(encoding="utf-8").strip()
    except (OSError, FileNotFoundError):
        return "[not found]"


def build_recent_activity(n: int) -> str:
    logs = get_recent_daily_logs(n)
    if not logs:
        return ""
    parts = []
    for date, content in logs:
        truncated = truncate_to_tokens(content, max_chars=DAILY_MAX_CHARS)
        parts.append(f"### {date}\n{truncated}")
    return "\n\n".join(parts)


def assemble_block(soul: str, user: str, projects: str, rules: str, activity: str) -> str:
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
        "<projects>",
        projects,
        "</projects>",
        "",
        "<rules>",
        rules,
        "</rules>",
        "",
        "<recent_activity>",
        activity,
        "</recent_activity>",
        "</memory>",
    ]
    return "\n".join(lines)


def main() -> None:
    try:
        vault = get_vault_path()
    except Exception:
        return

    soul = read_vault_file(vault, "SOUL.md")
    user = read_vault_file(vault, "USER.md")
    projects = truncate_to_tokens(read_vault_file(vault, "PROJECTS.md"), max_chars=PROJECTS_MAX_CHARS)
    rules = truncate_to_tokens(read_vault_file(vault, "RULES.md"), max_chars=RULES_MAX_CHARS)

    activity = build_recent_activity(3)
    block = assemble_block(soul, user, projects, rules, activity)

    if len(block) > MAX_TOTAL_CHARS:
        activity = build_recent_activity(1)
        block = assemble_block(soul, user, projects, rules, activity)

    print(block)


if __name__ == "__main__":
    main()

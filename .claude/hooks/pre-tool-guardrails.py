from __future__ import annotations

import json
import sys

_BASH_BLOCKLIST = [
    "rm ",
    "rm -",
    "del ",
    "Remove-Item",
    "git push --force",
    "git push -f",
    "format ",
    "mkfs",
    "rd /s",
]

_ALLOWED_PATH_PREFIXES = [
    r"C:\Users\cliao\Desktop\2nd_Brain\vault\\",
    r"C:\Users\cliao\Desktop\2nd_Brain\.claude\\",
    "C:/Users/cliao/Desktop/2nd_Brain/vault/",
    "C:/Users/cliao/Desktop/2nd_Brain/.claude/",
    "/c/Users/cliao/Desktop/2nd_Brain/vault/",
    "/c/Users/cliao/Desktop/2nd_Brain/.claude/",
]


def _block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(2)


def _check_bash(command: str) -> None:
    for pattern in _BASH_BLOCKLIST:
        if pattern in command:
            _block(f"Blocked dangerous bash pattern: '{pattern}'")


def _check_write(path: str) -> None:
    # Normalize backslashes to compare uniformly
    normalized = path.replace("/", "\\")
    for prefix in _ALLOWED_PATH_PREFIXES:
        normalized_prefix = prefix.replace("/", "\\")
        if normalized.startswith(normalized_prefix):
            return
    _block(f"Write path outside allowed vault/.claude/ prefixes: '{path}'")


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        _check_bash(command)
    elif tool_name in ("Write", "Edit"):
        path = tool_input.get("file_path", "")
        if path:
            _check_write(path)

    sys.exit(0)


if __name__ == "__main__":
    main()

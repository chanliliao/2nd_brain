"""
Nightly log cleanup — runs as last step in nightly_update.bat.

For each operational log: scan for ERROR/WARNING lines.
If any found, append a ## Nightly Errors section to today's daily vault log.
Then truncate all operational logs to empty.
Reset heartbeat-state.json to {}.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path


def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("Could not locate project root.")


_ROOT = _find_project_root()
_LOGS_DIR = _ROOT / ".claude" / "data" / "logs"
_STATE_PATH = _ROOT / ".claude" / "data" / "state" / "heartbeat-state.json"
_VAULT_DAILY = _ROOT / "vault" / "daily"

# Logs to scan + truncate (mcp_access.log excluded — security, handled by RotatingFileHandler)
_OPERATIONAL_LOGS = [
    "heartbeat.log",
    "codeburn.log",
    "reflect.log",
    "graphify.log",
]


def _scan_log(log_path: Path) -> list[str]:
    """Return lines containing ERROR or WARNING."""
    if not log_path.exists() or log_path.stat().st_size == 0:
        return []
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return [l for l in lines if "ERROR" in l or "WARNING" in l]
    except OSError:
        return []


def _append_errors_to_daily(error_lines: list[str]) -> None:
    today = date.today().isoformat()
    daily = _VAULT_DAILY / f"{today}.md"
    daily.parent.mkdir(parents=True, exist_ok=True)
    block = f"\n\n## Nightly Errors ({today})\n\n"
    block += "\n".join(f"- `{l.strip()}`" for l in error_lines[:50])  # cap at 50
    if daily.exists():
        daily.write_text(daily.read_text(encoding="utf-8") + block, encoding="utf-8")
    else:
        daily.write_text(block.lstrip(), encoding="utf-8")
    print(f"  Appended {len(error_lines)} error/warning line(s) to {daily.name}")


def _truncate_log(log_path: Path) -> None:
    if log_path.exists():
        log_path.write_text("", encoding="utf-8")
        print(f"  Truncated: {log_path.name}")


def _reset_heartbeat_state() -> None:
    if _STATE_PATH.exists():
        _STATE_PATH.write_text("{}\n", encoding="utf-8")
        print("  Reset: heartbeat-state.json")


def main() -> None:
    print("=== Nightly log cleanup ===")
    all_errors: list[str] = []
    for name in _OPERATIONAL_LOGS:
        path = _LOGS_DIR / name
        errors = _scan_log(path)
        if errors:
            print(f"  {name}: {len(errors)} error/warning line(s) found")
            all_errors.extend([f"[{name}] {l}" for l in errors])

    if all_errors:
        _append_errors_to_daily(all_errors)
    else:
        print("  No errors found in operational logs.")

    for name in _OPERATIONAL_LOGS:
        _truncate_log(_LOGS_DIR / name)

    _reset_heartbeat_state()
    print("=== Cleanup complete ===")


if __name__ == "__main__":
    main()

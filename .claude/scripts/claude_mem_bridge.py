"""
claude_mem_bridge.py — Nightly bridge between claude-mem sessions and the vault daily log.

Scheduled at 3:45 AM daily (before Daily Reflection at 4:00 AM).

Flow:
  1. Start the claude-mem worker if not already running
  2. Fetch yesterday's session summaries from the REST API
  3. Append a "## Claude Sessions" section to vault/daily/YYYY-MM-DD.md
  4. Shut down the worker (if we started it)

The reflection pipeline reads the daily log at 4 AM and promotes the session
content into long-term memory (vault/MEMORY.md + SQLite RAG index).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PLUGIN_CACHE = Path.home() / ".claude" / "plugins" / "cache" / "thedotmack" / "claude-mem"
_NODE = Path(r"C:\Program Files\nodejs\node.exe")
_PORT = 37777
_HOST = "127.0.0.1"


def _plugin_root() -> Path | None:
    """Return the latest installed claude-mem version directory."""
    if not _PLUGIN_CACHE.exists():
        return None
    versions = sorted(_PLUGIN_CACHE.iterdir(), reverse=True)
    for v in versions:
        if (v / "scripts" / "bun-runner.js").exists():
            return v
    return None


def _project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return current.parent


_PROJECT_ROOT = _project_root()
_VAULT_ROOT = _PROJECT_ROOT / "vault"


# ---------------------------------------------------------------------------
# Worker lifecycle
# ---------------------------------------------------------------------------

def _is_running() -> bool:
    try:
        with urllib.request.urlopen(
            f"http://{_HOST}:{_PORT}/api/health", timeout=2
        ) as r:
            return r.status == 200
    except Exception:
        return False


def _start_worker(plugin_root: Path) -> bool:
    bun_runner = plugin_root / "scripts" / "bun-runner.js"
    worker_script = plugin_root / "scripts" / "worker-wrapper.cjs"
    if not worker_script.exists():
        worker_script = plugin_root / "scripts" / "worker-service.cjs"

    if not _NODE.exists():
        print("[bridge] node.exe not found — cannot start worker", file=sys.stderr)
        return False

    print(f"[bridge] Starting worker (plugin: {plugin_root.name})", file=sys.stderr)
    subprocess.Popen(
        [str(_NODE), str(bun_runner), str(worker_script), "start"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait up to 30 s for the worker to become healthy
    for _ in range(30):
        time.sleep(1)
        if _is_running():
            print("[bridge] Worker healthy", file=sys.stderr)
            return True

    print("[bridge] Worker did not start within 30 s", file=sys.stderr)
    return False


def _stop_worker() -> None:
    try:
        req = urllib.request.Request(
            f"http://{_HOST}:{_PORT}/api/admin/shutdown", method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
        print("[bridge] Worker shutdown requested", file=sys.stderr)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _get(path: str) -> dict | list | None:
    try:
        with urllib.request.urlopen(
            f"http://{_HOST}:{_PORT}{path}", timeout=10
        ) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[bridge] GET {path} failed: {e}", file=sys.stderr)
        return None


def _unwrap(data: dict | list | None) -> list[dict]:
    """Normalize paginated {items:[...]} or raw list to a plain list."""
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items", [])
    return []


def _fetch_yesterday_sessions(yesterday: date) -> list[dict]:
    """Pull summaries from the worker API and filter to yesterday."""
    yesterday_str = yesterday.isoformat()

    for endpoint in ("/api/summaries", "/api/observations"):
        items = _unwrap(_get(endpoint))
        if items:
            filtered = [
                s for s in items
                if str(s.get("createdAt", s.get("created_at", s.get("date", s.get("timestamp", ""))))).startswith(yesterday_str)
            ]
            if filtered:
                return filtered

    return []


def _extract_text(session: dict) -> str:
    """Pull the most useful text field from a session object."""
    for field in ("summary", "narrative", "content", "text", "description"):
        val = session.get(field)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return json.dumps(session, ensure_ascii=False)[:300]


# ---------------------------------------------------------------------------
# Daily log writing
# ---------------------------------------------------------------------------

def _append_sessions(vault_root: Path, yesterday: date, sessions: list[dict]) -> int:
    """Append session summaries to vault/daily/YYYY-MM-DD.md. Returns count written."""
    if not sessions:
        return 0

    daily_path = vault_root / "daily" / f"{yesterday.isoformat()}.md"
    daily_path.parent.mkdir(parents=True, exist_ok=True)

    if not daily_path.exists():
        daily_path.write_text(
            f"# {yesterday.isoformat()}\n\n## Today's Focus\n\n",
            encoding="utf-8",
        )

    lines = ["\n## Claude Sessions\n"]
    for s in sessions:
        text = _extract_text(s)
        if text:
            lines.append(f"- {text}")

    if len(lines) <= 1:
        return 0

    with daily_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(
        f"[bridge] Appended {len(sessions)} session(s) to {daily_path.name}",
        file=sys.stderr,
    )
    return len(sessions)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_bridge(vault_root: Path | None = None) -> dict:
    vault_root = vault_root or _VAULT_ROOT
    yesterday = date.today() - timedelta(days=1)

    plugin_root = _plugin_root()
    if plugin_root is None:
        print("[bridge] claude-mem plugin not installed — nothing to bridge", file=sys.stderr)
        return {"sessions": 0, "error": "plugin_not_found"}

    we_started = False
    if not _is_running():
        started = _start_worker(plugin_root)
        if not started:
            return {"sessions": 0, "error": "worker_start_failed"}
        we_started = True

    sessions = _fetch_yesterday_sessions(yesterday)
    written = _append_sessions(vault_root, yesterday, sessions)

    if we_started:
        _stop_worker()

    return {"sessions": len(sessions), "written": written}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Bridge claude-mem sessions into the vault daily log"
    )
    parser.add_argument(
        "--vault",
        type=Path,
        default=_VAULT_ROOT,
        help=f"Vault root (default: {_VAULT_ROOT})",
    )
    parser.add_argument(
        "--date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Target date (default: yesterday)",
    )
    args = parser.parse_args()

    if args.date:
        try:
            target = date.fromisoformat(args.date)
        except ValueError:
            print(f"[bridge] Invalid date: {args.date}", file=sys.stderr)
            sys.exit(1)
        # Override yesterday with the explicit date
        import datetime as _dt
        _orig_today = date.today
        date.today = staticmethod(lambda: target + _dt.timedelta(days=1))  # type: ignore

    result = run_bridge(args.vault)
    print(json.dumps(result))
    sys.exit(0 if result.get("error") is None else 1)

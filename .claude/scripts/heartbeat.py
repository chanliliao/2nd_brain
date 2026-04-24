"""
Heartbeat orchestrator for Henry's Second Brain.

Runs every 30 min during active hours (8AM-10PM Eastern).
Gathers data from Gmail, GitHub, and Google Calendar; diffs against the last
state snapshot; calls Haiku for a structured analysis; auto-detects habit
completions; sends a Windows Toast notification on deltas; and writes an
action summary to today's daily log + HEARTBEAT.md.

Usage:
    python heartbeat.py [--once] [--force] [--vault PATH] [--db PATH]
                        [--state PATH] [--log PATH] [--skip-hours-check]
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path


# --------------------------------------------------------------------------- #
# Project root                                                                  #
# --------------------------------------------------------------------------- #

def _find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return start.resolve()


_PROJECT_ROOT = _find_project_root(Path(__file__))
_VAULT_ROOT = _PROJECT_ROOT / "vault"
_STATE_PATH = _PROJECT_ROOT / "data" / "state" / "heartbeat-state.json"
_LOG_PATH = _PROJECT_ROOT / "data" / "logs" / "heartbeat.log"
_SCRIPTS_DIR = Path(__file__).parent

_ACTIVE_HOURS = (8, 22)  # 8 AM – 10 PM inclusive start, exclusive end


# --------------------------------------------------------------------------- #
# Logging                                                                       #
# --------------------------------------------------------------------------- #

def _setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("heartbeat")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
        logger.addHandler(logging.StreamHandler(sys.stdout))
    return logger


# --------------------------------------------------------------------------- #
# Active hours guard                                                            #
# --------------------------------------------------------------------------- #

def _is_active_hours() -> bool:
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+
    except ImportError:
        try:
            from backports.zoneinfo import ZoneInfo  # type: ignore
        except ImportError:
            return True  # can't check timezone — let Task Scheduler enforce it
    now_et = datetime.now(ZoneInfo("America/New_York"))
    return _ACTIVE_HOURS[0] <= now_et.hour < _ACTIVE_HOURS[1]


# --------------------------------------------------------------------------- #
# Integration data gathering                                                    #
# --------------------------------------------------------------------------- #

def _add_scripts_to_path() -> None:
    scripts_parent = _SCRIPTS_DIR
    if str(scripts_parent) not in sys.path:
        sys.path.insert(0, str(scripts_parent))


def _gather_gmail() -> list[dict]:
    _add_scripts_to_path()
    try:
        from integrations.gmail import GmailConfig, list_unread
        return list_unread(GmailConfig.from_env())
    except Exception as exc:
        return [{"error": str(exc)}]


def _gather_github() -> list[dict]:
    _add_scripts_to_path()
    try:
        from integrations.github import GitHubConfig, list_prs_for_review
        return list_prs_for_review(GitHubConfig.from_env())
    except Exception as exc:
        return [{"error": str(exc)}]


def _gather_calendar() -> list[dict]:
    _add_scripts_to_path()
    try:
        from integrations.gcal import GCalConfig, upcoming
        return upcoming(GCalConfig.from_env(), hours=2)
    except Exception as exc:
        return [{"error": str(exc)}]


def _gather_codeburn() -> str:
    try:
        result = subprocess.run(
            ["codeburn", "status", "--format", "json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            total = data.get("total_cost_usd", data.get("total", "?"))
            sessions = data.get("session_count", data.get("sessions", "?"))
            return f"Total: ${total}, Sessions: {sessions}"
        return f"codeburn exit {result.returncode}: {result.stderr[:80]}"
    except FileNotFoundError:
        return "codeburn not installed"
    except Exception as exc:
        return f"codeburn error: {exc}"


# --------------------------------------------------------------------------- #
# LLM analysis (Haiku — cost-efficient for frequent runs)                      #
# --------------------------------------------------------------------------- #

_SYSTEM_PROMPT = """\
You are the heartbeat analyzer for Henry Liao's personal Second Brain.
Henry is a software engineer job-hunting in NYC who studies AI engineering.

Analyze the provided JSON snapshot and produce a JSON object with exactly these keys:
- "notification_title": string, ≤60 chars. Set to "" if nothing notable changed.
- "notification_body": string, ≤200 chars. One or two sentences.
- "draft_emails": list of Gmail thread IDs (strings) that need a reply draft.
- "draft_prs": list of "{repo}#{number}" strings that need a review draft.
- "habit_notes": string. Brief (≤80 chars) observation about habit progress. "" if nothing to note.
- "summary": string. 2-3 sentences summarising what changed this cycle.

Rules:
- Prioritise delta information from the "diff" key — only surface new/changed items.
- If diff is empty or {"first_run": true} with no notable integrations data, set notification_title to "".
- draft_emails: only include thread IDs where needs_reply is true AND they appear in diff.gmail.newly_needs_reply.
- draft_prs: only include new PRs from diff.github.new_prs.
- Output ONLY valid JSON — no markdown fences, no extra text.
"""


def _analyze(
    gmail: list[dict],
    github: list[dict],
    calendar: list[dict],
    codeburn: str,
    diff: dict,
    habits: dict[str, bool],
    logger: logging.Logger,
) -> dict:
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed — skipping LLM analysis")
        return _fallback_analysis(gmail, github, diff)

    context = {
        "gmail": {
            "unread_count": len([t for t in gmail if "error" not in t]),
            "needs_reply_ids": [t["id"] for t in gmail if t.get("needs_reply") and "error" not in t],
            "subjects_preview": [t.get("subject", "?") for t in gmail[:5] if "error" not in t],
        },
        "github": {
            "prs_count": len([p for p in github if "error" not in p]),
            "prs_preview": [
                f"{p['repo']}#{p['number']}: {p.get('title', '')}"
                for p in github[:5]
                if "error" not in p
            ],
        },
        "calendar": {
            "upcoming_count": len([e for e in calendar if "error" not in e]),
            "events_preview": [e.get("summary", "?") for e in calendar[:3] if "error" not in e],
        },
        "codeburn": codeburn,
        "diff": diff,
        "habits_today": habits,
    }

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(context)}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as exc:
        logger.warning(f"LLM analysis failed: {exc}")
        return _fallback_analysis(gmail, github, diff)


def _fallback_analysis(gmail: list, github: list, diff: dict) -> dict:
    g_count = len([t for t in gmail if "error" not in t])
    gh_count = len([p for p in github if "error" not in p])
    return {
        "notification_title": "Heartbeat" if diff else "",
        "notification_body": f"Gmail: {g_count} unread · GitHub: {gh_count} PRs",
        "draft_emails": [],
        "draft_prs": [],
        "habit_notes": "",
        "summary": "Analysis unavailable — check logs.",
    }


# --------------------------------------------------------------------------- #
# Draft action note in daily log                                                #
# --------------------------------------------------------------------------- #

def _write_draft_action_note(
    vault_root: Path,
    draft_emails: list[str],
    draft_prs: list[str],
    logger: logging.Logger,
) -> None:
    if not draft_emails and not draft_prs:
        return

    today_str = date.today().strftime("%Y-%m-%d")
    daily_path = vault_root / "daily" / f"{today_str}.md"

    lines = ["\n## Heartbeat Actions\n"]
    if draft_emails:
        lines.append("**Emails needing reply drafts:**")
        for tid in draft_emails:
            lines.append(f"- Gmail thread `{tid}` — run `/draft-email` to compose a reply")
    if draft_prs:
        lines.append("\n**PRs needing review drafts:**")
        for pr_key in draft_prs:
            lines.append(f"- {pr_key} — run `/code-review-sweep` to draft a review")

    section = "\n".join(lines) + "\n"

    if not daily_path.exists():
        daily_path.parent.mkdir(parents=True, exist_ok=True)
        daily_path.write_text(f"# {today_str}\n\n## Today's Focus\n\n", encoding="utf-8")

    with daily_path.open("a", encoding="utf-8") as f:
        f.write(section)

    logger.info(f"Draft actions written to {daily_path.name}")


# --------------------------------------------------------------------------- #
# HEARTBEAT.md update                                                           #
# --------------------------------------------------------------------------- #

def _write_heartbeat_md(
    vault_root: Path,
    run_dt: datetime,
    analysis: dict,
    habits: dict[str, bool],
    gmail_count: int,
    github_count: int,
    cal_count: int,
) -> None:
    heartbeat_path = vault_root / "HEARTBEAT.md"
    try:
        from zoneinfo import ZoneInfo
        dt_str = run_dt.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M ET")
    except Exception:
        dt_str = run_dt.strftime("%Y-%m-%d %H:%M UTC")

    habit_lines = [
        f"- {'✓' if done else '○'} {name}"
        for name, done in habits.items()
    ]

    lines = [
        f"# Heartbeat — {dt_str}",
        "",
        "## Integration Snapshot",
        f"- Unread Gmail: {gmail_count}",
        f"- GitHub PRs needing attention: {github_count}",
        f"- Calendar events (next 2h): {cal_count}",
        "",
        "## Habits Today",
        *habit_lines,
        "",
        "## Analysis",
        analysis.get("summary", ""),
    ]

    if analysis.get("habit_notes"):
        lines += ["", "## Habit Notes", analysis["habit_notes"]]

    heartbeat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Main heartbeat cycle                                                          #
# --------------------------------------------------------------------------- #

def run_heartbeat(
    vault_root: Path = _VAULT_ROOT,
    db_path: Path | None = None,
    state_path: Path = _STATE_PATH,
    log_path: Path = _LOG_PATH,
    force: bool = False,
) -> dict:
    """Execute one heartbeat cycle. Returns a status summary dict."""
    logger = _setup_logging(log_path)
    run_dt = datetime.now(timezone.utc)

    if db_path is None:
        db_path = _PROJECT_ROOT / "data" / "memory.sqlite"

    # Import sibling modules (same scripts/ directory)
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    from heartbeat_state import build_snapshot, diff_snapshot, load_state, save_state
    from habits import detect_habits, update_habits_md
    from notify import send_toast

    logger.info("=== Heartbeat start ===")

    # Gather integration data
    logger.info("Gathering Gmail…")
    gmail = _gather_gmail()

    logger.info("Gathering GitHub…")
    github = _gather_github()

    logger.info("Gathering Calendar…")
    calendar = _gather_calendar()

    codeburn = _gather_codeburn()
    logger.info(f"Codeburn: {codeburn}")

    # State diff — skip LLM + notification if nothing changed (unless --force)
    old_state = load_state(state_path)
    new_snapshot = build_snapshot(gmail, github, calendar)
    diff = diff_snapshot(old_state, new_snapshot)

    if not diff and not force:
        logger.info("No changes detected — saving state and exiting quietly")
        save_state(new_snapshot, state_path)
        return {"status": "no_change"}

    # Detect habits and update HABITS.md
    habits = detect_habits(vault_root)
    update_habits_md(habits, vault_root)
    logger.info(f"Habits: {habits}")

    # LLM analysis
    analysis = _analyze(gmail, github, calendar, codeburn, diff, habits, logger)
    logger.info(f"Analysis: title='{analysis.get('notification_title', '')}' "
                f"draft_emails={analysis.get('draft_emails', [])} "
                f"draft_prs={analysis.get('draft_prs', [])}")

    # Send Windows Toast if something notable
    if analysis.get("notification_title"):
        ok = send_toast(
            analysis["notification_title"],
            analysis.get("notification_body", ""),
        )
        logger.info(f"Toast {'sent' if ok else 'failed (see fallback)'}")

    # Write action notes to daily log
    _write_draft_action_note(
        vault_root,
        analysis.get("draft_emails", []),
        analysis.get("draft_prs", []),
        logger,
    )

    # Update HEARTBEAT.md
    gmail_ok = [t for t in gmail if "error" not in t]
    github_ok = [p for p in github if "error" not in p]
    cal_ok = [e for e in calendar if "error" not in e]
    _write_heartbeat_md(
        vault_root, run_dt, analysis, habits,
        len(gmail_ok), len(github_ok), len(cal_ok),
    )

    # Persist new state
    save_state(new_snapshot, state_path)
    logger.info("=== Heartbeat complete ===")

    return {
        "status": "ok",
        "diff": diff,
        "habits": habits,
        "notification_sent": bool(analysis.get("notification_title")),
    }


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Second Brain heartbeat — runs one cycle and exits."
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Alias for the default behaviour (single run). Kept for Task Scheduler compatibility.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Send notification even if no state changes detected.",
    )
    parser.add_argument("--vault", default=str(_VAULT_ROOT), help="Vault root path")
    parser.add_argument("--db", default=None, help="SQLite database path")
    parser.add_argument("--state", default=str(_STATE_PATH), help="State JSON path")
    parser.add_argument("--log", default=str(_LOG_PATH), help="Log file path")
    parser.add_argument(
        "--skip-hours-check", action="store_true",
        help="Run regardless of active-hours window (8AM-10PM ET).",
    )
    args = parser.parse_args()

    if not args.skip_hours_check and not _is_active_hours():
        print("Outside active hours (8AM–10PM ET). Use --skip-hours-check to override.")
        sys.exit(0)

    result = run_heartbeat(
        vault_root=Path(args.vault),
        db_path=Path(args.db) if args.db else None,
        state_path=Path(args.state),
        log_path=Path(args.log),
        force=args.force,
    )
    print(json.dumps(result, indent=2, default=str))

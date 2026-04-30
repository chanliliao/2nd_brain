"""
Nightly codeburn reflection — stats to daily log, optimize suggestions to proposal queue.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path


def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("No .claude/ dir found")


_ROOT = _find_project_root()
_VAULT = _ROOT / "vault"
_SCRIPTS = _ROOT / ".claude" / "scripts"
sys.path.insert(0, str(_SCRIPTS))


def _run_codeburn(*args: str, timeout: int = 60) -> str:
    result = subprocess.run(
        ["codeburn", *args], capture_output=True, text=True, timeout=timeout,
        shell=sys.platform == "win32", encoding="utf-8", errors="replace",
    )
    # codeburn writes to stderr on Windows ps1 wrapper
    return result.stdout or result.stderr


def _append_daily_stats(stats: dict) -> None:
    today = date.today().isoformat()
    daily = _VAULT / "daily" / f"{today}.md"
    daily.parent.mkdir(parents=True, exist_ok=True)

    # Dedup: skip if already written today
    if daily.exists() and f"## Codeburn ({today})" in daily.read_text(encoding="utf-8"):
        print(f"  Stats already written for {today}, skipping.")
        return

    summary = stats.get("summary", [])
    rows = {r["Period"]: r for r in summary}
    t = rows.get("Today", {})
    w = rows.get("7 Days", {})
    m = rows.get("30 Days", {})

    block = (
        f"\n\n## Codeburn ({today})\n\n"
        "| Period | Cost | Calls | Sessions |\n"
        "|--------|------|-------|----------|\n"
        f"| Today  | ${t.get('Cost (USD)', 0):.2f} | {t.get('API Calls', 0)} | {t.get('Sessions', 0)} |\n"
        f"| 7 Days | ${w.get('Cost (USD)', 0):.2f} | {w.get('API Calls', 0)} | {w.get('Sessions', 0)} |\n"
        f"| 30 Days| ${m.get('Cost (USD)', 0):.2f} | {m.get('API Calls', 0)} | {m.get('Sessions', 0)} |\n"
    )

    if daily.exists():
        daily.write_text(daily.read_text(encoding="utf-8") + block, encoding="utf-8")
    else:
        daily.write_text(f"# {today}\n{block}", encoding="utf-8")
    print(f"  Stats appended -> {daily}")


def _parse_suggestions(text: str) -> list[dict]:
    suggestions = []
    # Split on section headers: ─── N. Title ────── Priority ───
    parts = re.split(r"─{3,}\s+\d+\.\s+", text)
    for part in parts[1:]:
        lines = part.strip().splitlines()
        if not lines:
            continue

        # Header line: "Title ──────────────── Priority ───"
        header = lines[0]
        priority_match = re.search(r"─{3,}\s*(High|Medium|Low)\s*─{3,}", header)
        priority = priority_match.group(1) if priority_match else "Medium"
        title = re.sub(r"\s*─{3,}.*$", "", header).strip()

        savings_match = re.search(r"Potential savings:\s*(.+)", part)
        savings = savings_match.group(1).strip() if savings_match else ""

        # Collect indented command lines
        commands = [
            line.strip()
            for line in lines
            if re.match(r"^\s{4,}\S", line) and not line.strip().startswith("In ")
        ]

        # Description: non-empty lines after header, before savings/commands
        desc_lines = []
        for line in lines[1:]:
            stripped = line.strip()
            if re.match(r"Potential savings:", stripped):
                break
            if stripped:
                desc_lines.append(stripped)
        description = " ".join(desc_lines)

        suggestions.append(
            {
                "title": title,
                "priority": priority,
                "savings": savings,
                "description": description,
                "commands": commands,
            }
        )
    return suggestions


def _extract_item_names(commands: list[str]) -> set[str]:
    """Extract specific item names from mv commands.

    e.g. "mv ~/.claude/agents/changelog-updater.md ~/.claude/agents/.archived/"
    → "changelog-updater"
    """
    items: set[str] = set()
    for cmd in commands:
        m = re.search(r'/([^/\s]+?)(?:\.md)?\s', cmd)
        if m:
            items.add(m.group(1))
    return items


def _rejected_items(vault: Path) -> set[str]:
    """Return all item names that appear in rejected proposal commands."""
    items: set[str] = set()
    for f in (vault / "rejected").glob("*codeburn-suggestion*.md"):
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        cmds = re.findall(r"- '(mv .+?)'", text)
        items |= _extract_item_names(cmds)
    return items


def _already_decided(title: str, commands: list[str]) -> bool:
    """Return True if this proposal was already approved/rejected.

    Two checks:
    1. Exact title match in approved/ or rejected/.
    2. Item-level match: if every specific item in this proposal's commands
       was already mentioned in a rejected proposal, suppress it.
       Allows future proposals about NEW items of the same type (agents,
       skills, commands) while blocking re-suggestions of rejected ones.
    """
    vault = _ROOT / "vault" / "drafts"

    # 1. Exact title match
    for folder in ("approved", "rejected"):
        for f in (vault / folder).glob("*codeburn-suggestion*.md"):
            try:
                text = f.read_text(encoding="utf-8")
                if f"title: '{title}'" in text or f'title: "{title}"' in text:
                    return True
            except OSError:
                pass

    # 2. Item-level dedup: block if all items in this proposal were previously rejected
    new_items = _extract_item_names(commands)
    if new_items:
        already_rejected = _rejected_items(vault)
        if new_items <= already_rejected:
            overlap = new_items & already_rejected
            print(f"  Skip (items already rejected — {', '.join(sorted(overlap))}): {title[:60]}")
            return True

    return False


def _create_proposals(suggestions: list[dict]) -> None:
    from proposals import write_proposal  # type: ignore

    for s in suggestions:
        if _already_decided(s["title"], s.get("commands", [])):
            print(f"  Skip (already approved/rejected): {s['title'][:60]}")
            continue
        payload = {
            "title": s["title"],
            "priority": s["priority"],
            "savings": s["savings"],
            "description": s["description"],
            "commands": s["commands"],
        }
        body = f"**{s['priority']}** — {s['title']}\n\n{s['description']}\n\nSavings: {s['savings']}"
        if s["commands"]:
            body += "\n\n```\n" + "\n".join(s["commands"]) + "\n```"
        path = write_proposal("codeburn-suggestion", payload, "codeburn-reflect", body)
        print(f"  Proposal: {s['title'][:60]} -> {path.name}")


def main() -> None:
    print(f"[codeburn_reflect] {datetime.now(timezone.utc).isoformat()}")

    # 1. Stats
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        tmp_path = Path(f.name)
    try:
        subprocess.run(
            ["codeburn", "export", "-f", "json", "-o", str(tmp_path)],
            capture_output=True, text=True, timeout=30,
            shell=sys.platform == "win32", encoding="utf-8", errors="replace",
        )
        raw = tmp_path.read_text(encoding="utf-8")
        stats = json.loads(raw)
        _append_daily_stats(stats)
    except Exception as exc:
        print(f"  Stats error: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)

    # 2. Optimize suggestions
    print("  Running codeburn optimize --period week …")
    opt_text = _run_codeburn("optimize", "--period", "week")
    suggestions = _parse_suggestions(opt_text)
    print(f"  Parsed {len(suggestions)} suggestion(s).")
    if suggestions:
        _create_proposals(suggestions)

    print("[codeburn_reflect] done.")


if __name__ == "__main__":
    main()

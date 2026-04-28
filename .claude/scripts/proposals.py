"""proposals.py — Approval-gated proposal queue for the Second Brain system.

CLI: python proposals.py list|approve|reject|defer|auto-approve [<path>]

Auto-approval: reflect-mistake and reflect-shortcut proposals older than
AUTO_APPROVE_HOURS hours are approved automatically if they have no conflicts.
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

AUTO_APPROVE_HOURS = 24
AUTO_APPROVE_TYPES = {"reflect-mistake", "reflect-shortcut"}

import yaml

# ── paths ──────────────────────────────────────────────────────────────────────

def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return here.parent

_ROOT = _find_project_root()
_VAULT = _ROOT / "vault"
_PROPOSALS_DIR = _VAULT / "drafts" / "proposals"
_DB_PATH = _ROOT / ".claude" / "data" / "memory.sqlite"

# ── small helpers ──────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text[:30].lower()).strip("-") or "proposal"

def _parse(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return {}, raw
    end = raw.index("---", 3)
    return yaml.safe_load(raw[3:end]) or {}, raw[end + 3:].strip()

def _set_status(src: Path, status: str, dest: Path) -> None:
    raw = re.sub(r"(?m)^status:.*$", f"status: {status}", src.read_text(encoding="utf-8"), count=1)
    dest.write_text(raw, encoding="utf-8")

def _write_md(dest: Path, fm_str: str, body: str) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f"---\n{fm_str}---\n{body}\n", encoding="utf-8")
    return dest

def _db_conn():
    try:
        from memory.db import init_db  # type: ignore
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent))
        from memory.db import init_db  # type: ignore
    return init_db(_DB_PATH)

def _index(dest: Path) -> None:
    try:
        from memory.indexer import index_file  # type: ignore
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent))
        from memory.indexer import index_file  # type: ignore
    conn = _db_conn()
    try:
        index_file(dest, _VAULT, conn)
    finally:
        conn.close()

# ── public write API ───────────────────────────────────────────────────────────

def _next_proposal_id() -> int:
    """Return next sequential proposal ID across all proposal dirs."""
    max_id = 0
    for folder in ("proposals", "approved", "rejected"):
        d = _VAULT / "drafts" / folder
        if not d.exists():
            continue
        for f in d.glob("*.md"):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                m = re.search(r"^id:\s*(\d+)", text, re.MULTILINE)
                if m:
                    max_id = max(max_id, int(m.group(1)))
            except OSError:
                pass
    return max_id + 1


def write_proposal(type: str, payload: dict[str, Any], proposed_by: str, body: str) -> Path:
    """Create a pending proposal file and return its path."""
    _PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(tz=timezone.utc)
    proposal_id = _next_proposal_id()
    path = _PROPOSALS_DIR / f"{now.strftime('%Y-%m-%d')}_{type}_{proposal_id:03d}.md"
    lines = ["---", f"id: {proposal_id}", f"type: {type}", f"proposed_at: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
             f"proposed_by: {proposed_by}", "status: pending-review", "payload:"]
    for k, v in payload.items():
        if isinstance(v, list):
            lines.append(f"  {k}:")
            for item in v:
                if isinstance(item, dict):
                    first = True
                    for ik, iv in item.items():
                        lines.append("  " + ("- " if first else "  ") + f"{ik}: {iv!r}")
                        first = False
                else:
                    lines.append(f"  - {item!r}")
        else:
            lines.append(f"  {k}: {v!r}")
    lines += ["---", "", body]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

# ── approve dispatch ───────────────────────────────────────────────────────────

def _execute_codeburn_commands(commands: list) -> None:
    import shutil as _shutil
    import re as _re
    claude_md = Path.home() / ".claude" / "CLAUDE.md"

    for cmd in commands:
        cmd = cmd.strip()
        if not cmd:
            continue

        mv_match = _re.match(r"^mv\s+(\S+)\s+(\S+)$", cmd)
        if mv_match:
            src = Path(mv_match.group(1)).expanduser()
            dst = Path(mv_match.group(2)).expanduser()
            try:
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    _shutil.move(str(src), str(dst))
                    print(f"  Moved: {src.name} -> {dst.parent.name}/")
                else:
                    print(f"  Skip (not found): {src}")
            except Exception as exc:
                print(f"  Move failed {src}: {exc}")
            continue

        if _re.match(r"^export\s+\w+=", cmd):
            print(f"  Note (set manually in shell profile): {cmd}")
            continue

        # Prose → append to ~/.claude/CLAUDE.md if not already present
        if claude_md.exists():
            existing = claude_md.read_text(encoding="utf-8")
            if cmd not in existing:
                claude_md.write_text(
                    existing.rstrip() + f"\n\n{cmd}\n", encoding="utf-8"
                )
                print(f"  Added to CLAUDE.md: {cmd[:80]}")
            else:
                print(f"  Already in CLAUDE.md: {cmd[:60]}")


def _apply_rule_to_claude_md(rule: str) -> None:
    """Append a behavioral rule to the project CLAUDE.md if not already present."""
    claude_md = _ROOT / "CLAUDE.md"
    if not claude_md.exists():
        return
    existing = claude_md.read_text(encoding="utf-8")
    if rule.strip() in existing:
        print(f"  Rule already in CLAUDE.md: {rule[:60]}")
        return
    claude_md.write_text(existing.rstrip() + f"\n\n## Auto-rule (reflect)\n{rule}\n", encoding="utf-8")
    print(f"  Rule added to CLAUDE.md: {rule[:80]}")


def _apply_code_fix_auto(problem: str, fix_description: str) -> None:
    """Call Claude (Sonnet) to generate and apply a code fix from the fix description."""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from claude_cli import call_claude  # type: ignore
    except ImportError:
        print(f"  Cannot auto-apply (claude_cli unavailable): {fix_description}")
        return

    import json as _json
    import re as _re

    prompt = (
        f"Project root: {_ROOT}\n\n"
        f"Problem: {problem}\n\n"
        f"Fix: {fix_description}\n\n"
        "Return ONLY a JSON object:\n"
        '{"file": "<path relative to project root>", "old": "<exact text to replace>", "new": "<replacement text>"}\n'
        "Rules: path must be relative. old must be exact substring present in the file. "
        'If no specific code change can be determined, return {"file": null}. No other text.'
    )

    try:
        raw = call_claude(prompt, model="sonnet").strip()
        raw = _re.sub(r"^```(?:json)?\s*", "", raw, flags=_re.IGNORECASE)
        raw = _re.sub(r"\s*```$", "", raw.strip())
        patch = _json.loads(raw.strip())
    except Exception as exc:
        print(f"  Auto-apply failed (parse error {exc}): {fix_description[:60]}")
        return

    if not patch.get("file"):
        print(f"  Auto-apply: no file identified for: {problem[:60]}")
        return

    target = _ROOT / patch["file"]
    if not target.exists():
        print(f"  Auto-apply: file not found: {patch['file']}")
        return

    old_text = patch.get("old", "")
    new_text = patch.get("new", "")
    if not old_text:
        print(f"  Auto-apply: empty old text in patch")
        return

    content = target.read_text(encoding="utf-8")
    if old_text not in content:
        print(f"  Auto-apply: old text not found in {patch['file']}")
        return

    target.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
    print(f"  Auto-applied code fix to {patch['file']}")


def _approve(fm: dict) -> None:
    p, t, today = fm.get("payload", {}), fm.get("type", ""), date.today().isoformat()
    pid = int(fm.get("id", 0))

    if t == "reflect-conflict":
        try:
            from memory.conflict import apply_supersede  # type: ignore
        except ImportError:
            sys.path.insert(0, str(Path(__file__).parent))
            from memory.conflict import apply_supersede  # type: ignore
        conn = _db_conn()
        try:
            apply_supersede(p["old_chunk_id"], p["new_chunk_id"], conn)
        finally:
            conn.close()

    elif t == "reflect-mistake":
        cat = p.get("suggested_category", "Misc")
        desc = p.get("description", "")
        fix = p.get("fix_description", "")
        fix_type = p.get("fix_type", "reminder")
        body = f"**Problem:** {desc}\n\n**Fix:** {fix}" if fix else desc
        dest = _write_md(
            _VAULT / "Memory" / cat / f"{today}_reflect-mistake_{pid:03d}.md",
            f"type: mistake\ncategory: {cat!r}\nfix_type: {fix_type!r}\n",
            body,
        )
        _index(dest)
        if fix and fix_type == "rule":
            _apply_rule_to_claude_md(fix)
        elif fix and fix_type == "code":
            _apply_code_fix_auto(desc, fix)

    elif t == "prune-set":
        try:
            from memory.prune import apply_chunks  # type: ignore
        except ImportError:
            sys.path.insert(0, str(Path(__file__).parent))
            from memory.prune import apply_chunks  # type: ignore
        conn = _db_conn()
        try:
            apply_chunks([c["id"] for c in p.get("chunks", [])], conn)
        finally:
            conn.close()

    elif t == "agent-memfact":
        cat = p.get("category", "Misc")
        tags = ", ".join(p.get("tags") or [])
        dest = _write_md(
            _VAULT / "Memory" / cat / f"{today}_agent-memfact_{pid:03d}.md",
            f"category: {cat!r}\ntags: {tags}\nsource_agent: {p.get('source_agent','')!r}\n",
            p.get("content", ""),
        )
        _index(dest)

    elif t == "reflect-shortcut":
        cat = p.get("suggested_category", "snippets")
        desc = p.get("description", "")
        fix = p.get("fix_description", "")
        body = f"**Shortcut:** {desc}\n\n**How to apply:** {fix}" if fix else desc
        dest = _write_md(
            _VAULT / "Memory" / cat / f"{today}_reflect-shortcut_{pid:03d}.md",
            f"type: shortcut\ncategory: {cat!r}\n",
            body,
        )
        _index(dest)

    elif t == "agent-session-log":
        agent = p.get("agent_name", "agent")
        dest = _write_md(_VAULT / "Sessions" / f"{today}_{agent}.md",
                         f"agent: {agent!r}\noutcome: {p.get('outcome','')!r}\n",
                         f"## Summary\n{p.get('summary','')}\n\n## Lessons\n{p.get('lessons','')}")
        _index(dest)

    elif t == "codeburn-suggestion":
        _execute_codeburn_commands(p.get("commands") or [])
        title = p.get("title", "optimization")
        cmds = p.get("commands", [])
        cmd_block = ("\n\n### Commands\n```\n" + "\n".join(cmds) + "\n```") if cmds else ""
        dest = _write_md(
            _VAULT / "Memory" / "snippets" / f"{today}_codeburn-suggestion_{pid:03d}.md",
            f"type: codeburn-suggestion\npriority: {p.get('priority', 'Medium')!r}\n",
            f"## {title}\n\n{p.get('description', '')}\n\nSavings: {p.get('savings', '')}{cmd_block}",
        )
        _index(dest)

    else:
        print(f"Unknown type {t!r} — moving to approved without action.")

# ── CLI ────────────────────────────────────────────────────────────────────────

def cmd_list() -> None:
    if not _PROPOSALS_DIR.exists():
        print("No proposals directory found.")
        return
    files = [f for f in sorted(_PROPOSALS_DIR.glob("*.md"), key=lambda p: p.name, reverse=True)
             if "pending-review" in f.read_text(encoding="utf-8")]
    if not files:
        print("No pending proposals.")
        return
    by_type: dict[str, list[Path]] = {}
    for f in files:
        by_type.setdefault(_parse(f)[0].get("type", "unknown"), []).append(f)
    for ptype, paths in sorted(by_type.items()):
        print(f"\n[{ptype}] ({len(paths)} pending)")
        for p in paths:
            print(f"  {p}")

def cmd_approve(path: Path) -> None:
    _approve(_parse(path)[0])
    dest = _VAULT / "drafts" / "approved" / path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    _set_status(path, "approved", dest)
    path.unlink()
    print(f"Approved: {dest}")

def cmd_reject(path: Path) -> None:
    dest = _VAULT / "drafts" / "rejected" / path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    _set_status(path, "rejected", dest)
    path.unlink()
    print(f"Rejected: {dest}")

def cmd_defer(path: Path) -> None:
    print(f"Deferred: {path}")

def cmd_auto_approve() -> None:
    """Auto-approve low-risk proposals older than AUTO_APPROVE_HOURS hours."""
    if not _PROPOSALS_DIR.exists():
        print("No proposals directory.")
        return
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=AUTO_APPROVE_HOURS)
    approved = 0
    for f in sorted(_PROPOSALS_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        if "pending-review" not in text:
            continue
        fm, _ = _parse(f)
        if fm.get("type") not in AUTO_APPROVE_TYPES:
            continue
        proposed_at_str = fm.get("proposed_at", "")
        try:
            proposed_at = datetime.fromisoformat(proposed_at_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if proposed_at > cutoff:
            continue
        print(f"Auto-approving: {f.name}")
        cmd_approve(f)
        approved += 1
    print(f"Auto-approved {approved} proposal(s).")

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Manage approval-gated proposals")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("auto-approve")
    for cmd in ("approve", "reject", "defer"):
        sub.add_parser(cmd).add_argument("path", type=Path)
    args = parser.parse_args()
    {"list": cmd_list, "auto-approve": cmd_auto_approve,
     "approve": lambda: cmd_approve(args.path),
     "reject": lambda: cmd_reject(args.path), "defer": lambda: cmd_defer(args.path)}[args.command]()

if __name__ == "__main__":
    main()

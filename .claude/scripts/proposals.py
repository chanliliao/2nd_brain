"""proposals.py — Approval-gated proposal queue for the Second Brain system.

CLI: python proposals.py list|approve|reject|defer [<path>]
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

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

def write_proposal(type: str, payload: dict[str, Any], proposed_by: str, body: str) -> Path:
    """Create a pending proposal file and return its path."""
    _PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(tz=timezone.utc)
    path = _PROPOSALS_DIR / f"{now.strftime('%Y-%m-%d')}_{type}_{_slugify(body)}.md"
    lines = ["---", f"type: {type}", f"proposed_at: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
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

def _approve(fm: dict) -> None:
    p, t, today = fm.get("payload", {}), fm.get("type", ""), date.today().isoformat()

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
        dest = _write_md(_VAULT / "Memory" / cat / f"{today}_mistake_{_slugify(p.get('description',''))}.md",
                         f"type: mistake\ncategory: {cat!r}\n", p.get("description", ""))
        _index(dest)

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
        dest = _write_md(_VAULT / "Memory" / cat / f"{today}_{_slugify(p.get('content',''))}.md",
                         f"category: {cat!r}\ntags: {tags}\nsource_agent: {p.get('source_agent','')!r}\n",
                         p.get("content", ""))
        _index(dest)

    elif t == "agent-session-log":
        agent = p.get("agent_name", "agent")
        dest = _write_md(_VAULT / "Sessions" / f"{today}_{agent}.md",
                         f"agent: {agent!r}\noutcome: {p.get('outcome','')!r}\n",
                         f"## Summary\n{p.get('summary','')}\n\n## Lessons\n{p.get('lessons','')}")
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

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Manage approval-gated proposals")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    for cmd in ("approve", "reject", "defer"):
        sub.add_parser(cmd).add_argument("path", type=Path)
    args = parser.parse_args()
    {"list": cmd_list, "approve": lambda: cmd_approve(args.path),
     "reject": lambda: cmd_reject(args.path), "defer": lambda: cmd_defer(args.path)}[args.command]()

if __name__ == "__main__":
    main()

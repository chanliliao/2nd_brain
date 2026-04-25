"""
Daily reflection pipeline for the personal second-brain.

Runs at 8AM daily. Reads yesterday's daily log, extracts facts with Haiku,
categorizes them with Sonnet, writes to MEMORY.md, re-indexes, checks conflicts,
and updates HEARTBEAT.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path


# --------------------------------------------------------------------------- #
# Project root detection                                                        #
# --------------------------------------------------------------------------- #

def _find_project_root(start: Path) -> Path:
    """Walk up from start looking for .claude/ directory."""
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    # Fallback: use start itself
    return start.resolve()


_PROJECT_ROOT = _find_project_root(Path(__file__))
_VAULT_ROOT = _PROJECT_ROOT / "vault"


# --------------------------------------------------------------------------- #
# Category parsing                                                              #
# --------------------------------------------------------------------------- #

def _load_category_ids(vault_root: Path) -> list[str]:
    """Parse category IDs from vault/Memory/_categories.yml using regex."""
    categories_path = vault_root / "Memory" / "_categories.yml"
    try:
        yaml_content = categories_path.read_text(encoding="utf-8")
        category_ids = re.findall(r"^\s*-\s*id:\s*(\S+)", yaml_content, re.MULTILINE)
        if category_ids:
            return category_ids
    except FileNotFoundError:
        pass

    # Fallback list
    return [
        "coding-projects", "job-hunt", "interview-prep", "career-goals",
        "tech-stack", "debugging", "snippets", "prompts", "agent-designs",
        "network", "relationships", "habits", "journal", "health", "finance",
    ]


# --------------------------------------------------------------------------- #
# Step 2 — Extract facts (Haiku)                                               #
# --------------------------------------------------------------------------- #

def _extract_facts(log_content: str, client) -> dict:
    """Use Haiku to extract facts, mistakes, and open problems from daily log.
    Returns {facts: [...], mistakes: [...], open_problems: [...]}."""
    system = "You are a memory extraction assistant for a personal second brain."
    user = (
        "Extract information from this daily log into three categories.\n"
        "Output ONLY a valid JSON object with exactly these keys:\n"
        '  "facts": list of strings (decisions, learnings, preferences — max 15)\n'
        '  "mistakes": list of strings (errors made, wrong assumptions — max 5)\n'
        '  "open_problems": list of strings (unresolved issues, blockers — max 5)\n'
        "No other text.\n\nDaily log:\n" + log_content
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return {
                "facts": [str(f) for f in result.get("facts", [])],
                "mistakes": [str(m) for m in result.get("mistakes", [])],
                "open_problems": [str(p) for p in result.get("open_problems", [])],
            }
    except json.JSONDecodeError as exc:
        print(f"[reflect] WARNING: JSON parse error in fact extraction: {exc}", file=sys.stderr)
    return {"facts": [], "mistakes": [], "open_problems": []}


# --------------------------------------------------------------------------- #
# Dedup helper                                                                  #
# --------------------------------------------------------------------------- #

def _is_duplicate(fact: str, conn) -> bool:
    """Return True if this fact is already in the DB (exact hash or cosine > 0.95)."""
    import numpy as np
    import sqlite_vec
    from hashlib import sha256 as _sha256

    content_hash = _sha256(fact.encode()).hexdigest()
    # Exact match
    row = conn.execute(
        "SELECT 1 FROM chunks WHERE content_hash = ? AND superseded_by IS NULL LIMIT 1",
        (content_hash,),
    ).fetchone()
    if row:
        return True

    # Semantic near-duplicate
    try:
        from .embeddings import embed_one
    except ImportError:
        from memory.embeddings import embed_one  # type: ignore
    vec = embed_one(fact)
    blob = sqlite_vec.serialize_float32(vec)
    sim_row = conn.execute(
        """
        SELECT 1 FROM chunk_vectors cv
        JOIN chunks c ON c.id = cv.chunk_id
        WHERE c.superseded_by IS NULL
          AND (1.0 - vec_distance_cosine(cv.embedding, ?)) > 0.95
        LIMIT 1
        """,
        (blob,),
    ).fetchone()
    return sim_row is not None


# --------------------------------------------------------------------------- #
# Step 3 — Categorize facts (Sonnet)                                           #
# --------------------------------------------------------------------------- #

def _categorize_facts(facts: list[str], category_ids: list[str], client) -> list[dict]:
    """Use Sonnet to assign each fact a category. Returns list of {fact, category}."""
    if not facts:
        return []

    categories_list = ", ".join(category_ids)
    system = "You are organizing personal memory into categories."
    user = (
        f"For each fact, assign it to exactly one category from this list: {categories_list}\n"
        f"Output ONLY a valid JSON array of objects with 'fact' and 'category' keys. No other text.\n\n"
        f"Facts:\n{json.dumps(facts)}"
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    try:
        categorized = json.loads(raw)
        if not isinstance(categorized, list):
            raise ValueError("Expected JSON array")
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"[reflect] WARNING: JSON parse error in categorization: {exc}", file=sys.stderr)
        # Fallback: assign everything to 'journal'
        return [{"fact": f, "category": "journal"} for f in facts]

    # Validate categories; default unknown to 'journal'
    valid = set(category_ids)
    result = []
    for item in categorized:
        if not isinstance(item, dict):
            continue
        fact = str(item.get("fact", ""))
        category = str(item.get("category", "journal"))
        if category not in valid:
            print(
                f"[reflect] WARNING: Unknown category '{category}' — defaulting to 'journal'",
                file=sys.stderr,
            )
            category = "journal"
        result.append({"fact": fact, "category": category})

    return result


# --------------------------------------------------------------------------- #
# Step 4 — Write to MEMORY.md                                                  #
# --------------------------------------------------------------------------- #

def _write_memory_section(
    vault_root: Path,
    target_date: date,
    categorized_facts: list[dict],
) -> int:
    """Append reflection section to vault/MEMORY.md. Returns number of facts written."""
    memory_path = vault_root / "MEMORY.md"

    date_str = target_date.strftime("%Y-%m-%d")
    lines = [f"\n## {date_str} Reflection\n"]

    for item in categorized_facts:
        fact = item["fact"]
        category = item["category"]
        chunk_id = sha256(fact.encode()).hexdigest()[:8]
        lines.append(
            f"- [{category}] {fact} <!-- id:{chunk_id} created:{date_str} -->"
        )

    section = "\n".join(lines) + "\n"

    # Create file with header if it doesn't exist
    if not memory_path.exists():
        memory_path.write_text(
            "# Memory — Henry Liao\n\n"
            "This file is append-only. Facts are never deleted — only superseded.\n\n---\n",
            encoding="utf-8",
        )

    with memory_path.open("a", encoding="utf-8") as f:
        f.write(section)

    return len(categorized_facts)


# --------------------------------------------------------------------------- #
# Step 7 — Update HEARTBEAT.md                                                 #
# --------------------------------------------------------------------------- #

def _write_heartbeat(
    vault_root: Path,
    run_dt: datetime,
    yesterday: date,
    facts_extracted: int,
    facts_categorized: int,
    facts_written: int,
    conflicts: list[dict],
) -> None:
    """Overwrite vault/HEARTBEAT.md with reflection summary."""
    heartbeat_path = vault_root / "HEARTBEAT.md"

    dt_str = run_dt.strftime("%Y-%m-%d %H:%M")
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    conflicts_count = len(conflicts)

    lines = [
        f"# Heartbeat — {dt_str} UTC",
        "",
        "## Last Reflection",
        f"- Date: {yesterday_str}",
        f"- Facts extracted: {facts_extracted}",
        f"- Facts categorized: {facts_categorized}",
        f"- Facts written: {facts_written}",
        f"- Conflicts found: {conflicts_count}",
    ]

    if conflicts:
        lines.append("")
        lines.append("## Active Conflicts")
        for c in conflicts:
            old_id = c.get("old_id", "?")
            new_id = c.get("new_id", "?")
            reason = c.get("reason", "")
            lines.append(f"- [{old_id}] superseded by [{new_id}]: {reason}")

    content = "\n".join(lines) + "\n"
    heartbeat_path.write_text(content, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def run_reflection(
    vault_root: Path,
    db_path: Path,
    target_date: date | None = None,
) -> dict:
    """Run full reflection pipeline for target_date (default: yesterday).

    Returns:
        {facts_extracted: N, facts_categorized: M, conflicts_found: C, facts_written: K}
    """
    import anthropic

    # Support both `python reflect.py` (direct) and `python -m memory.reflect` (module)
    try:
        from .db import init_db
        from .indexer import index_file
        from .conflict import check_conflicts
    except ImportError:
        # Direct script execution: add package parent to sys.path
        _pkg_dir = Path(__file__).resolve().parent.parent
        if str(_pkg_dir) not in sys.path:
            sys.path.insert(0, str(_pkg_dir))
        from memory.db import init_db  # type: ignore
        from memory.indexer import index_file  # type: ignore
        from memory.conflict import check_conflicts  # type: ignore

    vault_root = Path(vault_root)
    db_path = Path(db_path)

    run_dt = datetime.now(timezone.utc)

    if target_date is None:
        yesterday = date.today() - timedelta(days=1)
    else:
        yesterday = target_date

    zero_result = {
        "facts_extracted": 0,
        "facts_categorized": 0,
        "conflicts_found": 0,
        "facts_written": 0,
    }

    # ---------------------------------------------------------------------- #
    # Step 1 — Read sources                                                    #
    # ---------------------------------------------------------------------- #
    daily_log_path = vault_root / "daily" / f"{yesterday.strftime('%Y-%m-%d')}.md"

    if not daily_log_path.exists():
        print(
            f"[reflect] No daily log found for {yesterday.strftime('%Y-%m-%d')}, "
            f"skipping reflection.",
            file=sys.stderr,
        )
        # Still write HEARTBEAT.md so the file is always fresh
        _write_heartbeat(vault_root, run_dt, yesterday, 0, 0, 0, [])
        return zero_result

    log_content = daily_log_path.read_text(encoding="utf-8")

    # Optionally read HEARTBEAT for context (not strictly needed for extraction)
    heartbeat_path = vault_root / "HEARTBEAT.md"
    # We just note its existence; no further use required by spec
    _ = heartbeat_path.exists()

    # ---------------------------------------------------------------------- #
    # Step 2 — Extract facts/mistakes/open_problems (Haiku)                  #
    # ---------------------------------------------------------------------- #
    client = anthropic.Anthropic()
    category_ids = _load_category_ids(vault_root)

    buckets = _extract_facts(log_content, client)
    facts_extracted = len(buckets["facts"]) + len(buckets["mistakes"]) + len(buckets["open_problems"])

    # ---------------------------------------------------------------------- #
    # Step 3 — Categorize facts (Sonnet)                                      #
    # ---------------------------------------------------------------------- #
    categorized = _categorize_facts(buckets["facts"], category_ids, client)
    facts_categorized = len(categorized)

    # ---------------------------------------------------------------------- #
    # Step 4 — Dedup check + write to MEMORY.md                              #
    # ---------------------------------------------------------------------- #
    conn = init_db(db_path)

    surviving = [item for item in categorized if not _is_duplicate(item["fact"], conn)]
    facts_written = _write_memory_section(vault_root, yesterday, surviving)

    # ---------------------------------------------------------------------- #
    # Step 5 — Re-index MEMORY.md                                             #
    # ---------------------------------------------------------------------- #
    memory_path = vault_root / "MEMORY.md"
    index_file(memory_path, vault_root, conn)
    conn.commit()

    # ---------------------------------------------------------------------- #
    # Step 6 — Check conflicts (read-only) + write proposals                  #
    # ---------------------------------------------------------------------- #
    # Import proposals helper
    try:
        _scripts_parent = Path(__file__).resolve().parent.parent
        import sys as _sys
        if str(_scripts_parent) not in _sys.path:
            _sys.path.insert(0, str(_scripts_parent))
        from proposals import write_proposal  # type: ignore
        _has_proposals = True
    except ImportError:
        _has_proposals = False

    yesterday_str = yesterday.strftime("%Y-%m-%d")
    today_start_ts = time.mktime(date.today().timetuple())
    new_chunk_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM chunks WHERE path LIKE ? AND created_at > ?",
            ("%MEMORY.md%", today_start_ts),
        ).fetchall()
    ]

    all_conflicts: list[dict] = []
    for cid in new_chunk_ids:
        all_conflicts.extend(check_conflicts(cid, conn))

    if _has_proposals:
        for conflict in all_conflicts:
            old_row = conn.execute("SELECT content FROM chunks WHERE id = ?", (conflict["old_id"],)).fetchone()
            new_row = conn.execute("SELECT content FROM chunks WHERE id = ?", (conflict["new_id"],)).fetchone()
            write_proposal(
                "reflect-conflict",
                {
                    "old_chunk_id": conflict["old_id"],
                    "new_chunk_id": conflict["new_id"],
                    "old_content": old_row[0] if old_row else "",
                    "new_content": new_row[0] if new_row else "",
                    "reason": conflict["reason"],
                },
                "reflect.py",
                f"Conflict: {conflict['old_id']} vs {conflict['new_id']}",
            )
        for mistake in buckets["mistakes"]:
            write_proposal(
                "reflect-mistake",
                {"description": mistake, "context": yesterday_str, "suggested_category": "debugging"},
                "reflect.py",
                mistake[:60],
            )
        for problem in buckets["open_problems"]:
            write_proposal(
                "reflect-mistake",
                {"description": problem, "context": yesterday_str, "suggested_category": "debugging"},
                "reflect.py",
                problem[:60],
            )

    conn.commit()
    conn.close()

    # ---------------------------------------------------------------------- #
    # Step 7 — Update HEARTBEAT.md                                            #
    # ---------------------------------------------------------------------- #
    _write_heartbeat(
        vault_root,
        run_dt,
        yesterday,
        facts_extracted,
        facts_categorized,
        facts_written,
        all_conflicts,
    )

    return {
        "facts_extracted": facts_extracted,
        "facts_categorized": facts_categorized,
        "conflicts_found": len(all_conflicts),
        "facts_written": facts_written,
    }


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the daily reflection pipeline for the second brain."
    )
    parser.add_argument(
        "--vault",
        default=str(_VAULT_ROOT),
        help=f"Path to vault root (default: {_VAULT_ROOT})",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite database (default: auto-detected from project root)",
    )
    parser.add_argument(
        "--date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Target date to reflect on (default: yesterday)",
    )
    args = parser.parse_args()

    vault_root = Path(args.vault)

    if args.db is not None:
        db_path = Path(args.db)
    else:
        # Auto-detect: project_root/data/memory.sqlite
        db_path = _PROJECT_ROOT / "data" / "memory.sqlite"

    target_date: date | None = None
    if args.date:
        try:
            target_date = date.fromisoformat(args.date)
        except ValueError:
            print(f"[reflect] ERROR: Invalid date format '{args.date}'. Use YYYY-MM-DD.", file=sys.stderr)
            sys.exit(1)

    result = run_reflection(vault_root, db_path, target_date)

    print(
        f"Reflection complete: {result['facts_extracted']} facts extracted, "
        f"{result['facts_categorized']} categorized, "
        f"{result['facts_written']} written, "
        f"{result['conflicts_found']} conflicts"
    )

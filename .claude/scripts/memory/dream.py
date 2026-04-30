"""
Daily reflection pipeline for the personal second-brain.

Runs at 8AM daily. Reads yesterday's daily log, extracts facts with Haiku,
categorizes them with Sonnet, appends to vault/Memory/<group>/<category>.md,
appends lessons to vault/RULES.md, and updates HEARTBEAT.md.
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
    return start.resolve()


_PROJECT_ROOT = _find_project_root(Path(__file__))
_VAULT_ROOT = _PROJECT_ROOT / "vault"


# --------------------------------------------------------------------------- #
# Category parsing                                                              #
# --------------------------------------------------------------------------- #

def _parse_categories_yml(yaml_content: str) -> dict[str, dict]:
    """Parse _categories.yml into {id: {label, reflection_prompt}} using regex."""
    result: dict[str, dict] = {}
    entries = re.split(r'\n\s*-\s+id:', yaml_content)
    for entry in entries[1:]:
        id_match = re.match(r'\s*(\S+)', entry)
        if not id_match:
            continue
        cat_id = id_match.group(1)

        label_match = re.search(r'\n\s+label:\s+(.+)', entry)
        label = label_match.group(1).strip().strip('"\'') if label_match else cat_id.replace('-', ' ').title()

        prompt_match = re.search(r'\n\s+reflection_prompt:\s+"([^"]*)"', entry)
        if not prompt_match:
            prompt_match = re.search(r"\n\s+reflection_prompt:\s+'([^']*)'", entry)
        if not prompt_match:
            prompt_match = re.search(r'\n\s+reflection_prompt:\s+(.+)', entry)
        reflection_prompt = (
            prompt_match.group(1).strip().strip('"\'')
            if prompt_match
            else f"Extract facts related to {cat_id}."
        )

        result[cat_id] = {"label": label, "reflection_prompt": reflection_prompt}
    return result


def _load_categories(vault_root: Path) -> list[dict]:
    """Discover categories from vault/Memory/ folder structure + _categories.yml metadata.

    Flat .md files in memory_root and .md files in group subdirs are both categories.
    _categories.yml provides label and reflection_prompt metadata.
    """
    memory_root = vault_root / "Memory"

    yml_meta: dict[str, dict] = {}
    try:
        yaml_content = (memory_root / "_categories.yml").read_text(encoding="utf-8")
        yml_meta = _parse_categories_yml(yaml_content)
    except FileNotFoundError:
        pass

    folder_ids: list[str] = []
    seen_folder: set[str] = set()
    if memory_root.exists():
        # Flat .md files directly in memory root
        for md_file in sorted(memory_root.glob("*.md")):
            if not md_file.name.startswith("_"):
                cat_id = md_file.stem
                if cat_id not in seen_folder:
                    folder_ids.append(cat_id)
                    seen_folder.add(cat_id)
        # .md files inside group subdirs
        for item in sorted(memory_root.iterdir()):
            if not item.is_dir() or item.name.startswith('_'):
                continue
            for md_file in sorted(item.glob("*.md")):
                cat_id = md_file.stem
                if cat_id not in seen_folder:
                    folder_ids.append(cat_id)
                    seen_folder.add(cat_id)
            for cat_dir in sorted(item.iterdir()):
                if cat_dir.is_dir() and not cat_dir.name.startswith('_'):
                    if cat_dir.name not in seen_folder:
                        folder_ids.append(cat_dir.name)
                        seen_folder.add(cat_dir.name)

    result: list[dict] = []
    for cat_id in folder_ids:
        meta = yml_meta.get(cat_id, {})
        result.append({
            "id": cat_id,
            "label": meta.get("label", cat_id.replace("-", " ").title()),
            "reflection_prompt": meta.get("reflection_prompt", f"Extract any facts related to {cat_id}."),
        })

    for cat_id, meta in yml_meta.items():
        if cat_id not in seen_folder:
            result.append({
                "id": cat_id,
                "label": meta.get("label", cat_id.replace("-", " ").title()),
                "reflection_prompt": meta.get("reflection_prompt", f"Extract any facts related to {cat_id}."),
            })

    if not result:
        return [{"id": "journal", "label": "Journal", "reflection_prompt": "Extract notable facts and learnings."}]

    return result


def _load_category_ids(vault_root: Path) -> list[str]:
    return [c["id"] for c in _load_categories(vault_root)]


# --------------------------------------------------------------------------- #
# Step 2 — Extract facts (Haiku)                                               #
# --------------------------------------------------------------------------- #

def _extract_facts(log_content: str, categories: list[dict]) -> dict:
    """Use Haiku to extract facts from daily log targeting all memory categories.

    Returns {facts: [...], mistakes: [...], open_problems: [...], shortcuts: [...]}.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from claude_cli import call_claude  # type: ignore

    category_guidance = "\n".join(
        f"  - {c['id']}: {c['reflection_prompt']}"
        for c in categories
    )

    system = "You are a memory extraction assistant for a personal second brain."
    user = (
        "Extract information from this daily log. Look for content relevant to ANY of these memory categories:\n"
        f"{category_guidance}\n\n"
        "Output ONLY a valid JSON object with exactly these keys:\n"
        '  "facts": list of strings — ALL items found across ALL categories above. '
        "Each fact must be specific and self-contained. Capture: projects discussed or initiated "
        "(with name and purpose), job applications, interview prep done, career goals stated, "
        "technical decisions, tools adopted or rejected, habits logged, health notes, financial info, "
        "personal relationships mentioned, goals/intentions expressed, things asked to create or set up, "
        "agent/system designs discussed, shortcuts or patterns discovered. Max 30 items.\n"
        '  "mistakes": list of {"description": str, "fix": str, "fix_type": "rule"|"code"|"reminder"} — '
        "errors made + concrete fix stated as an imperative rule. fix_type: rule=behavioral rule, "
        "code=code change needed, reminder=general note. Max 5.\n"
        '  "open_problems": list of {"description": str, "fix": str, "fix_type": "rule"|"code"|"reminder"} — '
        "unresolved issues + proposed solution as imperative. Max 5.\n"
        '  "shortcuts": list of strings — approaches that worked well, time-savers, successful patterns. Max 5.\n'
        "No other text.\n\nDaily log:\n" + log_content
    )

    raw = call_claude(user, system=system, model="haiku")
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    def _normalize_item(item) -> dict:
        if isinstance(item, dict):
            return {
                "description": str(item.get("description", item.get("text", str(item)))),
                "fix": str(item.get("fix", "")),
                "fix_type": str(item.get("fix_type", "reminder")),
            }
        return {"description": str(item), "fix": "", "fix_type": "reminder"}

    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return {
                "facts": [str(f) for f in result.get("facts", [])],
                "mistakes": [_normalize_item(m) for m in result.get("mistakes", [])],
                "open_problems": [_normalize_item(p) for p in result.get("open_problems", [])],
                "shortcuts": [str(s) for s in result.get("shortcuts", [])],
            }
    except json.JSONDecodeError as exc:
        print(f"[reflect] WARNING: JSON parse error in fact extraction: {exc}", file=sys.stderr)
    return {"facts": [], "mistakes": [], "open_problems": [], "shortcuts": []}


# --------------------------------------------------------------------------- #
# Dedup helper                                                                  #
# --------------------------------------------------------------------------- #

def _is_duplicate(fact: str, conn) -> bool:
    """Return True if this fact is already in the DB (exact hash or cosine > 0.95)."""
    import numpy as np
    import sqlite_vec
    from hashlib import sha256 as _sha256

    content_hash = _sha256(fact.encode()).hexdigest()
    row = conn.execute(
        "SELECT 1 FROM chunks WHERE content_hash = ? AND superseded_by IS NULL LIMIT 1",
        (content_hash,),
    ).fetchone()
    if row:
        return True

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

def _categorize_facts(facts: list[str], category_ids: list[str]) -> list[dict]:
    """Use Sonnet to assign each fact a category. Returns list of {fact, category}."""
    if not facts:
        return []

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from claude_cli import call_claude  # type: ignore

    categories_list = ", ".join(category_ids)
    system = "You are organizing personal memory into categories."
    user = (
        f"For each fact, assign it to exactly one category from this list: {categories_list}\n"
        f"Output ONLY a valid JSON array of objects with 'fact' and 'category' keys. No other text.\n\n"
        f"Facts:\n{json.dumps(facts)}"
    )

    raw = call_claude(user, system=system, model="sonnet")
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    try:
        categorized = json.loads(raw)
        if not isinstance(categorized, list):
            raise ValueError("Expected JSON array")
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"[reflect] WARNING: JSON parse error in categorization: {exc}", file=sys.stderr)
        return [{"fact": f, "category": "journal"} for f in facts]

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
# Step 4 — Append facts to category .md files                                  #
# --------------------------------------------------------------------------- #

def _build_group_map(vault_root: Path) -> dict[str, str]:
    """Return {category_id: group_dir_name} by scanning vault/Memory/ structure.

    Flat .md files directly in memory_root map to group="".
    .md files inside group subdirs map to that group name.
    """
    memory_root = vault_root / "Memory"
    group_map: dict[str, str] = {}
    if not memory_root.exists():
        return group_map
    # Flat .md files directly in memory root (no group)
    for md_file in memory_root.glob("*.md"):
        if not md_file.name.startswith("_"):
            group_map[md_file.stem] = ""
    # Group subdirs
    for item in sorted(memory_root.iterdir()):
        if not item.is_dir() or item.name.startswith("_"):
            continue
        for md_file in item.glob("*.md"):
            group_map[md_file.stem] = item.name
        for cat_dir in item.iterdir():
            if cat_dir.is_dir() and not cat_dir.name.startswith("_"):
                group_map[cat_dir.name] = item.name
    return group_map


def _append_to_category_file(
    vault_root: Path,
    target_date: date,
    categorized_facts: list[dict],
    fact_type: str = "fact",
) -> tuple[int, list[Path]]:
    """Append facts to vault/Memory/<group>/<category>.md, one section per date.

    Returns (count_written, list_of_modified_file_paths).
    """
    group_map = _build_group_map(vault_root)
    memory_root = vault_root / "Memory"
    date_str = target_date.strftime("%Y-%m-%d")
    written = 0
    modified_paths: list[Path] = []

    # Group by category
    by_cat: dict[str, list[str]] = {}
    for item in categorized_facts:
        by_cat.setdefault(item["category"], []).append(item["fact"])

    for category, facts in by_cat.items():
        group = group_map.get(category, "")
        group_dir = memory_root / group if group else memory_root
        group_dir.mkdir(parents=True, exist_ok=True)
        cat_file = group_dir / f"{category}.md"

        if cat_file.exists():
            existing = cat_file.read_text(encoding="utf-8")
        else:
            existing = f"# {category.replace('-', ' ').title()}\n"

        new_section = f"\n## {date_str}\n" + "".join(f"- {f}\n" for f in facts)
        cat_file.write_text(existing + new_section, encoding="utf-8")
        written += len(facts)
        if cat_file not in modified_paths:
            modified_paths.append(cat_file)

    return written, modified_paths


# --------------------------------------------------------------------------- #
# Rebuild PROJECTS.md from Memory/projects.md                                  #
# --------------------------------------------------------------------------- #

def _update_projects_md(vault_root: Path) -> None:
    """Rebuild vault/PROJECTS.md as a summary by scanning vault/Memory/projects/*.md."""
    projects_dir = vault_root / "Memory" / "projects"
    if not projects_dir.exists():
        return

    lines = ["# Projects — Henry Liao", ""]
    for project_file in sorted(projects_dir.glob("*.md")):
        text = project_file.read_text(encoding="utf-8")
        file_lines = text.splitlines()
        # H1 = project name, first non-empty non-header line = summary
        name = next((l.lstrip("# ").strip() for l in file_lines if l.startswith("# ")), project_file.stem)
        summary = next(
            (l.strip().lstrip("- ").split(".")[0] for l in file_lines if l.strip() and not l.startswith("#")),
            ""
        )
        lines.append(f"## {name}")
        if summary:
            lines.append(summary)
        lines.append("")

    (vault_root / "PROJECTS.md").write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Step 6 — Append lessons to RULES.md                                          #
# --------------------------------------------------------------------------- #

def _append_to_rules_md(
    vault_root: Path,
    target_date: date,
    mistakes: list[dict],
    open_problems: list[dict],
) -> None:
    """Append new rules derived from mistakes/open_problems to vault/RULES.md."""
    rules_path = vault_root / "RULES.md"
    if not rules_path.exists():
        return

    date_str = target_date.strftime("%Y-%m-%d")
    new_rules: list[str] = []

    for item in mistakes:
        desc = item.get("description", "").strip()
        fix = item.get("fix", "").strip()
        if fix and desc:
            new_rules.append(f"- {fix} — {desc}")
        elif fix:
            new_rules.append(f"- {fix}")
        elif desc:
            new_rules.append(f"- Avoid: {desc}")

    for item in open_problems:
        desc = item.get("description", "").strip()
        fix = item.get("fix", "").strip()
        if fix and desc:
            new_rules.append(f"- {fix} — open issue: {desc}")
        elif desc:
            new_rules.append(f"- Investigate: {desc}")

    if not new_rules:
        return

    existing = rules_path.read_text(encoding="utf-8")
    new_section = f"\n## Added {date_str}\n" + "\n".join(new_rules) + "\n"
    rules_path.write_text(existing + new_section, encoding="utf-8")


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

    heartbeat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def _reflect_already_proposed(description: str) -> bool:
    """Return True if this mistake/shortcut was already recorded."""
    needle = description[:60].lower()

    # Check RULES.md first — already captured as a rule
    rules_path = _PROJECT_ROOT / "vault" / "RULES.md"
    if rules_path.exists():
        try:
            rules_text = rules_path.read_text(encoding="utf-8", errors="replace").lower()
            if needle in rules_text:
                return True
        except OSError:
            pass

    # Check drafts proposals
    drafts = _PROJECT_ROOT / "vault" / "drafts"
    for folder in ("proposals", "approved", "rejected"):
        d = drafts / folder
        if not d.exists():
            continue
        for f in d.glob("*.md"):
            try:
                text = f.read_text(encoding="utf-8", errors="replace").lower()
                if needle in text and ("reflect-mistake" in text or "reflect-shortcut" in text):
                    return True
            except OSError:
                pass
    return False


def run_reflection(
    vault_root: Path,
    db_path: Path,
    target_date: date | None = None,
) -> dict:
    """Run full reflection pipeline for target_date (default: yesterday)."""
    try:
        from .db import init_db
        from .indexer import index_file
        from .conflict import check_conflicts
    except ImportError:
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
    date_str = yesterday.strftime('%Y-%m-%d')
    daily_dir = vault_root / "daily"
    # Collect base log + any source-tagged logs (e.g. YYYY-MM-DD-codex-jarvis.md)
    daily_files = sorted(daily_dir.glob(f"{date_str}*.md"))

    if not daily_files:
        print(
            f"[reflect] No daily log found for {date_str}, skipping reflection.",
            file=sys.stderr,
        )
        _write_heartbeat(vault_root, run_dt, yesterday, 0, 0, 0, [])
        return zero_result

    log_content = "\n\n".join(f.read_text(encoding="utf-8") for f in daily_files)
    _ = (vault_root / "HEARTBEAT.md").exists()

    # ---------------------------------------------------------------------- #
    # Step 2 — Extract facts/mistakes/open_problems (Haiku)                  #
    # ---------------------------------------------------------------------- #
    categories = _load_categories(vault_root)
    category_ids = [c["id"] for c in categories]

    buckets = _extract_facts(log_content, categories)
    facts_extracted = (
        len(buckets["facts"])
        + len(buckets["mistakes"])
        + len(buckets["open_problems"])
        + len(buckets.get("shortcuts", []))
    )

    # ---------------------------------------------------------------------- #
    # Step 3 — Categorize facts (Sonnet)                                      #
    # ---------------------------------------------------------------------- #
    categorized = _categorize_facts(buckets["facts"], category_ids)
    facts_categorized = len(categorized)

    # ---------------------------------------------------------------------- #
    # Step 4 — Dedup check + append to category .md files                    #
    # ---------------------------------------------------------------------- #
    conn = init_db(db_path)

    surviving = [item for item in categorized if not _is_duplicate(item["fact"], conn)]
    facts_written, new_paths = _append_to_category_file(vault_root, yesterday, surviving, "fact")

    # ---------------------------------------------------------------------- #
    # Step 5 — Index modified files                                           #
    # ---------------------------------------------------------------------- #
    for path in new_paths:
        index_file(path, vault_root, conn)
    conn.commit()

    # Rebuild PROJECTS.md if any facts went to a project category
    _project_categories = {f.stem for f in (vault_root / "Memory" / "projects").glob("*.md")} if (vault_root / "Memory" / "projects").exists() else set()
    if any(item["category"] in _project_categories for item in surviving):
        _update_projects_md(vault_root)

    # ---------------------------------------------------------------------- #
    # Step 6 — Conflicts + append lessons to RULES.md + shortcuts to snippets #
    # ---------------------------------------------------------------------- #
    try:
        _scripts_parent = Path(__file__).resolve().parent.parent
        import sys as _sys
        if str(_scripts_parent) not in _sys.path:
            _sys.path.insert(0, str(_scripts_parent))
        from proposals import write_proposal  # type: ignore
        _has_proposals = True
    except ImportError:
        _has_proposals = False

    today_start_ts = time.mktime(date.today().timetuple())
    new_chunk_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM chunks WHERE created_at > ?",
            (today_start_ts,),
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
                "dream.py",
                f"Conflict: {conflict['old_id']} vs {conflict['new_id']}",
            )

    # Mistakes + open_problems → RULES.md
    new_mistakes = []
    new_open_problems = []
    for item in buckets["mistakes"]:
        if _reflect_already_proposed(item["description"]):
            print(f"[reflect] Skip duplicate mistake: {item['description'][:60]}", file=sys.stderr)
            continue
        new_mistakes.append(item)
        print(f"[reflect] Adding rule from mistake: {item['description'][:60]}", file=sys.stderr)
    for item in buckets["open_problems"]:
        if _reflect_already_proposed(item["description"]):
            print(f"[reflect] Skip duplicate open_problem: {item['description'][:60]}", file=sys.stderr)
            continue
        new_open_problems.append(item)
        print(f"[reflect] Adding rule from open_problem: {item['description'][:60]}", file=sys.stderr)
    _append_to_rules_md(vault_root, yesterday, new_mistakes, new_open_problems)

    # Shortcuts → RULES.md (patterns that worked well)
    new_shortcuts = [s for s in buckets.get("shortcuts", []) if not _reflect_already_proposed(s)]
    if new_shortcuts:
        shortcut_items = [{"description": s, "fix": s, "fix_type": "rule"} for s in new_shortcuts]
        rules_path = vault_root / "RULES.md"
        if rules_path.exists():
            date_str = yesterday.strftime("%Y-%m-%d")
            existing = rules_path.read_text(encoding="utf-8")
            new_section = f"\n## Shortcuts {date_str}\n" + "".join(f"- {s}\n" for s in new_shortcuts)
            rules_path.write_text(existing + new_section, encoding="utf-8")
        for s in new_shortcuts:
            print(f"[reflect] Added shortcut to RULES.md: {s[:60]}", file=sys.stderr)

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

    # ---------------------------------------------------------------------- #
    # Step 8 — Rebuild llmwiki session index                                  #
    # ---------------------------------------------------------------------- #
    import subprocess as _subprocess
    yesterday_str_for_wiki = yesterday.strftime("%Y-%m-%d")
    _subprocess.run(
        f'llmwiki index add "sessions/{yesterday_str_for_wiki}.md" "Session {yesterday_str_for_wiki}: nightly reflect pass"',
        capture_output=True,
        shell=True,
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

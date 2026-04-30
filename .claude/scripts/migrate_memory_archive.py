"""
One-time migration: parse vault/archive/MEMORY_archive_2026-04-29.md,
deduplicate by chunk ID, write each unique fact to the correct
vault/Memory/<group>/<category>/<date>_<type>_<id>.md file.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ARCHIVE = Path(__file__).resolve().parent.parent.parent / "vault" / "archive" / "MEMORY_archive_2026-04-29.md"
MEMORY_ROOT = Path(__file__).resolve().parent.parent.parent / "vault" / "Memory"

GROUP_MAP = {
    "coding-projects": "coding",
    "agent-designs":   "coding",
    "debugging":       "coding",
    "snippets":        "coding",
    "tech-stack":      "coding",
    "prompts":         "coding",
    "finance":         "personal",
    "habits":          "personal",
    "health":          "personal",
    "journal":         "personal",
    "relationships":   "personal",
    "job-hunt":        "career",
    "career-goals":    "career",
    "network":         "career",
    "interview-prep":  "career",
}

# Regex to parse fact lines:
# - [category] fact text <!-- id:XXXXXXXX created:YYYY-MM-DD -->
FACT_RE = re.compile(
    r"^- \[([^\]]+)\]\s+(.+?)\s+<!--\s+id:(\S+)\s+created:(\d{4}-\d{2}-\d{2})\s+-->$"
)


def fact_type_from(category: str, text: str) -> str:
    if text.startswith("[mistake]"):
        return "mistake"
    if text.startswith("[open-problem]"):
        return "open-problem"
    if category == "snippets":
        return "shortcut"
    return "fact"


def migrate() -> None:
    text = ARCHIVE.read_text(encoding="utf-8", errors="replace")
    seen_ids: set[str] = set()
    written = 0
    skipped_dup = 0
    skipped_exists = 0

    for line in text.splitlines():
        m = FACT_RE.match(line.strip())
        if not m:
            continue
        category, fact_text, chunk_id, date_str = m.groups()
        category = category.strip()

        # Deduplicate by ID
        if chunk_id in seen_ids:
            skipped_dup += 1
            continue
        seen_ids.add(chunk_id)

        group = GROUP_MAP.get(category, "")
        cat_dir = MEMORY_ROOT / group / category if group else MEMORY_ROOT / category
        cat_dir.mkdir(parents=True, exist_ok=True)

        ftype = fact_type_from(category, fact_text)
        filepath = cat_dir / f"{date_str}_{ftype}_{chunk_id}.md"

        if filepath.exists():
            skipped_exists += 1
            continue

        filepath.write_text(
            f"---\ntype: {ftype}\ncategory: '{category}'\ndate: {date_str}\nid: {chunk_id}\n---\n{fact_text}\n",
            encoding="utf-8",
        )
        written += 1

    print(f"Migration complete: {written} written, {skipped_dup} deduped, {skipped_exists} already existed")


if __name__ == "__main__":
    migrate()

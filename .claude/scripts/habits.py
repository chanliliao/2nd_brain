"""Habit auto-detection and HABITS.md checkbox updater.

Checks Henry's 4 daily pillars against observable signals in the vault
and updates the checkboxes in vault/HABITS.md. Called by the heartbeat.

Signals:
  Coding     — #habit/coding tag OR coding-time pattern (≥2h) in daily log
  AI Study   — #ai-learning tag + ≥500 words in Learning section of daily log
  Job Hunt   — vault/Memory/job-hunt/ contains a file dated today
  Reflection — daily log has a ## Reflection section
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path


def _find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return start.resolve()


_PROJECT_ROOT = _find_project_root(Path(__file__))
_VAULT_ROOT = _PROJECT_ROOT / "vault"


# --------------------------------------------------------------------------- #
# Individual pillar checks                                                      #
# --------------------------------------------------------------------------- #

def check_coding_habit(vault_root: Path, today: date) -> bool:
    """True if today's daily log signals ≥2h of focused coding."""
    daily_path = vault_root / "daily" / f"{today.strftime('%Y-%m-%d')}.md"
    if not daily_path.exists():
        return False
    content = daily_path.read_text(encoding="utf-8")
    if "#habit/coding" in content:
        return True
    # e.g. "2h coding", "3.5 hours build", "coding: 2h"
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*h(?:ours?)?\s+(?:coding|build|dev|programming)",
        content,
        re.IGNORECASE,
    )
    if match and float(match.group(1)) >= 2.0:
        return True
    match2 = re.search(
        r"(?:coding|build|dev|programming)[:\s]+(\d+(?:\.\d+)?)\s*h",
        content,
        re.IGNORECASE,
    )
    if match2 and float(match2.group(1)) >= 2.0:
        return True
    return False


def check_ai_study_habit(vault_root: Path, today: date) -> bool:
    """True if today's daily log has #ai-learning tag and ≥500 words of learning content."""
    daily_path = vault_root / "daily" / f"{today.strftime('%Y-%m-%d')}.md"
    if not daily_path.exists():
        return False
    content = daily_path.read_text(encoding="utf-8")
    if "#ai-learning" not in content:
        return False
    learning_match = re.search(
        r"## Learning(.*?)(?=^##|\Z)", content, re.DOTALL | re.MULTILINE
    )
    if learning_match:
        return len(learning_match.group(1).split()) >= 500
    # Fallback: if the full log has #ai-learning and is long enough
    return len(content.split()) >= 500


def check_job_hunt_habit(vault_root: Path, today: date) -> bool:
    """True if a job-hunt memory file dated today was written."""
    job_hunt_dir = vault_root / "Memory" / "job-hunt"
    if not job_hunt_dir.exists():
        return False
    today_str = today.strftime("%Y-%m-%d")
    return any(
        f.name.startswith(today_str) and f.suffix == ".md"
        for f in job_hunt_dir.iterdir()
        if f.is_file()
    )


def check_reflection_habit(vault_root: Path, today: date) -> bool:
    """True if today's daily log contains a ## Reflection section."""
    daily_path = vault_root / "daily" / f"{today.strftime('%Y-%m-%d')}.md"
    if not daily_path.exists():
        return False
    return "## Reflection" in daily_path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Aggregate detector                                                            #
# --------------------------------------------------------------------------- #

def detect_habits(
    vault_root: Path = _VAULT_ROOT,
    today: date | None = None,
) -> dict[str, bool]:
    """Run all 4 pillar checks. Returns {pillar_name: completed}."""
    if today is None:
        today = date.today()
    return {
        "Coding": check_coding_habit(vault_root, today),
        "AI Study": check_ai_study_habit(vault_root, today),
        "Job Hunt": check_job_hunt_habit(vault_root, today),
        "Reflection": check_reflection_habit(vault_root, today),
    }


# --------------------------------------------------------------------------- #
# HABITS.md updater                                                             #
# --------------------------------------------------------------------------- #

def update_habits_md(
    habits: dict[str, bool],
    vault_root: Path = _VAULT_ROOT,
) -> None:
    """Overwrite checkbox states in vault/HABITS.md for each pillar.

    Only modifies lines that start with '- [ ]' or '- [x]' and contain
    the bold pillar name. Does not touch the Streak Tracking table or Notes.
    """
    habits_path = vault_root / "HABITS.md"
    if not habits_path.exists():
        return

    content = habits_path.read_text(encoding="utf-8")
    pillar_markers = {
        "Coding": "**Coding**",
        "AI Study": "**AI Study**",
        "Job Hunt": "**Job Hunt**",
        "Reflection": "**Reflection**",
    }

    lines = content.splitlines()
    updated: list[str] = []
    for line in lines:
        new_line = line
        for pillar, marker in pillar_markers.items():
            if marker in line and re.match(r"\s*- \[[ x]\]", line):
                if habits.get(pillar, False):
                    new_line = re.sub(r"^(\s*- )\[ \]", r"\1[x]", line)
                else:
                    new_line = re.sub(r"^(\s*- )\[x\]", r"\1[ ]", line)
                break
        updated.append(new_line)

    habits_path.write_text("\n".join(updated) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    results = detect_habits()
    for name, done in results.items():
        mark = "✓" if done else "○"
        print(f"  {mark} {name}")
    update_habits_md(results)
    print("HABITS.md updated.")

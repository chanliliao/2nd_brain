"""
prune.py — Remove low-value indexed chunks and archive old drafts.

Pruning criteria:
  - importance < 0.2 AND age_days > 90 AND (tag IS NULL OR tag != '#keep')

Only UNINDEX chunks (remove from chunk_vectors + chunks_fts).
NEVER delete from chunks table — raw metadata stays.

Archiving:
  - Move sent drafts older than 30 days from vault/drafts/sent/ to vault/drafts/archive/
  - Age determined by YAML frontmatter created: field; falls back to file mtime
"""

import sys
import re
import shutil
import sqlite3
from pathlib import Path

# Allow running as a script directly (not only as a module)
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    __package__ = "scripts.memory"


def _find_project_root() -> Path:
    """Walk up from __file__ to find project root (containing .claude/)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("Could not find project root (no .claude/ directory found)")


def find_prunable(conn: sqlite3.Connection) -> list[str]:
    """Return list of chunk IDs matching prune criteria.

    Criteria: importance < 0.2 AND age_days > 90 AND (tag IS NULL OR tag != '#keep')
    Only returns IDs that exist in chunk_vectors (i.e., currently indexed).

    Args:
        conn: SQLite connection to the memory database

    Returns:
        List of chunk IDs to prune
    """
    query = """
    SELECT c.id
    FROM chunks c
    INNER JOIN chunk_vectors cv ON c.id = cv.chunk_id
    WHERE c.importance < 0.2
      AND (unixepoch() - c.created_at) / 86400.0 > 90
      AND (c.tag IS NULL OR c.tag != '#keep')
    """
    cursor = conn.execute(query)
    return [row[0] for row in cursor.fetchall()]


def prune(conn: sqlite3.Connection, dry_run: bool = True) -> int:
    """Remove prunable chunks from chunk_vectors + chunks_fts only.

    Does NOT delete from chunks table. Raw metadata stays—just won't be retrieved.

    Args:
        conn: SQLite connection to the memory database
        dry_run: If True, reports only; no deletions

    Returns:
        Count of chunks unindexed
    """
    prunable = find_prunable(conn)
    count = len(prunable)

    if not dry_run and count > 0:
        for chunk_id in prunable:
            conn.execute("DELETE FROM chunk_vectors WHERE chunk_id = ?", (chunk_id,))
            conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk_id,))
        conn.commit()

    return count


def apply_chunks(ids: list[str], conn: sqlite3.Connection) -> int:
    """Delete indexed data for given chunk IDs. Called after Henry approves a prune proposal."""
    for chunk_id in ids:
        conn.execute("DELETE FROM chunk_vectors WHERE chunk_id = ?", (chunk_id,))
        conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk_id,))
    conn.commit()
    return len(ids)


def archive_old_drafts(vault_root: Path, dry_run: bool = True) -> int:
    """Move sent drafts older than 30 days to archive.

    A draft's age is determined by YAML frontmatter created: field (ISO date string).
    If no frontmatter, falls back to file mtime.
    Never deletes—only moves. Creates vault/drafts/archive/ if needed.

    Args:
        vault_root: Path to vault directory (e.g., /project/vault)
        dry_run: If True, reports only; no moves

    Returns:
        Count of files moved (or would be moved in dry_run)
    """
    from datetime import datetime, timedelta

    sent_dir = vault_root / "drafts" / "sent"
    archive_dir = vault_root / "drafts" / "archive"

    # Handle missing sent directory gracefully
    if not sent_dir.exists():
        return 0

    # Create archive directory if needed (only in non-dry-run)
    if not dry_run and not archive_dir.exists():
        archive_dir.mkdir(parents=True, exist_ok=True)

    cutoff = datetime.now() - timedelta(days=30)
    count = 0

    # Parse YAML frontmatter for created: date
    pattern = re.compile(r'^created:\s*(\d{4}-\d{2}-\d{2})', re.MULTILINE)

    for draft_file in sent_dir.glob("*"):
        if not draft_file.is_file():
            continue

        created_date = None

        # Try to extract created date from YAML frontmatter
        try:
            with open(draft_file, "r", encoding="utf-8") as f:
                first_500 = f.read(500)
            match = pattern.search(first_500)
            if match:
                date_str = match.group(1)
                created_date = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            pass

        # Fall back to file mtime if no frontmatter date
        if not created_date:
            mtime = draft_file.stat().st_mtime
            created_date = datetime.fromtimestamp(mtime)

        # Check if older than 30 days
        if created_date < cutoff:
            count += 1
            if not dry_run:
                dest = archive_dir / draft_file.name
                shutil.move(str(draft_file), str(dest))

    return count


def main() -> None:
    """CLI entry point."""
    import argparse
    from .db import init_db

    parser = argparse.ArgumentParser(
        description="Prune low-value chunks and archive old drafts"
    )
    parser.add_argument(
        "--db",
        default=None,
        metavar="PATH",
        help="Path to SQLite database (default: project/data/memory.sqlite)",
    )
    parser.add_argument(
        "--vault",
        default=None,
        metavar="PATH",
        help="Path to vault directory (default: project/vault)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually prune and archive (default: dry-run only)",
    )
    parser.add_argument(
        "--propose",
        action="store_true",
        help="Write a prune-set proposal instead of pruning (requires approval)",
    )

    args = parser.parse_args()

    # Find project root and set defaults
    root = _find_project_root()
    db_path = Path(args.db) if args.db else root / ".claude" / "data" / "memory.sqlite"
    vault_path = Path(args.vault) if args.vault else root / "vault"

    dry_run = not args.execute
    mode = "DRY RUN" if dry_run else ""

    # Prune chunks
    conn = init_db(db_path)

    if args.propose:
        prunable_ids = find_prunable(conn)
        if not prunable_ids:
            print("No prunable chunks found — no proposal written.")
            conn.close()
            return

        # Build chunk details for the proposal payload
        chunks_detail = []
        for cid in prunable_ids:
            row = conn.execute(
                "SELECT path, content, importance, (unixepoch() - created_at) / 86400.0 FROM chunks WHERE id = ?",
                (cid,),
            ).fetchone()
            if row:
                chunks_detail.append({
                    "id": cid,
                    "path": row[0],
                    "content_preview": row[1][:80],
                    "importance": row[2],
                    "age_days": int(row[3]),
                })
        conn.close()

        # Import proposals (handle direct vs module execution)
        try:
            import sys as _sys
            _sys.path.insert(0, str(Path(__file__).parent.parent))
            from proposals import write_proposal
        except ImportError as e:
            print(f"Cannot import proposals: {e}", file=sys.stderr)
            return

        path = write_proposal(
            "prune-set",
            {"chunks": chunks_detail},
            "prune.py",
            f"Prune {len(chunks_detail)} low-value chunks",
        )
        print(f"Proposal written: {path}")
        print(f"Run: python .claude/scripts/proposals.py approve {path}")
        return

    try:
        pruned = prune(conn, dry_run=dry_run)
    finally:
        conn.close()

    # Archive drafts
    archived = archive_old_drafts(vault_path, dry_run=dry_run)

    # Print output
    if mode:
        print(f"[{mode}] Prunable chunks: {pruned}")
        print(f"[{mode}] Old drafts to archive: {archived}")
    else:
        print(f"Prunable chunks: {pruned}")
        print(f"Old drafts to archive: {archived}")


if __name__ == "__main__":
    main()

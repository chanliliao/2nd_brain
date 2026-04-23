"""
dedup.py — Deduplication utilities for the memory chunk store.

Two strategies:
  1. Exact dedup: find rows with the same content_hash, keep the oldest.
  2. Semantic dedup: find pairs with cosine similarity > threshold, keep the oldest.

CLI usage:
  python dedup.py [--db PATH] [--threshold 0.95] [--execute]

Default behaviour is a dry-run (no DB changes). Pass --execute to delete duplicates.
"""

import argparse
import sqlite3
import sys
import warnings
from pathlib import Path

# Allow running as a script directly (not only as a module)
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    __package__ = "scripts.memory"


# ---------------------------------------------------------------------------
# Exact duplicates
# ---------------------------------------------------------------------------

def find_exact_duplicates(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Return [(duplicate_id, canonical_id), ...].

    Same content_hash, different id.  Canonical = lower created_at (older row kept).
    Rows with a NULL content_hash are ignored.
    """
    rows = conn.execute(
        """
        SELECT id, content_hash, created_at
        FROM chunks
        WHERE content_hash IS NOT NULL
        ORDER BY content_hash, created_at ASC
        """
    ).fetchall()

    # Group by content_hash; first row in each group is canonical (oldest created_at)
    seen: dict[str, str] = {}   # content_hash -> canonical_id
    duplicates: list[tuple[str, str]] = []

    for chunk_id, content_hash, _created_at in rows:
        if content_hash not in seen:
            seen[content_hash] = chunk_id
        else:
            duplicates.append((chunk_id, seen[content_hash]))

    return duplicates


# ---------------------------------------------------------------------------
# Semantic duplicates
# ---------------------------------------------------------------------------

def find_semantic_duplicates(
    conn: sqlite3.Connection,
    threshold: float = 0.95,
) -> list[tuple[str, str]]:
    """Return [(near_duplicate_id, canonical_id), ...] where cosine_sim > threshold.

    Canonical = lower created_at. Pairs already identified as exact duplicates are
    skipped.  Only chunks created in the last 90 days are considered.  Aborts (with
    a warning) if more than 500 qualifying chunks are present.
    """
    import numpy as np

    # Collect the exact-duplicate set so we can skip those pairs
    exact_pairs = find_exact_duplicates(conn)
    exact_dup_ids: set[str] = {dup_id for dup_id, _ in exact_pairs}

    cutoff = conn.execute("SELECT unixepoch() - 90 * 86400").fetchone()[0]

    rows = conn.execute(
        """
        SELECT cv.chunk_id, cv.embedding, c.created_at
        FROM chunk_vectors cv
        JOIN chunks c ON c.id = cv.chunk_id
        WHERE c.created_at >= ?
        ORDER BY c.created_at ASC
        """,
        (cutoff,),
    ).fetchall()

    if not rows:
        return []

    if len(rows) > 500:
        warnings.warn(
            f"find_semantic_duplicates: {len(rows)} chunks exceed the 500-chunk limit. "
            "Skipping semantic dedup to keep runtime reasonable.",
            RuntimeWarning,
            stacklevel=2,
        )
        return []

    # Deserialise embeddings
    chunk_ids: list[str] = []
    created_ats: list[float] = []
    embeddings: list = []

    for chunk_id, emb_bytes, created_at in rows:
        chunk_ids.append(chunk_id)
        created_ats.append(created_at)
        embeddings.append(np.frombuffer(emb_bytes, dtype=np.float32))

    mat = np.stack(embeddings)  # shape (N, 384)

    # L2-normalise rows so cosine similarity == dot product
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)  # avoid division by zero
    mat_normed = mat / norms

    duplicates: list[tuple[str, str]] = []

    # O(N^2) upper-triangle scan — acceptable for N <= 500
    for i in range(len(chunk_ids)):
        for j in range(i + 1, len(chunk_ids)):
            sim = float(np.dot(mat_normed[i], mat_normed[j]))
            if sim <= threshold:
                continue

            id_i = chunk_ids[i]
            id_j = chunk_ids[j]

            # Skip pairs that are already exact duplicates
            if id_i in exact_dup_ids or id_j in exact_dup_ids:
                continue

            # Canonical = older (smaller created_at = index i, since rows are
            # sorted ASC by created_at)
            canonical_id = id_i if created_ats[i] <= created_ats[j] else id_j
            duplicate_id = id_j if canonical_id == id_i else id_i

            duplicates.append((duplicate_id, canonical_id))

    return duplicates


# ---------------------------------------------------------------------------
# Remove duplicates
# ---------------------------------------------------------------------------

def remove_duplicates(conn: sqlite3.Connection, dry_run: bool = True) -> dict:
    """Find exact + semantic duplicates and optionally delete them.

    In dry_run=False, DELETE duplicate rows from chunks, chunk_vectors, and
    chunks_fts (in that order, to respect foreign-key-like dependencies).

    Returns {'exact': N, 'semantic': M} with the counts of pairs found.
    """
    exact_pairs = find_exact_duplicates(conn)
    semantic_pairs = find_semantic_duplicates(conn)

    result = {"exact": len(exact_pairs), "semantic": len(semantic_pairs)}

    if dry_run:
        return result

    all_dup_ids = [dup_id for dup_id, _ in exact_pairs] + [
        dup_id for dup_id, _ in semantic_pairs
    ]

    if not all_dup_ids:
        return result

    for dup_id in all_dup_ids:
        conn.execute("DELETE FROM chunk_vectors WHERE chunk_id = ?", (dup_id,))
        conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (dup_id,))
        conn.execute("DELETE FROM chunks WHERE id = ?", (dup_id,))

    conn.commit()
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("Could not find project root (no .claude/ directory found)")


_ROOT = _find_project_root()
_DB = _ROOT / ".claude" / "data" / "memory.sqlite"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deduplicate memory chunks (exact + semantic).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--db",
        default=str(_DB),
        metavar="PATH",
        help=f"Path to SQLite database (default: {_DB})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.95,
        metavar="FLOAT",
        help="Cosine similarity threshold for semantic dedup (default: 0.95)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete duplicates (default: dry-run only)",
    )
    args = parser.parse_args()

    from .db import init_db

    conn = init_db(Path(args.db))
    try:
        dry_run = not args.execute
        counts = remove_duplicates(conn, dry_run=dry_run)

        mode = "DRY RUN" if dry_run else "EXECUTED"
        print(f"[{mode}] {counts['exact']} exact, {counts['semantic']} semantic duplicates found.")
        if dry_run and (counts["exact"] or counts["semantic"]):
            print("Run with --execute to delete them.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

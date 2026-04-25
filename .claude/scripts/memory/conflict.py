"""
Conflict detection for memory chunks.

Detects when a newly-added chunk contradicts existing chunks using vector
similarity search followed by LLM-based contradiction checking via Haiku.
Superseded chunks are marked in the DB and excluded from search results.
"""

import argparse
import sqlite3
from pathlib import Path

import anthropic

from .db import _DEFAULT_DB_PATH, init_db


def check_conflicts(new_chunk_id: str, conn: sqlite3.Connection) -> list[dict]:
    """Check a newly-added chunk against existing chunks for contradictions.

    Steps:
    1. Fetch new_chunk from chunks table (content, created_at)
    2. Fetch new_chunk embedding from chunk_vectors
    3. Find top-5 similar chunks via chunk_vectors where cosine_sim > 0.80
       (exclude new_chunk_id itself and any already superseded chunks)
    4. For each candidate: call Haiku to check contradiction
    5. For YES contradictions: add to conflicts list (no DB write — caller writes proposal)
    6. Return list of {old_id, new_id, reason} for each conflict found

    Returns [] if new_chunk_id not found or has no embedding.
    """
    import numpy as np
    import sqlite_vec

    # ------------------------------------------------------------------ #
    # 1. Fetch new chunk content                                           #
    # ------------------------------------------------------------------ #
    chunk_row = conn.execute(
        "SELECT content, created_at FROM chunks WHERE id = ?",
        (new_chunk_id,),
    ).fetchone()
    if chunk_row is None:
        return []
    new_content, _created_at = chunk_row

    # ------------------------------------------------------------------ #
    # 2. Fetch new chunk embedding                                         #
    # ------------------------------------------------------------------ #
    vec_row = conn.execute(
        "SELECT embedding FROM chunk_vectors WHERE chunk_id = ?",
        (new_chunk_id,),
    ).fetchone()
    if vec_row is None:
        return []
    new_embedding = list(np.frombuffer(vec_row[0], dtype=np.float32))

    # ------------------------------------------------------------------ #
    # 3. Find top-5 similar chunks (cosine_sim > 0.80)                    #
    # ------------------------------------------------------------------ #
    rows = conn.execute(
        """
        SELECT cv.chunk_id, 1.0 - vec_distance_cosine(cv.embedding, ?) AS sim
        FROM chunk_vectors cv
        JOIN chunks c ON c.id = cv.chunk_id
        WHERE cv.chunk_id != ?
          AND c.superseded_by IS NULL
        ORDER BY sim DESC
        LIMIT 5
        """,
        (sqlite_vec.serialize_float32(new_embedding), new_chunk_id),
    ).fetchall()
    candidates = [(row[0], row[1]) for row in rows if row[1] > 0.80]

    if not candidates:
        return []

    # ------------------------------------------------------------------ #
    # 4 & 5. Call Haiku to check contradiction; update DB if conflict      #
    # ------------------------------------------------------------------ #
    client = anthropic.Anthropic()
    conflicts: list[dict] = []

    for old_chunk_id, _sim in candidates:
        old_row = conn.execute(
            "SELECT content FROM chunks WHERE id = ?",
            (old_chunk_id,),
        ).fetchone()
        if old_row is None:
            continue
        old_content = old_row[0]

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Do these two facts contradict each other? "
                        "Answer YES or NO, then one sentence explaining why.\n\n"
                        f"Fact A: {old_content}\n\n"
                        f"Fact B: {new_content}"
                    ),
                }
            ],
        )
        answer = response.content[0].text.strip()
        is_contradiction = answer.upper().startswith("YES")
        reason = answer  # keep full response

        if is_contradiction:
            conflicts.append(
                {
                    "old_id": old_chunk_id,
                    "new_id": new_chunk_id,
                    "reason": reason,
                }
            )

    return conflicts


def apply_supersede(old_id: str, new_id: str, conn: sqlite3.Connection) -> None:
    """Apply a supersede relationship — called only after Henry approves a reflect-conflict proposal."""
    conn.execute("UPDATE chunks SET superseded_by = ? WHERE id = ?", (new_id, old_id))
    conn.execute("UPDATE chunks SET supersedes = ? WHERE id = ?", (old_id, new_id))
    conn.commit()


def get_conflict_summary(
    conn: sqlite3.Connection, since_ts: float | None = None
) -> list[dict]:
    """Return list of active conflicts for reporting.

    A conflict is a chunk where superseded_by IS NOT NULL.
    Each dict: {id, path, content_preview (first 100 chars), superseded_by, created_at}
    If since_ts provided, only return conflicts newer than since_ts.
    """
    if since_ts is not None:
        rows = conn.execute(
            """
            SELECT id, path, content, superseded_by, created_at
            FROM chunks
            WHERE superseded_by IS NOT NULL
              AND created_at > ?
            ORDER BY created_at DESC
            """,
            (since_ts,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, path, content, superseded_by, created_at
            FROM chunks
            WHERE superseded_by IS NOT NULL
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [
        {
            "id": row[0],
            "path": row[1],
            "content_preview": row[2][:100],
            "superseded_by": row[3],
            "created_at": row[4],
        }
        for row in rows
    ]


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check a chunk for conflicts with existing chunks."
    )
    parser.add_argument("--chunk-id", required=True, help="ID of the newly-added chunk")
    parser.add_argument(
        "--db",
        default=str(_DEFAULT_DB_PATH),
        help="Path to the SQLite database (default: auto-detected)",
    )
    args = parser.parse_args()

    conn = init_db(Path(args.db))
    conflicts = check_conflicts(args.chunk_id, conn)
    conn.close()

    if not conflicts:
        print("No conflicts found.")
    else:
        print(f"Found {len(conflicts)} conflict(s):")
        for c in conflicts:
            print(f"  old_id={c['old_id']}  new_id={c['new_id']}")
            print(f"  reason: {c['reason']}")
            print()

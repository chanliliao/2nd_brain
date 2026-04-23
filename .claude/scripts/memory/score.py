"""
score.py — Importance scoring for memory chunks.

Computes the importance metric based on user signal, reflection rating,
reference count, access frequency, and recency.

Formula:
  importance = 0.30*user_signal + 0.25*reflection_rating
             + 0.20*reference_count_norm + 0.15*access_frequency_norm
             + 0.10*recency_boost

Where:
  - user_signal: from chunks.user_signal (0.0–1.0; #verified tag → 1.0)
  - reflection_rating: from chunks.reflection_rating (0.0–1.0)
  - reference_count_norm: min(reference_count / 10.0, 1.0)
  - access_frequency_norm: min(access_count / 20.0, 1.0)
  - recency_boost: max(0.0, 1.0 - age_days / 90.0)
"""

import sys
from pathlib import Path
from time import time

# Allow running as a script directly
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    __package__ = "scripts.memory"

from .db import init_db, _DEFAULT_DB_PATH


def compute_importance(row: dict) -> float:
    """
    Compute importance from a chunks row dict.

    Pure function, no DB side-effects.

    Args:
        row: Dict with keys:
          - user_signal: float 0.0–1.0
          - reflection_rating: float 0.0–1.0
          - reference_count: int >= 0
          - access_count: int >= 0
          - created_at: float (unix timestamp)
          - tag: str or None

    Returns:
        Float in [0.0, 1.0] representing chunk importance.
    """
    # Extract fields, with safe defaults
    user_signal = float(row.get("user_signal") or 0.0)
    reflection_rating = float(row.get("reflection_rating") or 0.0)
    reference_count = int(row.get("reference_count") or 0)
    access_count = int(row.get("access_count") or 0)
    created_at = float(row.get("created_at") or time())
    tag = row.get("tag")

    # If tag is #verified, override user_signal to 1.0
    if tag == "#verified":
        user_signal = 1.0

    # Clamp inputs to [0, 1]
    user_signal = max(0.0, min(1.0, user_signal))
    reflection_rating = max(0.0, min(1.0, reflection_rating))

    # Normalize reference_count to [0, 1]: cap at 10 refs
    reference_count_norm = min(reference_count / 10.0, 1.0)

    # Normalize access_count to [0, 1]: cap at 20 accesses
    access_frequency_norm = min(access_count / 20.0, 1.0)

    # Recency boost: decay over 90 days
    age_days = (time() - created_at) / 86400.0
    recency_boost = max(0.0, 1.0 - age_days / 90.0)

    # Weighted sum
    importance = (
        0.30 * user_signal
        + 0.25 * reflection_rating
        + 0.20 * reference_count_norm
        + 0.15 * access_frequency_norm
        + 0.10 * recency_boost
    )

    return max(0.0, min(1.0, importance))


def rescore_all(db_path: Path = _DEFAULT_DB_PATH) -> int:
    """
    Recompute importance for all chunks.

    Updates chunks.importance in place. Returns count of updated rows.

    Args:
        db_path: Path to SQLite database (default: from db module)

    Returns:
        Number of chunks updated.
    """
    db_path = Path(db_path)
    conn = init_db(db_path)

    try:
        # Fetch all chunks
        cursor = conn.execute(
            """
            SELECT id, user_signal, reflection_rating, reference_count,
                   access_count, created_at, tag
            FROM chunks
            """
        )
        rows = cursor.fetchall()

        if not rows:
            return 0

        # Compute importance for each row
        updates = []
        for row in rows:
            row_dict = {
                "id": row[0],
                "user_signal": row[1],
                "reflection_rating": row[2],
                "reference_count": row[3],
                "access_count": row[4],
                "created_at": row[5],
                "tag": row[6],
            }
            importance = compute_importance(row_dict)
            updates.append((importance, row[0]))

        # Batch update
        conn.executemany(
            "UPDATE chunks SET importance = ? WHERE id = ?",
            updates,
        )
        conn.commit()

        return len(updates)

    finally:
        conn.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Recompute importance scores for all memory chunks"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=_DEFAULT_DB_PATH,
        metavar="PATH",
        help=f"Path to SQLite database (default: {_DEFAULT_DB_PATH})",
    )

    args = parser.parse_args()

    count = rescore_all(args.db)
    print(f"Updated {count} chunks.")


if __name__ == "__main__":
    main()

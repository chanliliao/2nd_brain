"""
Hybrid search over vault chunks.

Combines vector similarity (cosine, 70%) and BM25 full-text search (30%) to
rank chunks. Returns the top_k results as a list of dicts.
"""

import sqlite3
import sqlite_vec
from pathlib import Path

from .db import init_db
from .embeddings import embed_one


def search(query: str, db_path: Path, top_k: int = 5) -> list[dict]:
    """Hybrid search over vault chunks. Returns top_k results sorted by score.

    Score formula: score = 0.7 * cosine_sim + 0.3 * bm25_score

    Args:
        query:    Natural-language search query.
        db_path:  Path to the SQLite database file.
        top_k:    Number of results to return (default 5).

    Returns:
        List of dicts with keys: id, path, chunk_idx, content, heading, score.
    """
    conn = init_db(db_path)

    # ------------------------------------------------------------------ #
    # 1. Embed query                                                       #
    # ------------------------------------------------------------------ #
    query_vec = embed_one(query)
    query_blob = sqlite_vec.serialize_float32(query_vec)

    # ------------------------------------------------------------------ #
    # 2. Vector search — top-50 by cosine distance                        #
    # ------------------------------------------------------------------ #
    cosine_scores: dict[str, float] = {}
    try:
        rows = conn.execute(
            """
            SELECT c.id, vec_distance_cosine(cv.embedding, ?) AS dist
            FROM chunk_vectors cv
            JOIN chunks c ON cv.chunk_id = c.id
            ORDER BY dist ASC
            LIMIT 50
            """,
            (query_blob,),
        ).fetchall()
        for chunk_id, dist in rows:
            cosine_scores[chunk_id] = 1.0 - dist
    except sqlite3.OperationalError:
        # chunk_vectors table empty or schema mismatch — treat as no results
        pass

    # ------------------------------------------------------------------ #
    # 3. BM25 via FTS5 — top-50 matches                                   #
    # ------------------------------------------------------------------ #
    bm25_norm: dict[str, float] = {}
    try:
        fts_rows = conn.execute(
            """
            SELECT chunk_id, rank
            FROM chunks_fts
            WHERE content MATCH ?
            ORDER BY rank
            LIMIT 50
            """,
            (query,),
        ).fetchall()
        if fts_rows:
            ranks = [r for _, r in fts_rows]
            min_r = min(ranks)
            max_r = max(ranks)
            denom = min_r - max_r + 1e-9  # min_r <= max_r (both negative), so denom >= 1e-9
            for chunk_id, rank in fts_rows:
                # rank is negative; more negative = better match
                # formula: (rank - max_r) / (min_r - max_r) → 1 for best, 0 for worst
                bm25_norm[chunk_id] = (rank - max_r) / denom
    except sqlite3.OperationalError:
        # FTS table empty or query syntax error — treat as no results
        pass

    # ------------------------------------------------------------------ #
    # 4. Merge scores                                                      #
    # ------------------------------------------------------------------ #
    all_chunk_ids = set(cosine_scores) | set(bm25_norm)
    if not all_chunk_ids:
        conn.close()
        return []

    scored: list[tuple[float, str]] = []
    for chunk_id in all_chunk_ids:
        cosine = cosine_scores.get(chunk_id, 0.0)
        bm25 = bm25_norm.get(chunk_id, 0.0)
        final_score = 0.7 * cosine + 0.3 * bm25
        scored.append((final_score, chunk_id))

    # ------------------------------------------------------------------ #
    # 5. Sort descending, take top_k                                       #
    # ------------------------------------------------------------------ #
    scored.sort(key=lambda x: x[0], reverse=True)
    top_ids = [chunk_id for _, chunk_id in scored[:top_k]]
    top_scores = {chunk_id: score for score, chunk_id in scored[:top_k]}

    # ------------------------------------------------------------------ #
    # 6. Fetch full chunk data                                             #
    # ------------------------------------------------------------------ #
    placeholders = ",".join("?" * len(top_ids))
    chunk_rows = conn.execute(
        f"SELECT id, path, chunk_idx, content FROM chunks WHERE id IN ({placeholders})",
        top_ids,
    ).fetchall()

    # ------------------------------------------------------------------ #
    # 7. Update last_accessed and access_count                             #
    # ------------------------------------------------------------------ #
    for chunk_id in top_ids:
        conn.execute(
            "UPDATE chunks SET last_accessed = unixepoch(), access_count = access_count + 1 WHERE id = ?",
            (chunk_id,),
        )
    conn.commit()

    # ------------------------------------------------------------------ #
    # 8. Build result list, sorted by score descending                     #
    # ------------------------------------------------------------------ #
    chunk_map = {row[0]: row for row in chunk_rows}

    results: list[dict] = []
    for chunk_id in top_ids:
        if chunk_id not in chunk_map:
            continue
        cid, path, chunk_idx, content = chunk_map[chunk_id]
        results.append(
            {
                "id": cid,
                "path": path,
                "chunk_idx": chunk_idx,
                "content": content,
                "heading": "",  # not persisted in Phase 3; Phase 3.5 will add it
                "score": top_scores[chunk_id],
            }
        )

    conn.close()
    return results

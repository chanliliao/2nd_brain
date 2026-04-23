import sqlite3
import sqlite_vec
from hashlib import sha256
from pathlib import Path

from .db import init_db
from .chunker import chunk_file
from .embeddings import embed_texts


def index_file(file_path: Path, vault_root: Path, conn: sqlite3.Connection) -> int:
    """Index one file. Returns number of chunks upserted (not skipped)."""
    chunks = chunk_file(file_path)
    if not chunks:
        return 0

    vault_relative_path = str(file_path.relative_to(vault_root))

    # Compute chunk IDs and content hashes
    chunk_ids = []
    content_hashes = []
    for chunk in chunks:
        chunk_id = sha256(f"{vault_relative_path}::{chunk['chunk_idx']}".encode()).hexdigest()[:16]
        content_hash = sha256(chunk["content"].encode()).hexdigest()
        chunk_ids.append(chunk_id)
        content_hashes.append(content_hash)

    # Check existing rows for skip logic
    skip_set = set()
    for i, chunk_id in enumerate(chunk_ids):
        row = conn.execute(
            "SELECT content_hash FROM chunks WHERE id = ?", (chunk_id,)
        ).fetchone()
        if row is not None and row[0] == content_hashes[i]:
            skip_set.add(i)

    # Collect contents for chunks that need upsert
    upsert_indices = [i for i in range(len(chunks)) if i not in skip_set]
    if not upsert_indices:
        return 0

    # Batch embed only the chunks that need upsert (skip unchanged chunks)
    contents = [chunks[i]["content"] for i in upsert_indices]
    embeddings = embed_texts(contents)

    upserted = 0
    for offset, i in enumerate(upsert_indices):
        chunk = chunks[i]
        chunk_id = chunk_ids[i]
        content_hash = content_hashes[i]
        embedding = embeddings[offset]

        # Upsert into chunks table
        conn.execute(
            "INSERT OR REPLACE INTO chunks(id, path, chunk_idx, heading, content, content_hash) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (chunk_id, vault_relative_path, chunk["chunk_idx"], chunk.get("heading"), chunk["content"], content_hash),
        )

        # Upsert into chunk_vectors (delete then insert — sqlite-vec vec0 doesn't support UPDATE)
        conn.execute("DELETE FROM chunk_vectors WHERE chunk_id = ?", (chunk_id,))
        conn.execute(
            "INSERT INTO chunk_vectors(chunk_id, embedding) VALUES(?, ?)",
            (chunk_id, sqlite_vec.serialize_float32(embedding)),
        )

        # Upsert into FTS table
        conn.execute(
            "INSERT OR REPLACE INTO chunks_fts(chunk_id, content) VALUES(?, ?)",
            (chunk_id, chunk["content"]),
        )

        upserted += 1

    return upserted


def index_vault(vault_path: Path, db_path: Path) -> None:
    """Walk vault, index all .md files, print progress to stderr."""
    import sys

    conn = init_db(db_path)

    skip_dirs = {
        vault_path / ".obsidian",
        vault_path / "drafts" / "expired",
    }

    for md_file in sorted(vault_path.rglob("*.md")):
        # Skip files under excluded directories
        should_skip = False
        for skip_dir in skip_dirs:
            try:
                md_file.relative_to(skip_dir)
                should_skip = True
                break
            except ValueError:
                pass
        if should_skip:
            continue

        n = index_file(md_file, vault_path, conn)
        relative = md_file.relative_to(vault_path)
        print(f"Indexed: {relative} ({n} chunks upserted)", file=sys.stderr)
        conn.commit()

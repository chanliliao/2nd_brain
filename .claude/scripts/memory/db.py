from pathlib import Path
import sqlite3

_DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "memory.sqlite"

_DDL_CHUNKS = """
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    chunk_idx INTEGER NOT NULL,
    heading TEXT,
    content TEXT NOT NULL,
    content_hash TEXT,
    created_at REAL DEFAULT (unixepoch()),
    last_accessed REAL,
    access_count INTEGER DEFAULT 0,
    importance REAL DEFAULT 0.5,
    source_ref TEXT,
    trust TEXT DEFAULT 'agent-extracted',
    supersedes TEXT,
    superseded_by TEXT
)
"""

_DDL_CHUNK_VECTORS = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vectors USING vec0(
    chunk_id TEXT PRIMARY KEY,
    embedding float[384]
)
"""

_DDL_CHUNKS_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content,
    chunk_id UNINDEXED
)
"""


def init_db(db_path: Path = _DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Initialize the SQLite database and return an open connection.

    Creates parent directories if needed, enables WAL mode, loads the
    sqlite-vec extension, and creates all required tables idempotently.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    conn.execute("PRAGMA journal_mode=WAL")

    import sqlite_vec
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    conn.execute(_DDL_CHUNKS)
    conn.execute(_DDL_CHUNK_VECTORS)
    conn.execute(_DDL_CHUNKS_FTS)
    conn.commit()

    return conn


if __name__ == "__main__":
    path = _DEFAULT_DB_PATH
    init_db(path)
    print(f"DB initialized at {path}")

"""Quick smoke test — run from project root with venv python."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from memory.search import search
from memory.db import init_db

DB = Path(".claude/data/memory.sqlite")

# --- search test ---
print("=== Search smoke test ===")
results = search("henry", DB, top_k=3)
if results:
    for r in results:
        print(f"  score={r['score']:.3f} | {r['content'][:80]}")
    print(f"PASS: {len(results)} hits")
else:
    print("WARN: no results (vault may be sparse)")

# --- DB chunk count ---
conn = init_db(DB)
count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
vec_count = conn.execute("SELECT COUNT(*) FROM chunk_vectors").fetchone()[0]
conn.close()
print(f"\n=== DB stats ===")
print(f"  chunks: {count}")
print(f"  vectors: {vec_count}")
print("PASS" if vec_count > 0 else "FAIL: no vectors — index may not have run")

"""
query.py — CLI entrypoint for the memory RAG system.

Subcommands:
  search "<query>" [--top-k N]   Search the vector index
  reindex [--vault PATH] [--db PATH]  Rebuild the index from the vault
  stats                          Show database statistics
"""

import sys
from pathlib import Path

# Allow running as a script directly (not only as a module)
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    __package__ = "scripts.memory"

import argparse


def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("Could not find project root (no .claude/ directory found)")


_ROOT = _find_project_root()
_VAULT = _ROOT / "vault"
_DB = _ROOT / ".claude" / "data" / "memory.sqlite"


def cmd_search(args: argparse.Namespace) -> None:
    from .search import search as _search
    results = _search(args.query, _DB, top_k=args.top_k)
    if not results:
        print("No results found.")
        return
    for i, result in enumerate(results, start=1):
        score = result["score"]
        path = result["path"]
        content = result["content"][:300]
        print(f"--- Result {i} (score: {score:.3f}) ---")
        print(f"File: {path}")
        print(content)
        print()


def cmd_reindex(args: argparse.Namespace) -> None:
    from .indexer import index_vault
    vault_path = Path(args.vault) if args.vault else _VAULT
    db_path = Path(args.db) if args.db else _DB
    index_vault(vault_path, db_path)
    print("Reindex complete.")


def cmd_stats(args: argparse.Namespace) -> None:
    from .db import init_db
    conn = init_db(_DB)
    try:
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        vector_count = conn.execute("SELECT COUNT(*) FROM chunk_vectors").fetchone()[0]
        fts_count = conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    finally:
        conn.close()

    db_size_kb = _DB.stat().st_size / 1024

    print(f"Chunks:  {chunk_count}")
    print(f"Vectors: {vector_count}")
    print(f"FTS rows: {fts_count}")
    print(f"DB size: {db_size_kb:.1f} KB")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Memory RAG system CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # search subcommand
    search_parser = subparsers.add_parser("search", help="Search the vector index")
    search_parser.add_argument("query", help="Search query string")
    search_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        metavar="N",
        dest="top_k",
        help="Number of results to return (default: 5)",
    )
    search_parser.set_defaults(func=cmd_search)

    # reindex subcommand
    reindex_parser = subparsers.add_parser(
        "reindex", help="Rebuild the index from the vault"
    )
    reindex_parser.add_argument(
        "--vault",
        default=None,
        metavar="PATH",
        help=f"Path to vault directory (default: {_VAULT})",
    )
    reindex_parser.add_argument(
        "--db",
        default=None,
        metavar="PATH",
        help=f"Path to SQLite database (default: {_DB})",
    )
    reindex_parser.set_defaults(func=cmd_reindex)

    # stats subcommand
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

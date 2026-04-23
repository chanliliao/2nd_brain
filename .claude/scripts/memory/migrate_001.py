"""
Phase 3.5 Schema Migration: Add quality-score columns to chunks table.

This migration adds columns needed for memory quality controls:
  - user_signal: manual signal (e.g. #verified tag gives 1.0)
  - reflection_rating: rating assigned at reflect time
  - reference_count: how many other chunks reference this one
  - tag: free-form tag for chunk protection (#keep prevents pruning)

Usage:
    python migrate_001.py [--db PATH]

If --db is not provided, uses the default database path from db.py.
"""

import argparse
import sqlite3
from pathlib import Path
import sys

from db import init_db, _DEFAULT_DB_PATH


def get_existing_columns(conn: sqlite3.Connection) -> set:
    """Get the set of column names that currently exist in the chunks table."""
    cursor = conn.execute("PRAGMA table_info(chunks)")
    return {row[1] for row in cursor.fetchall()}


def migrate(db_path: Path) -> None:
    """Apply the Phase 3.5 schema migration."""
    db_path = Path(db_path)
    print(f"Connecting to database at {db_path}...")

    # Use init_db to get a properly configured connection with sqlite-vec loaded
    conn = init_db(db_path)

    try:
        existing = get_existing_columns(conn)
        print(f"Existing columns: {sorted(existing)}")

        # Define new columns to add
        new_columns = {
            "user_signal": "REAL DEFAULT 0.0",
            "reflection_rating": "REAL DEFAULT 0.0",
            "reference_count": "INTEGER DEFAULT 0",
            "tag": "TEXT",
        }

        # Track what was added
        added = []
        already_present = []

        # Add columns that don't exist
        for col_name, col_def in new_columns.items():
            if col_name not in existing:
                print(f"Adding column: {col_name}")
                try:
                    conn.execute(f"ALTER TABLE chunks ADD COLUMN {col_name} {col_def}")
                    added.append(col_name)
                except sqlite3.OperationalError as e:
                    print(f"Warning: could not add {col_name}: {e}")
            else:
                already_present.append(col_name)

        # Commit all changes
        conn.commit()

        # Print summary
        print("\n=== Migration Summary ===")
        if added:
            print(f"Added: {', '.join(added)}")
        if already_present:
            print(f"Already present: {', '.join(already_present)}")

        # Verify the final state
        final_columns = get_existing_columns(conn)
        print(f"\nFinal columns: {sorted(final_columns)}")
        print("\nMigration complete!")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Apply Phase 3.5 schema migration for quality-score columns"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=_DEFAULT_DB_PATH,
        help=f"Path to the SQLite database (default: {_DEFAULT_DB_PATH})",
    )

    args = parser.parse_args()

    try:
        migrate(args.db)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

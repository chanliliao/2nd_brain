"""
FastMCP stdio server — Henry's Second Brain memory interface.
All writes go through a proposal queue; nothing lands in memory without approval.
"""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _find_project_root() -> Path:
    """Walk up from this file until we find a directory that contains .claude/."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("Could not locate project root (no .claude/ directory found).")


_PROJECT_ROOT = _find_project_root()
_SCRIPTS_DIR = _PROJECT_ROOT / ".claude" / "scripts"
_DB_PATH = _PROJECT_ROOT / ".claude" / "data" / "memory.sqlite"
_VAULT_ROOT = _PROJECT_ROOT / "vault"
_CATEGORIES_FILE = _VAULT_ROOT / "Memory" / "_categories.yml"
_PROPOSALS_DIR = _VAULT_ROOT / "drafts" / "proposals"

# Make scripts importable
sys.path.insert(0, str(_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP("second-brain")

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_memory(query: str, top_k: int = 5) -> list[dict]:
    """Search Henry's long-term memory vault."""
    from memory.search import search  # type: ignore

    results = search(query, _DB_PATH, top_k=top_k)
    return [
        {"content": r["content"], "path": r["path"], "score": r["score"]}
        for r in results
    ]


@mcp.tool()
def list_categories() -> list[str]:
    """List valid memory categories."""
    if not _CATEGORIES_FILE.exists():
        return []
    text = _CATEGORIES_FILE.read_text(encoding="utf-8")
    # Match lines like `  - id: some-category` or `- id: some-category`
    return re.findall(r"^\s*-?\s*id:\s*(\S+)", text, re.MULTILINE)


@mcp.tool()
def get_recent_daily_logs(days: int = 3) -> str:
    """Get recent daily log content (last N days)."""
    daily_dir = _VAULT_ROOT / "daily"
    parts: list[str] = []
    today = date.today()
    for offset in range(days):
        target = today - timedelta(days=offset)
        log_file = daily_dir / f"{target.isoformat()}.md"
        if log_file.exists():
            parts.append(f"## {target.isoformat()}\n{log_file.read_text(encoding='utf-8')}")
    return "\n\n".join(parts) if parts else "No daily logs found for the requested period."


@mcp.tool()
def propose_memory_fact(
    category: str,
    content: str,
    source_agent: str,
    tags: list[str] = [],
) -> str:
    """Propose adding a fact to memory. Requires Henry's approval."""
    from sanitize import sanitize_text  # type: ignore
    from proposals import write_proposal  # type: ignore

    valid = list_categories()
    if category not in valid:
        raise ValueError(f"Unknown category '{category}'. Valid: {valid}")

    sanitized_content = sanitize_text(content)
    payload = {
        "category": category,
        "content": sanitized_content,
        "tags": tags,
        "source_agent": source_agent,
    }
    path = write_proposal("agent-memfact", payload, f"mcp:{source_agent}", sanitized_content[:60])
    return f"Proposal written — pending Henry's approval: {path}"


@mcp.tool()
def log_agent_session(
    agent_name: str,
    summary: str,
    outcome: str,
    lessons: list[str] = [],
) -> str:
    """Log an agent session for Henry's review."""
    from sanitize import sanitize_text  # type: ignore
    from proposals import write_proposal  # type: ignore

    san_summary = sanitize_text(summary)
    san_outcome = sanitize_text(outcome)
    payload = {
        "agent_name": agent_name,
        "summary": san_summary,
        "outcome": san_outcome,
        "lessons": [sanitize_text(l) for l in lessons],
    }
    path = write_proposal("agent-session-log", payload, f"mcp:{agent_name}", san_summary[:60])
    return f"Session log proposal written — pending Henry's approval: {path}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")

"""
FastMCP stdio server — Henry's Second Brain memory interface.
All writes go through a proposal queue; nothing lands in memory without approval.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import subprocess
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
# HTTP server helpers
# ---------------------------------------------------------------------------

_TAILSCALE_RANGE = ipaddress.ip_network("100.64.0.0/10")


def _is_tailscale(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip) in _TAILSCALE_RANGE
    except ValueError:
        return False


def _resolve_tailscale_ip(host_arg: str | None) -> str:
    try:
        if host_arg is not None:
            if _is_tailscale(host_arg):
                return host_arg
            print(f"Refusing to bind: {host_arg!r} is not a Tailscale IP (100.64.0.0/10).", file=sys.stderr)
            sys.exit(3)

        bind_ip = os.environ.get("MCP_BIND_IP")
        if bind_ip:
            if _is_tailscale(bind_ip):
                return bind_ip
            print(f"Refusing to bind: {bind_ip!r} is not a Tailscale IP (100.64.0.0/10).", file=sys.stderr)
            sys.exit(3)

        result = subprocess.run(
            [r"C:\Program Files\Tailscale\tailscale.exe", "ip", "--4"],
            capture_output=True, text=True, timeout=5
        )
        bind_ip = result.stdout.strip().splitlines()[0].strip() if result.returncode == 0 else ""

        if bind_ip and _is_tailscale(bind_ip):
            return bind_ip

        print("Refusing to bind: no Tailscale IP detected. Is Tailscale running?", file=sys.stderr)
        sys.exit(3)

    except (subprocess.TimeoutExpired, OSError):
        print("Refusing to bind: could not query Tailscale (is it installed?).", file=sys.stderr)
        sys.exit(3)


def _run_http(host: str | None, port: int) -> None:
    import uvicorn
    from starlette.applications import Starlette

    sys.path.insert(0, str(Path(__file__).parent))
    from auth_middleware import BearerAuthMiddleware, Lockout  # type: ignore

    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("project_secrets", _SCRIPTS_DIR / "secrets.py")
    _sm = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_sm)
    secure_read_token = _sm.secure_read_token

    token_data = secure_read_token("mcp_bearer")
    if not token_data or "token" not in token_data:
        print(
            "ERROR: No MCP bearer token found.\n"
            "Run: python .claude/scripts/mcp_bootstrap_token.py",
            file=sys.stderr,
        )
        sys.exit(2)

    expected_token: str = token_data["token"]
    bind_ip = _resolve_tailscale_ip(host)

    # Allow the Tailscale IP as a valid Host header value.
    # DNS rebinding via Tailscale IPs is not a realistic attack vector;
    # Tailscale mesh + bearer token already handle access control.
    from mcp.server.transport_security import TransportSecuritySettings
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[f"{bind_ip}:*"],
        allowed_origins=[f"http://{bind_ip}:*"],
    )

    lockout = Lockout()
    http_app = mcp.streamable_http_app()
    app = Starlette(
        routes=http_app.routes,
        middleware=[],
        lifespan=http_app.router.lifespan_context,
    )
    app.add_middleware(BearerAuthMiddleware, expected_token=expected_token, lockout=lockout)

    print(f"Starting MCP HTTP server on http://{bind_ip}:{port}/mcp", flush=True)
    uvicorn.run(app, host=bind_ip, port=port, log_level="info")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Second Brain MCP Server")
    parser.add_argument("--serve", action="store_true", help="Run HTTP server (Tailscale only)")
    parser.add_argument("--host", default=None, help="Bind IP override (must be Tailscale 100.x.x.x)")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.serve:
        _run_http(args.host, args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

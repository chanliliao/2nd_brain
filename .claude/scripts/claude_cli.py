"""Thin wrapper around the claude CLI for non-interactive LLM calls.

Uses existing Claude Code auth — no ANTHROPIC_API_KEY needed.
"""
import shutil
import subprocess
from pathlib import Path

_CLAUDE_BIN: str | None = None


def _find_claude() -> str:
    found = shutil.which("claude")
    if found:
        return found
    for candidate in [
        Path.home() / ".local" / "bin" / "claude.exe",
        Path.home() / ".local" / "bin" / "claude",
    ]:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(
        "claude CLI not found. Install Claude Code from https://claude.ai/code"
    )


def call_claude(prompt: str, system: str = "", model: str = "haiku", timeout: int = 240) -> str:
    """Run a one-shot prompt via claude -p. Uses existing Claude Code OAuth auth.

    Uses --tools "" to skip tool initialization — significantly faster when run
    from Task Scheduler where plugin/hook startup can exceed 2 minutes otherwise.
    """
    global _CLAUDE_BIN
    if _CLAUDE_BIN is None:
        _CLAUDE_BIN = _find_claude()

    # Embed system prompt in the user message to avoid --system-prompt arg issues
    # on Windows subprocess invocations (large args + potential flag parsing problems).
    full_prompt = f"<system>\n{system}\n</system>\n\n{prompt}" if system else prompt

    cmd = [
        _CLAUDE_BIN, "-p", full_prompt,
        "--model", model,
        "--output-format", "text",
        "--no-session-persistence",
        "--tools", "",          # skip tool init — much faster non-interactive startup
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed (exit {result.returncode}): {result.stderr[:300]}")
    return result.stdout.strip()

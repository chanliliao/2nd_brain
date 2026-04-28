#!/usr/bin/env bash
# rtk_wrap.sh — Run a shell command through rtk-ai if installed, otherwise run it directly.
#
# rtk-ai compresses verbose shell output (git, npm, pytest, etc.) before it reaches
# Claude, saving 60-90% of tokens on noisy commands.
#
# Install:
#   cargo install rtk-ai
#   (requires Rust: https://rustup.rs)
#
# Manual usage:
#   bash .claude/scripts/rtk_wrap.sh "git log --oneline -20"
#   bash .claude/scripts/rtk_wrap.sh "npm install"
#   bash .claude/scripts/rtk_wrap.sh "pytest -v"
#
# Once rtk is on your PATH this wrapper automatically routes through it.
# Until then it falls back to plain bash — no breakage either way.

if [ -z "$1" ]; then
  echo "Usage: rtk_wrap.sh \"<command>\"" >&2
  exit 1
fi

if command -v rtk &>/dev/null; then
  exec rtk bash -c "$1"
else
  exec bash -c "$1"
fi

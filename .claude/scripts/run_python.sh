#!/usr/bin/env bash
# Self-resolving venv python wrapper.
# Finds the venv relative to this script's location — works regardless of
# project path, Windows username, or which machine you're on.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/../venv/Scripts/python.exe" "$@"

# Phase 2 — Hook Dependencies Install Guide

## Prerequisites
- Python 3.10+ at `C:\Users\cliao\AppData\Local\Programs\Python\Python313\python.exe`
- Claude Code CLI installed and in PATH
- Node.js 18+ and npm (for codeburn, Phase 9)

## 1. Python dependencies (hook scripts)

The three hook scripts (`session-start-context.py`, `pre-compact-flush.py`, `session-end-flush.py`) require the `anthropic` Python package.

```
pip install anthropic
```

Or install into a venv (recommended for isolation):
```
python -m venv .claude\venv
.claude\venv\Scripts\activate
pip install anthropic
```

If using a venv, update the Python command in `.claude\settings.json` from `python` to the venv path:
```
C:\Users\cliao\Desktop\2nd_Brain\.claude\venv\Scripts\python.exe
```

## 2. claude-mem (session telemetry memory)

Plugin — AGPL-3.0. Acceptable for personal use.

Install via Claude Code plugin marketplace:
```
claude plugin marketplace add thedotmack/claude-mem
claude plugin install claude-mem
```

Requires:
- Bun runtime (auto-installed by claude-mem)
- Port 37777 must be free

Config at: `~/.claude-mem/settings.json`

## 3. llm-wiki (session → wiki pages)

Syncs past session summaries into `vault/Sessions/` as wiki pages.

```
pip install llm-wiki[all]
llmwiki install-skills
```

After install, `llmwiki sync --quiet` will run on every session start.

## 4. caveman (token compression)

Plugin — compresses MEMORY.md and CLAUDE.md to save tokens.

```
claude plugin marketplace add JuliusBrussee/caveman
claude plugin install caveman@caveman
```

After install, `caveman-session-start` runs on every session start.

## 5. graphify (knowledge graph)

Builds a knowledge graph over the vault.

```
pip install graphifyy
```

Note: The PyPI package name is `graphifyy` (double-y). After install, `graphify-pre-tool` runs before each tool use.

## Verification

After installing all dependencies, open a new Claude Code session in this project. You should see:
1. A `<memory>` block injected at the start of the first turn (from `session-start-context.py`)
2. No hook failure warnings in the session header

To test the hooks manually:
```
# Test session-start-context
python C:\Users\cliao\Desktop\2nd_Brain\.claude\hooks\session-start-context.py

# Test pre-compact (empty transcript)
echo {} | python C:\Users\cliao\Desktop\2nd_Brain\.claude\hooks\pre-compact-flush.py

# Test session-end (empty transcript)
echo {} | python C:\Users\cliao\Desktop\2nd_Brain\.claude\hooks\session-end-flush.py
```

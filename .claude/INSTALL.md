# Second Brain — Setup Guide

Run these steps on **any machine** you clone this repo to.

---

## Prerequisites

- Windows 10+
- Python 3.10+ (installed at system level)
- Node.js 18+ and npm
- Claude Code CLI (`claude`)
- Tailscale (for Computer 2 MCP access)

---

## 1. Clone repo

```bash
git clone <repo-url> C:\Users\<you>\Desktop\2nd_Brain
cd C:\Users\<you>\Desktop\2nd_Brain
```

---

## 2. Python venv

```powershell
python -m venv .claude\venv
.claude\venv\Scripts\activate
pip install -r .claude\requirements.txt
```

**Fix hook paths** — `.claude\settings.json` has hardcoded paths to Computer 1's username.
Find/replace `cliao` with your Windows username in that file before opening Claude Code.

---

## 3. Codeburn (token usage tracking)

```bash
npm install -g codeburn
```

Verify: `codeburn stats`

---

## 4. RTK (token reduction proxy)

Install the `rtk` binary (Rust Token Killer). Get it from your existing Computer 1 installation:

```bash
# On Computer 1 — find the binary
which rtk

# Copy to Computer 2 or reinstall via cargo:
cargo install rtk
```

After install, configure the Claude Code hook in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "rtk intercept" }]
      }
    ]
  }
}
```

---

## 5. Claude Code plugins

```bash
claude plugin marketplace add JuliusBrussee/caveman
claude plugin install caveman@caveman

claude plugin marketplace add thedotmack/claude-mem
claude plugin install claude-mem

pip install llm-wiki[all]
llmwiki install-skills
```

---

## 6. MCP — Second Brain server

### Computer 1 (vault host) — one-time setup

```powershell
# Mint bearer token
.claude\venv\Scripts\python.exe .claude\scripts\mcp_bootstrap_token.py
# Save the printed token — shown once only
```

Register Task Scheduler tasks:

```powershell
# Run as Administrator
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.claude\deploy\install_tasks.ps1
```

### Computer 2 — client config

Create `~/.claude/mcp.json` (never commit this file):

```json
{
  "mcpServers": {
    "second-brain": {
      "type": "streamable-http",
      "url": "http://100.79.45.68:8765/mcp",
      "headers": { "Authorization": "Bearer <paste-token-from-step-above>" }
    }
  }
}
```

The URL is Computer 1's Tailscale IP. Check it with: `tailscale ip --4` on Computer 1.

---

## 7. What runs WHERE

| Feature | Computer 1 | Computer 2 |
|---|---|---|
| Nightly dream pipeline | YES (Task Scheduler 4am) | NO — never register tasks |
| Vault writes | Local + git push | Via MCP → Computer 1 proposals queue |
| Vault reads | Local | `git pull` or MCP `search_memory` |
| Codeburn stats | YES | YES (tracks its own sessions) |
| RTK token reduction | YES | YES |
| Claude Code plugins | YES | YES |

**Single source of truth**: vault lives on Computer 1, replicated to GitHub as backup.
Computer 2 syncs via `git pull`. Both machines push vault changes via normal git workflow.

---

## 8. Vault sync workflow (two computers)

```bash
# Before working on Computer 2:
git pull

# After working on Computer 2:
git add vault/
git commit -m "chore: vault sync $(date +%Y-%m-%d)"
git push

# On Computer 1 — pick up Computer 2 changes:
git pull
```

No merge conflicts if only one computer edits the same file at a time.

---

## Verification

Open Claude Code on Computer 2 in this project. You should see:
1. Memory block injected at session start
2. `mcp__second-brain__*` tools available
3. `codeburn stats` shows session data
4. `rtk gain` shows token savings

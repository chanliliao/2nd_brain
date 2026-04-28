# Setting Up Second Brain on a New Computer

Do these steps in order. Computer 1 (main machine) must already be running with the vault + MCP server.

---

## Prerequisites — install these first

- Windows 10+
- [Python 3.13](https://www.python.org/downloads/) — check "Add to PATH" during install
- [Node.js 18+](https://nodejs.org/) — includes npm
- [Git](https://git-scm.com/)
- [Tailscale](https://tailscale.com/download) — join the same Tailscale network as Computer 1
- [Rust + cargo](https://rustup.rs/) — needed for RTK

---

## Step 1 — Clone the repo

Clone to any path you want — settings are no longer hardcoded to a specific path or username.

```powershell
git clone <your-github-repo-url> C:\Users\<your-username>\Desktop\2nd_Brain
cd C:\Users\<your-username>\Desktop\2nd_Brain
```

---

## Step 2 — Python venv + dependencies

```powershell
python -m venv .claude\venv
.claude\venv\Scripts\activate
pip install -r .claude\requirements.txt
```

The hook scripts in `.claude\scripts\run_python.sh` resolve the venv path relative to the script's own location — no path editing needed.

---

## Step 3 — Codeburn (token usage tracking)

```bash
npm install -g codeburn
```

Verify: `codeburn stats`

---

## Step 4 — RTK (token reduction)

RTK intercepts shell commands and strips Claude's output to save tokens.

```bash
cargo install rtk
```

After install, add the user-level hook to `~/.claude/settings.json`:

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

Verify: `rtk gain`

---

## Step 5 — Claude Code plugins

Install [Claude Code CLI](https://claude.ai/code) first, then:

```bash
# Caveman — compresses prompts to save tokens
claude plugin marketplace add JuliusBrussee/caveman
claude plugin install caveman@caveman

# claude-mem — session telemetry + memory
claude plugin marketplace add thedotmack/claude-mem
claude plugin install claude-mem

# llm-wiki — session summaries → vault wiki pages
pip install llm-wiki[all]
llmwiki install-skills
```

---

## Step 6 — MCP client config (vault access via Computer 1)

Get the bearer token from Computer 1:
```powershell
# On Computer 1
.claude\venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.claude/scripts')
from secrets import secure_read_token
print(secure_read_token('mcp_bearer')['token'])
"
```

Get Computer 1's Tailscale IP:
```powershell
# On Computer 1
tailscale ip --4
```

Create `~/.claude/mcp.json` on this machine — **never commit this file**:

```json
{
  "mcpServers": {
    "second-brain": {
      "type": "streamable-http",
      "url": "http://<computer-1-tailscale-ip>:8765/mcp",
      "headers": { "Authorization": "Bearer <paste-token-here>" }
    }
  }
}
```

Verify — open Claude Code in this project and run:
```
mcp__second-brain__list_categories
```
Should return a list. If it times out, check Tailscale is connected on both machines and the MCP server task is running on Computer 1.

---

## Step 7 — Do NOT register Task Scheduler tasks

The nightly dream pipeline runs on **Computer 1 only** at 4am. Do not run `.claude\deploy\install_tasks.ps1` on this machine.

Running on two machines simultaneously would double-write to vault, double-count codeburn stats, and send duplicate notifications.

---

## Step 8 — Vault sync workflow

Pull before working:
```bash
git pull
```

Push after working:
```bash
git add vault/
git commit -m "chore: vault sync $(date +%Y-%m-%d)"
git push
```

**Rule**: only one machine edits the same vault file at a time.

---

## What each machine does

| Feature | Computer 1 (main) | Computer 2+ |
|---|---|---|
| Vault storage | Local (source of truth) | Git clone (replica) |
| Nightly dream (4am) | YES | NO |
| Vault writes (AI) | Direct | Via MCP → proposals queue on Computer 1 |
| Vault reads | Direct | `git pull` + MCP `search_memory` |
| Codeburn stats | YES (own sessions) | YES (own sessions) |
| RTK token savings | YES | YES |
| Claude Code plugins | YES | YES |
| MCP server | Hosts it | Connects to Computer 1 |

---

## Verification checklist (Claude Code)

- [ ] Session start shows `<memory>` block (hook working)
- [ ] `mcp__second-brain__list_categories` returns categories (MCP connected)
- [ ] `mcp__second-brain__search_memory` returns results
- [ ] `codeburn stats` shows session data
- [ ] `rtk gain` shows token savings
- [ ] Caveman mode activates at session start

---

## Troubleshooting

**MCP connection timeout**: Tailscale not connected, or MCP server task not running on Computer 1.
Check: `schtasks /Query /TN "SecondBrain - MCP Server" /FO LIST` on Computer 1.

**Hook failures at session start**: Venv missing. Re-run Step 2.

**`codeburn` not found**: `npm install -g codeburn` and restart terminal.

**`rtk` not found**: Check `~/.cargo/bin` in PATH. Run `rustup update`.

**Plugin not loading**: `claude plugin list` to confirm install.

---

---

# Codex CLI Setup

Codex is OpenAI's coding agent CLI. The Second Brain vault and MCP server work with Codex too — the nightly pipeline on Computer 1 keeps running regardless of which AI tool you use.

## What transfers to Codex

| Feature | Works in Codex? | Notes |
|---|---|---|
| Vault content | YES | Git sync same as above |
| MCP tools (search, propose) | YES | Codex supports MCP |
| Project instructions | YES | Use `AGENTS.md` instead of `CLAUDE.md` |
| Global instructions | YES | `~/.codex/instructions.md` |
| Nightly dream pipeline | YES | Runs on Computer 1, Codex benefits from results |
| Codeburn tracking | NO | Tracks Claude Code sessions only |
| Caveman plugin | NO | Claude Code plugin |
| claude-mem plugin | NO | Claude Code plugin |
| RTK token reduction | PARTIAL | May work if Codex uses same shell commands |

## Install Codex CLI

```bash
npm install -g @openai/codex
codex login
```

## Project instructions — AGENTS.md

Codex reads `AGENTS.md` in the project root (equivalent to Claude Code's `CLAUDE.md`).
Create it by copying key rules from `CLAUDE.md`:

```bash
cp CLAUDE.md AGENTS.md
```

Then edit `AGENTS.md` to remove Claude-specific sections (skills, slash commands, plugin hooks).
Keep: vault structure, hard limits, commit conventions, MCP tool usage.

## MCP config for Codex

Codex reads MCP servers from `~/.codex/config.toml`. Add the second-brain server:

```toml
[[mcp_servers]]
name = "second-brain"
type = "http"
url = "http://<computer-1-tailscale-ip>:8765/mcp"

[mcp_servers.second-brain.headers]
Authorization = "Bearer <paste-token-here>"
```

Use the same Tailscale IP and bearer token from Step 6 above.

> **Verify the exact config format** before using — run `codex --help` or check the
> [Codex CLI docs](https://github.com/openai/codex) since the config schema may have changed.

## Global instructions for Codex

`~/.codex/instructions.md` is injected into every Codex session (equivalent to global `~/.claude/CLAUDE.md`).
Copy the relevant user-level rules there:

```bash
cp ~/.claude/CLAUDE.md ~/.codex/instructions.md
```

Remove Claude-specific hook/plugin instructions. Keep: commit style, no-inline-secrets rule, vault hard limits.

## Memory injection in Codex

Claude Code injects memory via the `session-start-context.py` hook. Codex has no equivalent hook system.
Instead, rely on MCP: Codex can call `mcp__second-brain__search_memory` at the start of a task to pull relevant context manually.

You can also add a standing instruction to `AGENTS.md`:
```markdown
At the start of every session, call search_memory with a query about the current task
to load relevant context from the Second Brain vault.
```

## Verification checklist (Codex)

- [ ] `codex` command works
- [ ] MCP tools visible: ask Codex to list available MCP tools
- [ ] `search_memory` returns vault results
- [ ] `propose_memory_fact` creates a proposal file in `vault/drafts/proposals/`
- [ ] `AGENTS.md` loaded: Codex follows vault hard limits (no deletes, drafts only)

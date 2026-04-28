# Second Brain — New Computer Setup

**Purpose of this file:** Step-by-step setup guide for any new machine joining the Second Brain system. Written so a human *or* an AI agent can read it and execute all steps end-to-end without ambiguity.

**Prerequisites before starting:**
- Computer 1 (main vault host) must already be running with the MCP server active.
- You need Tailscale installed and connected to the same network as Computer 1.
- You need the bearer token from Computer 1 (retrieve it during Step 6).

---

## System overview

```
Computer 1 (vault host)                    Computer 2+ (this machine)
─────────────────────────────              ──────────────────────────
vault/ (source of truth)     ←─ git ─→    vault/ (replica)
nightly pipeline (4am)                     NO nightly pipeline
MCP HTTP server (Tailscale)  ←─ MCP ─→   Claude Code / Codex
```

---

## Part A — Claude Code Setup

### A1 — System dependencies

Install in this order. Each must succeed before continuing.

```powershell
# 1. Python 3.13 — check "Add to PATH" during installer
# Download: https://www.python.org/downloads/

# 2. Node.js 18+ (includes npm)
# Download: https://nodejs.org/

# 3. Git
# Download: https://git-scm.com/

# 4. Rust (needed for RTK)
# Run in PowerShell:
winget install Rustlang.Rustup
# OR download installer from https://rustup.rs/

# 5. Tailscale
# Download: https://tailscale.com/download/windows
# After install: sign in and join the same tailnet as Computer 1

# 6. Claude Code CLI
npm install -g @anthropic-ai/claude-code
claude login
```

Verify each before continuing:
```bash
python --version        # should print 3.13.x
node --version          # should print v18+
git --version
cargo --version
tailscale status        # should show connected peers including Computer 1
claude --version
```

---

### A2 — Clone the repo

Clone to any path — the project uses self-resolving relative paths, not hardcoded locations.

```bash
git clone <your-github-repo-url> C:\Users\<your-username>\Desktop\2nd_Brain
cd C:\Users\<your-username>\Desktop\2nd_Brain
```

Replace `<your-github-repo-url>` with the GitHub repo URL and `<your-username>` with your Windows username.

---

### A3 — Python venv + dependencies

```bash
python -m venv .claude/venv
.claude/venv/Scripts/activate
pip install -r .claude/requirements.txt
```

Verify:
```bash
.claude/venv/Scripts/python.exe -c "import anthropic, mcp; print('OK')"
```

The hook runner `.claude/scripts/run_python.sh` locates this venv relative to its own path automatically. No path editing needed.

---

### A4 — Codeburn (Claude session token usage tracking)

```bash
npm install -g codeburn
```

Verify: `codeburn stats` (shows "no data" on first install — that is correct)

---

### A5 — RTK (token reduction proxy)

RTK intercepts bash output and strips noise before it reaches Claude, saving 60–90% tokens on verbose commands.

```bash
cargo install rtk
```

After install, add the hook to your **user-level** Claude Code config at `~/.claude/settings.json`.
If the file does not exist, create it. If it exists, merge the `hooks` key into it.

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

Verify: `rtk gain` (shows "no data" on first install — correct)

---

### A6 — Claude Code plugins

Install in this exact order:

```bash
# Caveman — compresses verbose prompts to save tokens
claude plugin marketplace add JuliusBrussee/caveman
claude plugin install caveman@caveman

# claude-mem — session telemetry, feeds memory system
claude plugin marketplace add thedotmack/claude-mem
claude plugin install claude-mem

# llm-wiki — session summaries → vault/Sessions/wiki/ pages
pip install llm-wiki[all]
llmwiki install-skills
```

Verify: `claude plugin list` — all three should appear.

---

### A7 — MCP client config (vault access via Computer 1)

The Second Brain MCP server runs on Computer 1. This machine connects to it over Tailscale.

**Step 1 — Get Computer 1's Tailscale IP:**
```powershell
# Run this ON COMPUTER 1
tailscale ip --4
# Example output: 100.79.45.68
```

**Step 2 — Get the bearer token from Computer 1:**
```powershell
# Run this ON COMPUTER 1
.claude\venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.claude/scripts')
from secrets import secure_read_token
print(secure_read_token('mcp_bearer')['token'])
"
# Prints the 64-character hex token — copy it
```

**Step 3 — Create `~/.claude/mcp.json` on THIS machine:**

This file is gitignored — never commit it.

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

Replace `<computer-1-tailscale-ip>` and `<paste-token-here>` with the values from Steps 1 and 2.

**Verify:**

Open Claude Code in the project directory and run this tool call:
```
mcp__second-brain__list_categories
```
Expected: returns a list of memory categories (career-goals, coding-projects, etc.).
If it times out: check Tailscale is connected and the MCP server task is running on Computer 1.

```powershell
# Check MCP server on Computer 1:
schtasks /Query /TN "SecondBrain - MCP Server" /FO LIST
```

---

### A8 — Do NOT register Task Scheduler tasks

The nightly dream pipeline (heartbeat → graphify → codeburn reflect → memory reflect → log cleanup) runs on **Computer 1 only** at 4am ET.

Do **not** run `.claude\deploy\install_tasks.ps1` on this machine.

Running the pipeline on two machines simultaneously causes:
- Git conflicts in vault/ (both machines write daily logs at the same time)
- Duplicate codeburn stats (heartbeat counted twice)
- Duplicate Windows notifications

---

### A9 — Vault sync workflow

This machine and Computer 1 share the vault via git.

```bash
# Before starting work on this machine:
git pull

# After finishing work on this machine:
git add vault/
git commit -m "chore: vault sync $(date +%Y-%m-%d)"
git push

# On Computer 1, to pick up changes made on this machine:
git pull
```

Rule: edit only one file on one machine at a time to avoid merge conflicts.

---

### A10 — Claude Code verification checklist

Open Claude Code in the project directory (`claude` from the repo root). Confirm all of the following:

- [ ] Session start prints a `<memory>` block (session-start-context.py hook firing)
- [ ] Caveman mode activates ("CAVEMAN MODE ACTIVE" in session header)
- [ ] `mcp__second-brain__list_categories` returns categories
- [ ] `mcp__second-brain__search_memory` with any query returns results
- [ ] `codeburn stats` runs without error
- [ ] `rtk gain` runs without error
- [ ] No hook failure warnings in the session header

---

### Troubleshooting — Claude Code

| Symptom | Fix |
|---|---|
| MCP connection timeout | Check Tailscale connected on both machines; check MCP server task on Computer 1 |
| Hook failure at session start | Venv missing or broken — re-run A3 |
| `codeburn: command not found` | Re-run `npm install -g codeburn`, restart terminal |
| `rtk: command not found` | Check `~/.cargo/bin` in PATH; run `rustup update` |
| Plugin not activating | Run `claude plugin list`; reinstall if missing |
| `run_python.sh: venv not found` | Venv must be at `.claude/venv/` relative to project root |

---

---

## Part B — Codex CLI Setup

Codex is OpenAI's coding agent CLI. The Second Brain vault and MCP server work with Codex — the nightly pipeline on Computer 1 keeps producing vault updates regardless of which AI tool you use day-to-day.

### What transfers to Codex

| Feature | Works in Codex? | Notes |
|---|---|---|
| Vault content | YES | Same git sync as Part A |
| MCP tools (search_memory, propose_memory_fact, etc.) | YES | Codex supports MCP natively |
| Project instructions | YES | `AGENTS.md` at repo root |
| Global instructions | YES | `~/.codex/AGENTS.md` |
| Nightly dream pipeline results | YES | Computer 1 runs it, vault syncs via git |
| Codeburn tracking | NO | Tracks Claude Code sessions only |
| Caveman / claude-mem plugins | NO | Claude Code plugins, no Codex equivalent |
| RTK token reduction | NO | RTK targets Claude Code's Bash tool output |

---

### B1 — Install Codex CLI

```bash
npm install -g @openai/codex
```

Authenticate:
```bash
# Option 1 — browser OAuth (ChatGPT account):
codex login

# Option 2 — API key:
printenv OPENAI_API_KEY | codex login --with-api-key
```

Verify:
```bash
codex login status   # exits 0 if credentials exist
```

---

### B2 — Project instructions (AGENTS.md)

Codex reads `AGENTS.md` at the repo root for project-specific instructions — this is Codex's equivalent of `CLAUDE.md`.

Create it from the existing CLAUDE.md, keeping only the rules that apply to any AI agent:

```bash
cp CLAUDE.md AGENTS.md
```

Then edit `AGENTS.md` and **remove** these Claude-specific sections (Codex ignores them but they add noise):
- Skills / slash commands (`/graphify`, `/gsd:*`)
- Plugin hooks (caveman, claude-mem, llm-wiki)
- References to `settings.json` hook config

**Keep** these sections (they apply to Codex too):
- Vault hard limits (never delete, drafts only, no external posts)
- Commit conventions (conventional commits, no inline secrets)
- MCP tool usage instructions
- Vault structure explanation

---

### B3 — Global instructions

Codex reads `~/.codex/AGENTS.md` for global rules that apply across all projects (equivalent to `~/.claude/CLAUDE.md`).

```bash
# Create the codex home dir if it doesn't exist
mkdir -p ~/.codex

# Copy the global Claude rules as a starting point
cp ~/.claude/CLAUDE.md ~/.codex/AGENTS.md
```

Edit `~/.codex/AGENTS.md` to remove Claude-specific content (hooks, plugins, skills).
Keep the rules that apply to any agent: commit style, no-inline-secrets, vault hard limits.

To temporarily override global rules without deleting the base file:
```bash
# Create override file (takes priority over AGENTS.md):
~/.codex/AGENTS.override.md
```

---

### B4 — MCP config (vault access via Computer 1)

Codex reads MCP server configuration from `~/.codex/config.toml`.
Bearer tokens must be stored in an environment variable — never hardcoded in the TOML file.

**Step 1 — Store the bearer token as a Windows environment variable:**

Get the token from Computer 1 using the same command from A7 Step 2.

```powershell
# Set permanently in Windows user environment:
[System.Environment]::SetEnvironmentVariable(
  "SECOND_BRAIN_MCP_TOKEN",
  "<paste-token-here>",
  "User"
)
# Restart terminal after running this
```

Verify the env var is set:
```bash
echo $SECOND_BRAIN_MCP_TOKEN   # should print the token
```

**Step 2 — Add the server to `~/.codex/config.toml`:**

Option A — using the CLI (recommended, edits config.toml automatically):
```bash
codex mcp add second-brain \
  --url "http://<computer-1-tailscale-ip>:8765/mcp" \
  --bearer-token-env-var SECOND_BRAIN_MCP_TOKEN
```

Option B — edit `~/.codex/config.toml` directly:
```toml
[mcp_servers.second-brain]
url = "http://<computer-1-tailscale-ip>:8765/mcp"
bearer_token_env_var = "SECOND_BRAIN_MCP_TOKEN"
```

Replace `<computer-1-tailscale-ip>` with the IP from A7 Step 1.

**Verify:**
```bash
codex mcp list   # should show second-brain
```

Then start a Codex session and ask it to call `search_memory`. It should return vault results.

---

### B5 — Memory injection in Codex

Claude Code injects memory via the `session-start-context.py` hook. Codex has no equivalent automatic hook for this.

Add this instruction to `AGENTS.md` in the repo root so Codex pulls context at the start of every task:

```markdown
## Memory

At the start of every session, call `search_memory` with a query describing
the current task to load relevant context from the Second Brain vault before
taking any action. Example: if working on the heartbeat script, query
"heartbeat nightly pipeline design decisions".
```

---

### B6 — Vault sync

Same as Claude Code (A9). The vault is shared via git — Codex edits vault files like any other code.

```bash
git pull          # before starting
git add vault/
git commit -m "chore: vault sync $(date +%Y-%m-%d)"
git push          # after finishing
```

---

### B7 — Codex verification checklist

Start a Codex session in the project directory. Confirm:

- [ ] `codex login status` exits 0
- [ ] `codex mcp list` shows `second-brain`
- [ ] Codex can call `search_memory` and returns vault results
- [ ] Codex can call `propose_memory_fact` and a file appears in `vault/drafts/proposals/`
- [ ] Codex respects vault hard limits from `AGENTS.md` (asks before deleting, drafts only for emails)
- [ ] `git pull` before starting work returns latest vault state

---

### Troubleshooting — Codex

| Symptom | Fix |
|---|---|
| MCP server not found | Check `codex mcp list`; re-run B4 |
| Bearer token error | Verify `echo $SECOND_BRAIN_MCP_TOKEN` prints the token; restart terminal after setting env var |
| MCP connection timeout | Check Tailscale connected; check MCP server task on Computer 1 |
| `search_memory` returns empty | Normal if no vault content matches query; try broader query |
| AGENTS.md not loading | Must be at repo root (where `.git/` is); verify with `git rev-parse --show-toplevel` |

---

## Reference — Computer 1 MCP server management

```powershell
# Check MCP server status
schtasks /Query /TN "SecondBrain - MCP Server" /FO LIST

# Start manually if stopped
schtasks /Run /TN "SecondBrain - MCP Server"

# View MCP server logs
Get-Content .claude\data\logs\mcp_server.log -Tail 50
```

Sources:
- [Codex MCP Configuration](https://developers.openai.com/codex/mcp)
- [Codex Config Reference](https://developers.openai.com/codex/config-reference)
- [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
- [Codex CLI Reference](https://developers.openai.com/codex/cli/reference)

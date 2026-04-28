# Setting Up Second Brain on a New Computer

Do these steps in order. Computer 1 (main machine) must already be running with the vault + MCP server.

---

## Prerequisites — install these first

- Windows 10+
- [Python 3.13](https://www.python.org/downloads/) — check "Add to PATH" during install
- [Node.js 18+](https://nodejs.org/) — includes npm
- [Git](https://git-scm.com/)
- [Claude Code CLI](https://claude.ai/code) — install and `claude login`
- [Tailscale](https://tailscale.com/download) — join the same Tailscale network as Computer 1

---

## Step 1 — Clone the repo

```powershell
git clone <your-github-repo-url> C:\Users\<your-username>\Desktop\2nd_Brain
cd C:\Users\<your-username>\Desktop\2nd_Brain
```

Replace `<your-github-repo-url>` with the GitHub URL and `<your-username>` with your Windows username on this machine.

---

## Step 2 — Python venv + dependencies

```powershell
python -m venv .claude\venv
.claude\venv\Scripts\activate
pip install -r .claude\requirements.txt
```

---

## Step 3 — Fix hardcoded paths in settings.json

`.claude\settings.json` has paths hardcoded to Computer 1's Windows username (`cliao`). Fix them for this machine:

```powershell
# Replace 'cliao' with your username everywhere in the file
(Get-Content .claude\settings.json) -replace 'cliao', $env:USERNAME | Set-Content .claude\settings.json
```

Verify the paths look right after:
```powershell
cat .claude\settings.json
```

---

## Step 4 — Codeburn (token usage tracking)

```bash
npm install -g codeburn
```

Verify: `codeburn stats`

---

## Step 5 — RTK (token reduction)

RTK intercepts shell commands and strips Claude's output to save tokens.

```bash
cargo install rtk
```

If Rust/cargo not installed: [install Rust first](https://rustup.rs/)

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

## Step 6 — Claude Code plugins

Install in this order:

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

## Step 7 — MCP client config (vault access via Computer 1)

This connects Claude Code on this machine to Computer 1's Second Brain vault over Tailscale.

Get the bearer token from Computer 1:
```powershell
# On Computer 1 — print the stored token
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

Create `~/.claude/mcp.json` on **this** (new) machine — **never commit this file**:

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

Replace `<computer-1-tailscale-ip>` and `<paste-token-here>` with the values from above.

Verify MCP works — open Claude Code in this project, run:
```
mcp__second-brain__list_categories
```
Should return a list. If it times out, check Tailscale is connected on both machines and the MCP server task is running on Computer 1.

---

## Step 8 — Do NOT register Task Scheduler tasks

The nightly dream pipeline (heartbeat, graphify, codeburn reflect, memory reflect, log cleanup) runs on **Computer 1 only** at 4am. Do not run `.claude\deploy\install_tasks.ps1` on this machine.

Running the pipeline on two machines simultaneously would:
- Double-write to vault (git conflicts)
- Double-count codeburn stats
- Send duplicate notifications

---

## Step 9 — Vault sync workflow

Pull before you start working:
```bash
git pull
```

Push after you finish:
```bash
git add vault/
git commit -m "chore: vault sync $(date +%Y-%m-%d)"
git push
```

On Computer 1 — pick up changes from this machine:
```bash
git pull
```

**Rule**: only one machine edits the same vault file at a time to avoid merge conflicts.

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

## Verification checklist

Open Claude Code in this project and confirm:

- [ ] Session start shows `<memory>` block (session-start-context hook working)
- [ ] `mcp__second-brain__list_categories` returns categories (MCP connected)
- [ ] `mcp__second-brain__search_memory` returns results for a query
- [ ] `codeburn stats` shows session data
- [ ] `rtk gain` shows token savings (or "no data yet" on first session)
- [ ] Caveman mode activates at session start

---

## Troubleshooting

**MCP connection timeout**: Tailscale not connected, or MCP server task not running on Computer 1.
Check on Computer 1: `schtasks /Query /TN "SecondBrain - MCP Server" /FO LIST`

**Hook failures at session start**: Python paths wrong. Re-run Step 3 (path fix).

**`codeburn` not found**: Re-run `npm install -g codeburn` and restart terminal.

**`rtk` not found**: Check `~/.cargo/bin` is in PATH. Run `rustup update`.

**Plugin not loading**: Run `claude plugin list` to confirm install. Re-install if missing.

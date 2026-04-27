# Second Brain — Feature Verification Checklist

Run `.claude/scripts/checks.sh` for a quick green/red summary.
This doc is the detailed reference: what each feature does, how to check it, what healthy looks like.

---

## Quick snapshot

```bash
bash .claude/scripts/checks.sh
```

---

## 1. Vault skeleton

| Check | Command | Healthy = |
|---|---|---|
| 15 Memory folders present | `ls vault/Memory/` | 15 dirs: coding-projects, job-hunt, interview-prep, career-goals, tech-stack, debugging, snippets, prompts, agent-designs, network, relationships, habits, journal, health, finance |
| Daily log exists for today | `ls vault/daily/` | file named `YYYY-MM-DD.md` for today's date |
| Categories config | `cat vault/Memory/_categories.yml` | 15 category entries with id/label/reflection_prompt |

---

## 2. Content RAG (vault search)

**What it does:** Embeds every vault markdown file into SQLite for hybrid vector + full-text search. Claude uses this during sessions to retrieve past facts without re-reading every file.

| Check | Command | Healthy = |
|---|---|---|
| Index has chunks | `python .claude/scripts/memory/query.py stats` | chunk count > 0 |
| Search works | `python .claude/scripts/memory/query.py search "henry job hunt"` | returns snippet citing vault/USER.md or similar |
| Re-index | `python .claude/scripts/memory/query.py reindex` | completes without error |

---

## 3. MCP server (external agent access)

**What it does:** FastMCP server that external agents (and future skills) can call to `search_memory`, `get_recent_daily_logs`, `propose_memory_fact`, `log_agent_session`. Runs in-process via Claude Code.

| Check | Command | Healthy = |
|---|---|---|
| Tool visible in session | open Claude Code → check tool list | `mcp__second-brain__search_memory` present |
| Test a call | in Claude Code: ask "search memory for 'henry'" | response from MCP tool |

---

## 4. Hooks

**What they do:**
- **SessionStart** → injects SOUL/USER/MEMORY/3 daily logs as `<memory>` block + runs llmwiki sync + caveman compression
- **PreToolUse (all)** → blocks `rm`/`del`/`Remove-Item`/`git push -f`; blocks writes outside `vault/` and `.claude/`
- **PreToolUse (Glob|Grep)** → hints about graphify knowledge graph if built
- **PreCompact** → flushes session buffer to today's daily log when `/compact` runs
- **SessionEnd** → flushes session buffer on exit

| Check | Command | Healthy = |
|---|---|---|
| SessionStart injects context | `python .claude/hooks/session-start-context.py` | prints `<memory>` block with SOUL/USER/MEMORY content |
| Guardrail active | in session, attempt `Bash: rm vault/SOUL.md` | hook error: "rm command blocked" |
| PreCompact flushes | run `/compact` in a session | new section added to `vault/daily/YYYY-MM-DD.md` |

---

## 5. Heartbeat (every 30 min, 8AM–10PM ET)

**What it does:** Gathers GitHub PR count, codeburn cost, habit status → diffs against last state → calls Haiku for analysis → writes Windows toast notification → writes `vault/HEARTBEAT.md`.

| Check | Command | Healthy = |
|---|---|---|
| Manually trigger | `python .claude/scripts/heartbeat.py --force --skip-hours-check` | prints `{"status": "ok", ...}` |
| Analysis works | check `vault/HEARTBEAT.md` after force run | `## Analysis` section has real text (not "Analysis unavailable") |
| Toast fires | run `python .claude/scripts/notify.py "test toast"` | Windows notification appears |
| Logs clean | `tail -20 data/logs/heartbeat.log` | no WARNING or ERROR lines |
| State advances | `cat data/state/heartbeat-state.json` | non-empty JSON after a force run |

**If Analysis says "unavailable":** check `data/logs/heartbeat.log` for WARNING lines. The fix (already applied): `claude_cli.py` now uses `--tools ""` + 240s timeout.

---

## 6. Nightly reflection (4:00 AM daily)

**What it does:** Reads yesterday's daily log + any claude-mem session summaries → Haiku extracts facts → Sonnet categorizes into 15 categories → appends to `vault/MEMORY.md` with YAML frontmatter + supersede chain.

**Nightly chain:**
```
03:45  SecondBrain - ClaudeMemBridge  →  appends session summaries to daily log
04:00  SecondBrain - Daily Reflection  →  reads daily log, populates MEMORY.md
04:15  SecondBrain - AutoApprove      →  auto-approves low-risk memory proposals
```

| Check | Command | Healthy = |
|---|---|---|
| Run reflection manually | `python .claude/scripts/memory/reflect.py --date $(date -d yesterday +%F)` (Git Bash) | completes without error |
| MEMORY.md gets entries | open `vault/MEMORY.md` | entries under category sections with YAML frontmatter |
| Scheduled task registered | PowerShell: `schtasks /query /fo TABLE \| findstr /i SecondBrain` | row "SecondBrain - Daily Reflection" |

---

## 7. Weekly maintenance

| Task | Schedule | Check |
|---|---|---|
| Weekly compact (7 dailies → weekly) | Sunday 8 PM | `vault/weekly/YYYY-Www.md` exists for current week |
| Weekly prune (drop low-importance old chunks) | Sunday 11 PM | `python .claude/scripts/memory/prune.py --dry-run` shows candidates |
| Monthly rollup | 1st of month 2 AM | `vault/monthly/YYYY-MM.md` exists for current month |

Manual test: `python .claude/scripts/memory/compact.py --week current`

---

## 8. Habit auto-detection

**What it does:** Reads `vault/HABITS.md`, checks 4 objective pillars: Coding time from claude-mem session duration, AI study from `#ai-learning` tag in daily log, Job Hunt from vault/Memory/job-hunt diff.

| Check | Command | Healthy = |
|---|---|---|
| Detect habits | `python .claude/scripts/habits.py` | prints dict `{"Coding": bool, "AI Study": bool, ...}` |
| HABITS.md updates | run heartbeat with `--force` | `[x]` marks appear next to completed pillars |

---

## 9. Scheduled tasks (the master switch)

**Nothing runs automatically until `install_tasks.ps1` is run as Administrator.**

| Check | Command | Healthy = |
|---|---|---|
| Tasks registered | `schtasks /query /fo TABLE \| findstr /i SecondBrain` (PowerShell) | 7 rows: Heartbeat, Daily Reflection, AutoApprove, Weekly Compact, Weekly Prune, Monthly Rollup, ClaudeMemBridge |
| **Install (one-time, admin required)** | `powershell -ExecutionPolicy Bypass -File .claude/deploy/install_tasks.ps1` | "7 installed, 0 failed" |
| Prereq check | `powershell -ExecutionPolicy Bypass -File .claude/deploy/env_check.ps1` | 0 FAIL before installing |

---

## 10. Token-saving tools

### Caveman (prompt compression)

**What it does:** Compresses MEMORY.md and context files before injection into sessions, saving 60–70% tokens on large memory payloads.

| Check | How | Healthy = |
|---|---|---|
| Plugin installed | `claude plugin list` | shows `caveman` |
| Active this session | look at session-start output | `<memory>` block is present; no caveman errors in session header |
| Manual compress | `/caveman-compress vault/MEMORY.md` | command runs, outputs compressed file |
| Skill present | `.claude/skills/caveman-compress/SKILL.md` exists | file present |

**If not installed:** `claude plugin marketplace add JuliusBrussee/caveman && claude plugin install caveman@caveman`

SessionStart hook wired in `.claude/settings.json`: `caveman-session-start` (graceful — no-ops if plugin absent).

### RTK (shell output compression)

**What it does:** Routes verbose shell commands (git, npm, pytest) through `rtk-ai` before output reaches Claude, saving tokens on noisy commands.

| Check | How | Healthy = |
|---|---|---|
| rtk installed | `rtk --version` | version printed |
| Wrapper works | `bash .claude/scripts/rtk_wrap.sh "echo hi"` | prints `hi` |

**Status:** `rtk_wrap.sh` is a passthrough wrapper — graceful fallback to plain bash if `rtk` not on PATH. Install with `cargo install rtk-ai` (requires Rust).

**Currently not auto-wired** — to use, Henry manually invokes via `bash .claude/scripts/rtk_wrap.sh "your command"`. No hook integration yet.

---

## 11. Codeburn (cost observability)

**What it does:** Parses `~/.claude/` session files locally (no network, no API key) and reports token usage + estimated cost per session.

| Check | Command | Healthy = |
|---|---|---|
| Installed | `codeburn --version` | version printed |
| View usage | `codeburn status --format json` | JSON with total_cost_usd + session_count |
| Weekly report in heartbeat | check `vault/HEARTBEAT.md` → Codeburn line | shows cost summary (not "codeburn not installed") |
| Skill | `/cost-report` in Claude Code session | writes cost summary to today's daily log |

**If not installed:** `npm install -g codeburn` (requires Node 18+)

---

## 12. Claude-mem (session telemetry memory)

**What it does:** Observes every Claude Code tool call via hooks, stores observations in SQLite + Chroma at `~/.claude-mem/`. The `claude_mem_bridge.py` script pulls yesterday's session summaries at 3:45 AM and appends them to the daily log so reflection can read them.

| Check | Command | Healthy = |
|---|---|---|
| Plugin installed | `claude plugin list` | shows `claude-mem` |
| Service running | `curl 127.0.0.1:37777/api/health` | HTTP 200 |
| Bridge works | `python .claude/scripts/claude_mem_bridge.py --date YYYY-MM-DD` | appends `## Claude Sessions` to that day's daily log |
| Scheduled bridge | `schtasks /query \| findstr ClaudeMemBridge` | task row present |

**If not installed:** `claude plugin marketplace add thedotmack/claude-mem && claude plugin install claude-mem`

After installing, claude-mem auto-wires its own hooks (SessionStart, UserPromptSubmit, PostToolUse, PreCompact, SessionEnd, Stop).

---

## 13. LLM-wiki (session → vault wiki)

**What it does:** Converts past Claude Code sessions into structured wiki pages in `vault/Sessions/wiki/`. The SessionStart hook runs `llmwiki sync --quiet` to keep the wiki current.

| Check | Command | Healthy = |
|---|---|---|
| Installed | `llmwiki --version` | version printed |
| Sync runs | `llmwiki sync --quiet` | exits 0; `vault/Sessions/wiki/log.md` gains entries |
| Wiki has content | `cat vault/Sessions/wiki/log.md` | dated entries after each session |
| Hook wired | check `vault/Sessions/wiki/` after opening a new session | new entry for that session |

**If not installed:** `pip install llm-wiki[all] && llmwiki install-skills`

SessionStart hook wired in `.claude/settings.json`: `llmwiki sync --quiet` (graceful — no-ops if not installed).

---

## 14. Graphify (knowledge graph)

**What it does:** Builds a concept knowledge graph over the vault. PreToolUse hook hints Claude to check `graphify-out/GRAPH_REPORT.md` before searching raw files — finds related concepts faster and uses fewer tokens.

| Check | Command | Healthy = |
|---|---|---|
| Installed | `graphifyy --version` or `python -c "import graphifyy"` | no error |
| Graph built | `ls graphify-out/` | `graph.json` + `GRAPH_REPORT.md` present |
| Query works | `graphifyy query "memory architecture"` | returns related nodes |
| Hook fires | open new session + Glob/Grep tool use | session output shows graphify hint |
| Skill | `/graphify-walk memory` in session | returns concept expansion |

**First-time build (run once from project root):**
```bash
graphifyy init .
graphifyy build .
```

Per `CLAUDE.md`: `graphify-out/` has not been built yet. Until built, the hook no-ops silently.

**If not installed:** `pip install graphifyy` (note double-y)

---

## 15. End-to-end "did the night run?" check

Run this each morning to confirm the overnight chain completed:

```bash
# 1. Daily log created
ls vault/daily/ | tail -5

# 2. MEMORY.md was updated (new entries today)
head -50 vault/MEMORY.md

# 3. Heartbeat timestamp is recent
head -3 vault/HEARTBEAT.md

# 4. No errors in heartbeat log
grep -i "warning\|error" data/logs/heartbeat.log | tail -10
```

All four pass = overnight automation working.

---

## One-time setup checklist

Things that cannot be automated — Henry must do these manually once:

- [ ] **Run `install_tasks.ps1` as Administrator** (registers 7 Windows scheduled tasks)
- [ ] **Build graphify graph:** `graphifyy init . && graphifyy build .`
- [ ] **Install claude-mem:** `claude plugin marketplace add thedotmack/claude-mem && claude plugin install claude-mem`
- [ ] **Install caveman:** `claude plugin marketplace add JuliusBrussee/caveman && claude plugin install caveman@caveman`
- [ ] **Install llm-wiki:** `pip install llm-wiki[all] && llmwiki install-skills`
- [ ] **Install codeburn:** `npm install -g codeburn`
- [ ] **Install rtk (optional):** `cargo install rtk-ai` (requires Rust: https://rustup.rs)
- [ ] **Add GitHub PAT to `.env`:** `GITHUB_TOKEN=ghp_...`
- [ ] **Verify prereqs before tasking:** `powershell .claude/deploy/env_check.ps1`

---

*Last updated: 2026-04-26*

# Phase 5 — Skills Starter Pack Design

**Date:** 2026-04-24
**Status:** Approved
**Scope:** 6 Claude Code skills + 3 tool installations

---

## Context

Phases 1–4 are complete: vault structure, hooks, content RAG (SQLite + sqlite-vec + FTS5), memory quality controls, and Gmail/GitHub/Google Calendar integrations. No skills exist yet. Phase 5 teaches Claude Code Henry's vault and gives it reusable, scoped tools.

---

## What We're Building

### Skills (6 of the original 9)

The 3 tool-wrapper skills (`graphify-walk`, `cost-report`, `caveman-compress`) are deferred until after their external tools are confirmed working. The tools themselves are installed in this phase.

| Skill | Type | Trigger |
|---|---|---|
| `vault-structure` | SKILL.md only | reference / context injection |
| `memory-add-category` | SKILL.md only | "add a X category" |
| `learning-log` | SKILL.md only | "log my study session" |
| `memory-search` | SKILL.md + script | `/memory-search "<query>"` |
| `code-review-sweep` | SKILL.md + script | `/code-review-sweep` |
| `draft-email` | SKILL.md + script | `/draft-email <thread_id>` |

### Tools installed (3)

| Tool | Install method | Purpose |
|---|---|---|
| `codeburn` | `npm install -g codeburn` | Weekly cost observability |
| `graphify` | `uv tool install graphifyy` | Knowledge graph over vault |
| `caveman` | Claude plugin (manual) | MEMORY.md token compression |

---

## Directory Structure

```
.claude/skills/
  vault-structure/
    SKILL.md
  memory-add-category/
    SKILL.md
  learning-log/
    SKILL.md
  memory-search/
    SKILL.md
    scripts/
      search_pipeline.py
  code-review-sweep/
    SKILL.md
    scripts/
      sweep.py
  draft-email/
    SKILL.md
    scripts/
      draft.py
```

Skills are invoked via `/` prefix in Claude Code. SKILL.md files follow the standard superpowers skill format. Agentic skill scripts live in `scripts/` alongside their SKILL.md and import from `.claude/scripts/` (memory + integrations modules).

All scripts use `.claude/venv` Python and accept `--debug` flag. Non-zero exit on auth failure so Claude surfaces errors clearly.

---

## Simple Skills (SKILL.md only)

### `vault-structure`

Pure reference document. Content:
- Full folder tree for `vault/` with one-line description per directory
- All 15 category IDs and their `reflection_prompt` descriptions
- Draft lifecycle: `active → sent → expired → archive`
- File naming convention: `YYYY-MM-DD_<type>_<slug>.md`
- `_categories.yml` schema (fields: `id`, `label`, `promote_threshold`, `reflection_prompt`)
- Frontmatter fields used in draft files

No action — loads context so Claude never has to guess paths.

### `memory-add-category`

Triggered by: "add a X category" / "create a new memory category."

Steps encoded in SKILL.md:
1. Append new entry to `vault/Memory/_categories.yml` with all required fields
2. Create `vault/Memory/<id>/` directory with stub `README.md`
3. Confirm what was added (id, label, folder path)

Validates: `id` is kebab-case, `promote_threshold` is a positive integer, `reflection_prompt` is non-empty.

### `learning-log`

Triggered by: "log my study session" / "capture what I learned."

Steps encoded in SKILL.md:
1. Ask: topic, duration (minutes), key takeaways
2. Write structured entry to `vault/daily/YYYY-MM-DD.md` with `#ai-learning` tag
3. Entry targets ≥500 words so reflection's auto-promote threshold is met
4. If today's daily file doesn't exist, create from `vault/daily/template.md` first

---

## Agentic Skills (SKILL.md + scripts)

### `memory-search`

**Invocation:** `/memory-search "<query>"`

**SKILL.md role:** invoke `python .claude/skills/memory-search/scripts/search_pipeline.py "<query>"` and present output.

**`search_pipeline.py` pipeline:**
1. Parse intent: detect temporal cues (last week, this month), category scope (job-hunt, coding-projects), concept vs. factual query
2. Fan out to three backends in parallel:
   - `query.py search "<query>"` — vault RAG (sqlite-vec + FTS5 hybrid)
   - Grep `vault/MEMORY.md` for keyword matches
   - claude-mem MCP tools for session observations (if MCP server running on port 37777)
3. Collect top-20 raw results
4. Pass to Haiku for relevance rerank → top-5 with scores
5. Pass top-5 + original query to Sonnet for synthesized answer with source citations
6. Print synthesis to stdout

**Graceful degradation:** if claude-mem MCP is not running, skip that backend and note it in output. If vault RAG index is empty, fall back to MEMORY.md grep only.

---

### `code-review-sweep`

**Invocation:** `/code-review-sweep`

**SKILL.md role:** invoke `python .claude/skills/code-review-sweep/scripts/sweep.py` and summarize files written.

**`sweep.py` pipeline:**
1. Call `query.py github prs` — PRs where Henry is reviewer or author, excluding drafts
2. For each PR: fetch diff via `github.pr_diff(id)`
3. Pass diff + PR metadata (title, description, changed files) to Sonnet with code-review system prompt
4. Write draft to `vault/drafts/active/YYYY-MM-DD_review_pr-<n>-<slug>.md`

**Draft frontmatter:**
```yaml
---
type: review
pr_id: <n>
repo: <owner/repo>
pr_title: <title>
status: draft
created: YYYY-MM-DD
---
```

5. Print summary: `N drafts written to vault/drafts/active/`

**Hard limit:** never posts. GitHub write operations are not called.

---

### `draft-email`

**Invocation:** `/draft-email <thread_id>` or triggered by heartbeat with a thread ID.

**SKILL.md role:** invoke `python .claude/skills/draft-email/scripts/draft.py <thread_id>` and present draft path.

**`draft.py` pipeline:**
1. Fetch full thread via `query.py gmail thread <thread_id>`
2. Extract sender name/email for voice-match query
3. Search `vault/drafts/sent/` for past emails to same sender (grep frontmatter `recipient` field)
4. Pass thread + voice samples + Henry's SOUL.md excerpt to Sonnet for reply drafting
5. Write draft to `vault/drafts/active/YYYY-MM-DD_email_<slug>.md`

**Draft frontmatter:**
```yaml
---
type: email
thread_id: <id>
recipient: <name> <email>
subject: Re: <original subject>
status: draft
created: YYYY-MM-DD
---
```

6. Print draft path

**Hard limit:** never sends. `gmail.compose` (draft creation in Gmail) is not called — local file only.

---

## Tool Installations

### codeburn (automated)
```bash
npm install -g codeburn
```
Verify: `codeburn status` — parses `~/.claude/` session files locally, no network.

### graphify (automated)
```bash
uv tool install graphifyy
```
Config required: set `multi_agent = true` for parallel subagent extraction (PRD requirement).
Verify: `graphify --version`

### caveman (manual — Claude plugin)
Henry runs in a Claude Code session:
```
/plugin marketplace add JuliusBrussee/caveman
/plugin install caveman@caveman
```
Once installed, caveman activates via SessionStart hook and provides `/caveman-compress` for MEMORY.md compression.

---

## Deferred Skills

These 3 skills are intentionally out of scope for this phase. They will be added once their tools are confirmed working:

| Skill | Depends on |
|---|---|
| `graphify-walk` | graphify installed + indexed |
| `cost-report` | codeburn installed |
| `caveman-compress` | caveman plugin installed |

---

## Success Criteria

- `/memory-search "typescript preference"` returns a synthesized answer citing vault RAG + MEMORY.md
- `/code-review-sweep` fetches Henry's pending PRs and writes draft files to `vault/drafts/active/`
- `/draft-email <id>` writes a voice-matched reply draft, never sends
- "add a travel category" triggers `memory-add-category` — YAML updated, folder created
- "log my study session" triggers `learning-log` — entry with `#ai-learning` lands in today's daily
- `vault-structure` skill loads Henry's vault layout into context when invoked
- `codeburn status` runs without error
- `graphify --version` runs without error
- Caveman install instructions delivered to Henry

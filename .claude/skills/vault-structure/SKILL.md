# Skill: vault-structure

Use this skill whenever you need to understand, navigate, or explain Henry's Obsidian vault layout.

---

## Vault Root

`C:\Users\cliao\Desktop\2nd_Brain\vault\`

| File | Purpose |
|---|---|
| `SOUL.md` | Immutable identity — who Henry is, values, hard limits. Never overwrite. |
| `USER.md` | Evolving profile — current focus, preferences, active projects. Update when Henry shares new context. |
| `MEMORY.md` | Curated facts organized by the 15 categories. Append-only; use supersede chains for contradictions. |
| `HABITS.md` | 4 habit pillars with auto-check state. Heartbeat writes here. |
| `HEARTBEAT.md` | Latest heartbeat output. Overwritten each heartbeat run — do not treat as permanent record. |

---

## Folder Structure

```
vault/
├── SOUL.md
├── USER.md
├── MEMORY.md
├── HABITS.md
├── HEARTBEAT.md
├── daily/           ← YYYY-MM-DD.md  (daily logs)
├── weekly/          ← YYYY-Www.md    (weekly rollups, generated Sunday 8 PM)
├── monthly/         ← YYYY-MM.md     (monthly rollups, generated 1st of month)
├── drafts/
│   ├── active/      ← drafts being worked on
│   ├── sent/        ← drafts Henry has sent (moved here by heartbeat)
│   ├── expired/     ← drafts untouched >24h (moved here by heartbeat)
│   └── archive/     ← permanent archive
├── Sessions/        ← llm-wiki session pages (auto-generated)
└── Memory/
    ├── _categories.yml
    ├── coding-projects/
    ├── job-hunt/
    ├── interview-prep/
    ├── career-goals/
    ├── tech-stack/
    ├── debugging/
    ├── snippets/
    ├── prompts/
    ├── agent-designs/
    ├── network/
    ├── relationships/
    ├── habits/
    ├── journal/
    ├── health/
    └── finance/
```

---

## Memory Categories (15)

| ID | Label | What goes here |
|---|---|---|
| `coding-projects` | Coding Projects | Architecture decisions, blockers, shipped features |
| `job-hunt` | Job Hunt | Applications, recruiter threads, interview notes |
| `interview-prep` | Interview Prep | System design practice, LeetCode patterns, company research |
| `career-goals` | Career Goals | Quarterly OKRs, skills to build, milestones |
| `tech-stack` | Tech Stack | Tool/language choices with rationale, dev env configs |
| `debugging` | Debugging | Bug + root cause + solution (personal Stack Overflow) |
| `snippets` | Snippets | Reusable code patterns with usage context |
| `prompts` | Prompts | System prompts and tool prompts that work |
| `agent-designs` | Agent Designs | Architectures tried, failure modes, lessons learned |
| `network` | Network | People met, mentors, conversation context |
| `relationships` | Relationships | Family, friends, birthdays, recurring context |
| `habits` | Habits | Streaks, triggers, pillar completions |
| `journal` | Journal | Wins, lessons, emotional state, weekly retros |
| `health` | Health | Sleep, workouts, nutrition, symptoms |
| `finance` | Finance | Budget, income, expenses, subscriptions |

The single source of truth is `vault/Memory/_categories.yml`. New categories require a YAML entry there — use the `/memory-add-category` skill.

---

## Draft Lifecycle

```
drafts/active/  →  (Henry sends it)  →  drafts/sent/
             ↘  (>24h untouched)  →  drafts/expired/
                                              ↓
                                        drafts/archive/  (manual, permanent)
```

**Hard rule:** Skills only write to `drafts/active/`. Never write directly to `sent/`, `expired/`, or `archive/`.

### Draft Filename Convention

```
YYYY-MM-DD_<type>_<slug>.md
```

Types: `email`, `pr-review`, `note`

Examples:
- `2026-04-24_email_jane-acme-recruiter.md`
- `2026-04-24_pr-review_42-add-oauth-refresh.md`

Slug rules: lowercase, hyphens (not underscores), no special characters, max 40 chars.

### Draft YAML Frontmatter

```yaml
---
type: email | pr-review | note
source_id: gmail-thread-<id> | github-pr-<number> | manual
recipient: <name or email>         # email drafts only
subject: Re: <original subject>    # email drafts only
pr_url: <url>                      # pr-review drafts only
pr_title: <title>                  # pr-review drafts only
created: YYYY-MM-DD
status: draft
---
```

---

## Daily / Weekly / Monthly Notes

| Path | Format | Created by |
|---|---|---|
| `vault/daily/YYYY-MM-DD.md` | `# YYYY-MM-DD` header + free sections | Hooks + skills |
| `vault/weekly/YYYY-Www.md` | Rollup of 7 daily logs | `compact.py` Sunday 8 PM |
| `vault/monthly/YYYY-MM.md` | Rollup of weekly notes | `compact.py` 1st of month |

When appending to a daily log: if the file doesn't exist, create it with `# YYYY-MM-DD\n\n` as the header first.

---

## Session Wiki Pages

`vault/Sessions/` — auto-populated by llm-wiki at session end. Files follow the pattern `YYYY-MM-DD_claude-session.md`. Do not write here manually.

---

## Naming Rules

- All slugs: lowercase, hyphens not underscores
- Category folder names match the `id` field in `_categories.yml` exactly
- Daily note filenames use ISO 8601: `2026-04-24.md`
- Weekly notes use ISO week: `2026-W17.md`
- Monthly notes: `2026-04.md`

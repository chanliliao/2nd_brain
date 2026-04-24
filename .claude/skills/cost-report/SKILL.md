# Skill: cost-report

Runs codeburn to generate a Claude Code usage cost summary and writes it to today's daily log.

---

## What codeburn does

codeburn parses `~/.claude/` session JSONL files locally. No API keys, no network calls. It reads usage metadata from session files and computes token counts and cost estimates.

Install: `npm install -g codeburn` (requires Node ≥ 18)

---

## When to invoke

- Directly: `/cost-report`
- Called by the Sunday reflection job to append the weekly cost summary to `vault/weekly/YYYY-Www.md`
- Called by heartbeat's weekly state diff

---

## Steps

### Step 1 — Run codeburn

```
codeburn status --format json
```

If codeburn is not installed or fails, say:
> "codeburn is not available. Install it with `npm install -g codeburn`."
Then stop.

### Step 2 — Parse the JSON output

Extract:
- Total tokens this week
- Total estimated cost (USD)
- Number of sessions
- Most expensive session (date + cost)
- Model breakdown if available (Sonnet vs Haiku vs Opus)

### Step 3 — Format the summary

```markdown
## Cost Report — YYYY-MM-DD

| Metric | Value |
|---|---|
| Sessions | N |
| Total tokens | X,XXX,XXX |
| Estimated cost | $X.XX |
| Most expensive session | YYYY-MM-DD ($X.XX) |

**Model breakdown:** Sonnet 4.6: X tokens, Haiku 4.5: X tokens
```

Omit rows where data is unavailable.

### Step 4 — Write to today's daily log

Append the formatted section to `vault/daily/YYYY-MM-DD.md` (use today's actual date).

If today's daily log doesn't exist, create it first:
```markdown
# YYYY-MM-DD

```

Then append the cost report section.

### Step 5 — For Sunday weekly runs

When called as part of the Sunday reflection, also append the same section to `vault/weekly/YYYY-Www.md` under a `## Weekly Cost Summary` heading.

---

## Hard constraints

- Never expose raw API keys or token values from codeburn's internal config
- Write only to `vault/daily/` and `vault/weekly/` — nowhere else
- codeburn is read-only — never pass flags that modify session files

# Skill: code-review-sweep

Henry's flagship productivity skill. Fetches open PRs, generates first-pass review drafts, and saves them to vault. **NEVER posts to GitHub** — Assistant-level hard limit.

---

## Trigger

User says "review my PRs", "do a code review sweep", or invokes `/code-review-sweep`.

---

## Steps

### Step 1 — Fetch open PRs

```
python .claude/scripts/integrations/query.py github prs
```

Returns PRs where Henry is a requested reviewer or author, excluding draft PRs. Output lists each PR with: number, title, repo (`owner/repo`), URL, author, role.

If output shows 0 PRs:
> "No PRs need your review right now."
Then stop.

Otherwise proceed with up to 5 PRs.

---

### Step 2 — For each PR (up to 5), draft a review

Repeat substeps a–d for each PR.

#### 2a. Fetch the diff

```
python .claude/scripts/integrations/query.py github diff <owner/repo> <pr_number>
```

Example: PR #42 in repo `acme/backend` → `query.py github diff acme/backend 42`

The diff is truncated to 4000 characters for large PRs. Work with what's available.

#### 2b. Gather context

From the Step 1 output: PR title, URL, author, repo, Henry's role (reviewer or author).
From the diff: changed files, added/removed lines, overall scope of change.

#### 2c. Draft the review

Produce a structured review with these sections:

**Summary** — What this PR does in 2–3 specific sentences.

**Key changes** — Bullet list grouped by concern area (e.g., API layer, tests, config, dependencies).

**Potential issues** — Flag any of:
- Logic bugs or unhandled edge cases
- Missing error handling (uncaught exceptions, missing null checks)
- Security concerns (unsanitized input, secrets in code, overly broad permissions)
- Style inconsistencies relative to the rest of the diff
- Missing or inadequate test coverage for changed logic

Write "None identified." if nothing concerning is found.

**Suggestions** — Specific, actionable line-level comments:
```
filename.py:L42 — <suggestion>
```
Omit this section entirely if there are no suggestions.

**Verdict** — Exactly one of:
- `LGTM` — no blockers, ready to merge
- `Needs changes` — specific issues must be addressed before merge
- `Needs discussion` — ambiguous design decisions or unclear intent

#### 2d. Write draft to vault

Generate today's date as `YYYY-MM-DD`. Create a slug from the PR title: lowercase, spaces to hyphens, remove special characters, max 40 chars.

Write to:
```
vault/drafts/active/YYYY-MM-DD_pr-review_<pr-number>-<slug>.md
```

File contents:
```markdown
---
type: pr-review
source_id: github-pr-<number>
pr_url: <url>
pr_title: <title>
created: YYYY-MM-DD
status: draft
---

## Summary
<2–3 sentences>

## Key Changes
- <file or area>: <what changed>

## Potential Issues
<issues, or "None identified.">

## Suggestions
<filename:Lxx — suggestion>

## Verdict
<LGTM | Needs changes | Needs discussion>
```

---

### Step 3 — Report to Henry

> "Drafted reviews for N PR(s) — saved to vault/drafts/active/:"

List each draft filename so Henry can locate them quickly.

---

## Hard constraints

- **NEVER** call any GitHub write API — no comments, no approvals, no merge actions
- **NEVER** use `github.py` functions beyond `list_prs_for_review`, `pr_diff`, `list_issues_assigned`
- **NEVER** post a draft to GitHub even if Henry explicitly asks in the same session — redirect him to the draft file
- Always write to `vault/drafts/active/` — nowhere else
- If diff fetch fails for a specific PR, note the failure and continue with remaining PRs
- If 0 PRs are found, stop — do not fabricate PR data

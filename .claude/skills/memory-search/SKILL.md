# Skill: memory-search

Flagship agentic retrieval skill. Searches across all memory backends and synthesizes a cited answer.

---

## Trigger

User asks "what did I...", "do I have notes on...", "what was my decision about...", "find memories about...", "remind me of...", or invokes `/memory-search`.

---

## The Retrieval Loop

Execute **all** steps. Do not short-circuit after finding one result.

---

### Step 1 — Parse intent

From the user's question, extract:

1. **Core concept(s)** — the main thing being queried (e.g., "async patterns", "Acme recruiter", "OAuth setup")
2. **Temporal filter** — any time reference ("last week", "in March", "yesterday", "before the layoff"). If present, pass it to vault RAG — the temporal parser in `search.py` handles natural language and ISO dates.
3. **Category hint** — any domain hint ("my job hunt notes", "coding decisions", "health stuff"). Use this to weight MEMORY.md section scanning.

---

### Step 2 — Query all backends (run A, B, C in parallel where possible)

#### A. MEMORY.md direct scan

Read `vault/MEMORY.md`. Scan sections matching the category hint or concept keywords. MEMORY.md entries are curated and high-trust — prioritize them in synthesis.

#### B. Vault RAG

```
python .claude/scripts/memory/query.py search "<query>" [--limit 20]
```

- Include temporal filter terms in the query string if one was identified
- The CLI returns chunks with: path, chunk_idx, content, importance score, last_accessed
- Chunks from `vault/Memory/` are higher signal than chunks from `vault/daily/` for curated facts

#### C. claude-mem session observations

If claude-mem MCP tools are available in this session (check if `claude-mem` tool calls work), search prior session observations for the concept. This surfaces things Henry said or did in past Claude Code sessions that were never promoted to MEMORY.md.

#### D. graphify expansion (conditional)

Run this **only if** Step B returns fewer than 3 chunks with importance ≥ 0.5:

```
graphify query "<concept>"
```

Use the related nodes to expand the query. Re-run Step B with:
```
python .claude/scripts/memory/query.py search "<original query> <expanded terms>" --limit 20
```

Merge new results with the original result set. Mark chunks found via expansion as `[graphify-expanded]`.

---

### Step 3 — Rerank

Collect all results (up to 20 total across backends). Score each:

| Signal | Weight |
|---|---|
| Relevance to original query | High |
| In curated MEMORY.md | +boost (highest trust) |
| importance field from RAG | Proportional |
| Recency (newer = slightly higher) | Low-medium |
| User-confirmed (`#verified` tag) | +boost |

Keep top 5–8. Discard the rest.

---

### Step 4 — Synthesize

Write a coherent answer that:

1. **Directly answers** the user's question — lead with the answer, then cite evidence
2. **Cites sources** — use inline citations:
   - `[MEMORY.md §Coding Projects]`
   - `[vault/Memory/tech-stack/2026-03-15_typescript-decision.md]`
   - `[session obs: 2026-04-10]`
   - `[graphify-expanded: async → event loop]`
3. **Flags contradictions** — if older and newer entries disagree, say: "Older entry (2026-02-01) says X; newer entry (2026-04-10) supersedes it with Y."
4. **Suggests follow-up** if the answer is incomplete: "I found notes on X but nothing on Y — want me to search more specifically?"

**If nothing is found across all backends:**
> "I don't have a memory about this yet. Want me to create a note?"
Never fabricate memory.

---

### Step 5 — Access stats (automatic)

`query.py search` auto-updates `access_count` and `last_accessed` on retrieved chunks. No extra action needed.

---

## Example

User: `/memory-search "what did I decide about async patterns last month"`

1. Parse: concept = "async patterns", temporal = "last month" (→ March 2026), category hint = tech-stack
2. Backends: scan MEMORY.md §Tech Stack + RAG with `--limit 20` + claude-mem search
3. Rerank: 3 MEMORY.md entries + 4 RAG chunks → keep top 6
4. Synthesize: "In March 2026, you decided to use `asyncio.TaskGroup` for parallel tool calls (MEMORY.md §Tech Stack). You noted aiohttp was preferred over httpx for streaming (vault/Memory/tech-stack/2026-03-12.md). A session observation from 2026-03-18 shows you also evaluated `anyio` but ruled it out due to added complexity."

---

## Hard constraints

- Never fabricate memory — if it's not in any backend, say so
- Always cite sources — unsourced synthesis is not allowed
- Temporal filter must be applied when the user mentions time
- Never write to vault during retrieval — this is a read-only skill

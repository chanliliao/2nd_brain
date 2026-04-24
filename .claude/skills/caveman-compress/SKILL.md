# Skill: caveman-compress

Re-export of caveman's token-compression capability. Invoked when vault files or context files exceed the size cap.

---

## What caveman does

caveman is a Claude Code plugin that compresses large markdown files in-place using LLM summarization. It rewrites verbose content into a denser form while preserving meaning, reducing token cost when those files are loaded into context.

Install: Claude plugin (installed via `claude plugin install`). Activates automatically at session start.

---

## When to invoke

**Automatic triggers (called by other scripts):**
- `session-start-context.py` — if context budget (SOUL + USER + MEMORY + 3 daily logs) exceeds ~2000 tokens, compress MEMORY.md before injecting
- `reflect.py` — after appending to MEMORY.md, if file exceeds ~3000 words, compress it

**Manual trigger:**
- Henry says "compress my memory file", "MEMORY.md is getting too big", or `/caveman-compress`

---

## How to invoke

```
/caveman-compress <file-path>
```

Examples:
```
/caveman-compress vault/MEMORY.md
/caveman-compress vault/USER.md
```

The file is replaced in-place. The original content is compressed; the file path stays the same.

---

## Files that are good candidates

| File | Compress when... |
|---|---|
| `vault/MEMORY.md` | > ~3000 words |
| `vault/USER.md` | > ~1000 words |
| `vault/SOUL.md` | Almost never — it's intentionally concise |
| `vault/daily/YYYY-MM-DD.md` | After compaction into weekly rollup |
| Large vault Memory files | When a category folder has many large notes |

---

## Files to NEVER compress

- `vault/Memory/_categories.yml` — YAML must stay machine-readable; LLM compression will break structure
- Any `.py` script in `.claude/scripts/` — compression corrupts code
- `vault/HEARTBEAT.md` — ephemeral, overwritten each run; compressing it is pointless
- `vault/SOUL.md` — it's the identity anchor; altering it requires explicit user intent, not automatic compression
- Any file in `vault/drafts/` — drafts need to stay verbatim

---

## After compressing a vault markdown file

Re-index the memory database so the compressed version replaces the old chunks:

```
python .claude/scripts/memory/query.py reindex
```

This ensures vault RAG reflects the new compressed content.

---

## Hard constraints

- Never compress a file without confirming the target path is in the allowed list above
- Never compress `.py`, `.json`, `.yaml`/`.yml` files
- After any compression: tell Henry which file was compressed and its approximate size reduction

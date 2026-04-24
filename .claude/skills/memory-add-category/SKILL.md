# Skill: memory-add-category

Henry-triggered skill. Adds a new category to the memory system — one YAML entry + one vault folder + one stub README.

---

## Trigger

User says "add a \<name\> category", "I want to track \<topic\>", "create a new memory category", or invokes `/memory-add-category`.

---

## Steps

### Step 1 — Gather required information

Ask Henry for (or extract from his request if already provided):

| Field | Description | Example |
|---|---|---|
| `id` | Lowercase-hyphen slug. Must match `[a-z][a-z0-9-]+`. | `travel` |
| `label` | Human-readable name for MEMORY.md section headers. | `Travel` |
| `promote_threshold` | Daily mention count before auto-promote to MEMORY.md. Use 1–3. | `2` |
| `reflection_prompt` | Instruction to the reflection agent — what to extract for this category. | `"Extract trips planned, places visited, travel costs, and packing notes."` |

If Henry gives you a casual name (e.g., "travel stuff"), derive a clean id and label and confirm with him before writing.

### Step 2 — Check for duplicates

Read `vault/Memory/_categories.yml`. Scan all existing `id:` entries. If the requested id already exists, tell Henry:
> "A '\<id\>' category already exists. Did you mean a different name?"
Then stop.

### Step 3 — Append to `_categories.yml`

Add the new entry at the end of the `categories:` list, following this exact YAML schema:

```yaml
  - id: <id>
    label: <Label>
    promote_threshold: <n>
    reflection_prompt: "<prompt text>"
```

Preserve all existing entries and formatting. Do not rewrite the file — read it, append the new entry, write it back.

### Step 4 — Create the vault folder

Create the directory:
```
vault/Memory/<id>/
```

### Step 5 — Write stub README

Write `vault/Memory/<id>/README.md`:

```markdown
# <Label>

<reflection_prompt description — restate it as a sentence about what this folder contains>

Files in this folder are auto-populated by the daily reflection agent.
To add a manual note, create a file named `YYYY-MM-DD_<topic>.md` here.
```

### Step 6 — Confirm to Henry

> "Category '\<label\>' added. The reflection agent will start populating vault/Memory/\<id\>/ tomorrow morning at 8 AM."

---

## Hard constraints

- Never skip Step 2 (duplicate check)
- `id` must match `[a-z][a-z0-9-]+` — reject IDs with spaces, underscores, or uppercase
- Only modify `vault/Memory/_categories.yml` and create files in `vault/Memory/<id>/` — no other files
- Do not run `reindex` — the new folder is empty; the indexer will pick it up on the next run

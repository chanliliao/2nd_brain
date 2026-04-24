# Skill: graphify-walk

Thin wrapper around graphify's knowledge-graph query. Use this to expand a concept to related nodes when vault RAG returns sparse results.

---

## What graphify does

graphify (PyPI: `graphifyy`, double-y) builds a knowledge graph over the Obsidian vault. It extracts entities and relationships from vault markdown files and stores them as a graph. Querying it surfaces related concepts that plain vector search might miss — useful for expanding underdetermined queries.

Install: `uv tool install graphifyy`
Config requirement: `multi_agent = true` must be set in graphify's config for parallel subagent extraction.

---

## When to invoke this skill

- Called by **memory-search** when vault RAG returns fewer than 3 chunks with score ≥ 0.5
- Called when a query concept is abstract or has many synonyms (e.g., "async patterns", "job hunt strategy")
- Can be invoked directly: `/graphify-walk <concept>`

---

## Command

```
graphify query "<concept>"
```

Example:
```
graphify query "async patterns"
```

---

## Output format

graphify returns a list of related nodes with relationship labels. Format the output for inclusion in a memory-search response or context block like this:

```
**Related concepts (graphify):** async/await → coroutines, event loop, aiohttp; TaskGroup → concurrency patterns; FastAPI → async routes
```

If graphify returns no results (graph not built yet or concept not in vault), return:
```
**Related concepts (graphify):** none found
```

Do not surface raw graphify JSON to Henry — always format it as the compact inline summary above.

---

## Using the expansion in memory-search

After getting the related concepts, re-run vault RAG with the expanded terms:

```
python .claude/scripts/memory/query.py search "<original query> <expanded terms>"
```

Merge the new results with the original result set before reranking. Attribute any chunks found via expansion with `[graphify-expanded]` in the citation.

---

## Hard constraints

- graphify is read-only — never call any graphify write or rebuild command during retrieval
- If graphify is not installed or the binary isn't on PATH, skip silently and note `[graphify unavailable]` in the response
- Never block memory-search on graphify — it is an optional expansion step

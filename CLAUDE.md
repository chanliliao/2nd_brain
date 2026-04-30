## Memory Lookup Protocol

When Henry asks about his notes, projects, goals, or any personal facts:
1. Check loaded context (`vault/MEMORY.md` facts + `~/.claude/.../memory/` files)
2. If not found → search `vault/Memory/` files (Glob/Grep/Read) before concluding unknown
3. If still not found → tell Henry explicitly and ask him OR offer web search

Never say "I don't know" without checking `vault/Memory/` first.

## graphify

graphify CLI installed (venv). Graph built at `graphify-out/`.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- For cross-module "how does X relate to Y" questions, prefer `/graphify query "<question>"` over grep
- After modifying vault files in this session, run `/graphify --update` to keep the graph current

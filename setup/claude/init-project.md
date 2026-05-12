# Init Project

Initialize a new project's foundational docs from requirement documents.

Pass the paths to your PRD, TRD, and any additional docs as arguments:

```
/init-project docs/PRD.md docs/TRD.md
/init-project docs/PRD.md docs/TRD.md docs/API_SPEC.md docs/DESIGN.md
```

The agent reads all provided documents and generates:
- `docs/TECH_STACK_REF.md` — technology reference
- `docs/ARCHITECTURE.md` — system architecture
- `docs/PROJECT_STATUS.md` — milestones and status tracking
- `CLAUDE.md` — project rules for Claude Code

Existing files are never overwritten — if any target file already exists, it is skipped.

```
Use the Agent tool with subagent_type="project-init" and include the following in the prompt:

"Initialize this project. Read the following requirement documents and generate the foundational project files: $ARGUMENTS"
```

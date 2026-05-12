# Global Codex Instructions

These are the user-level instructions migrated from `~/.claude/CLAUDE.md`.

## Commits

- Write commit messages that describe what changed and why.
- Keep commits focused on one logical change.
- Use conventional prefixes such as `feat:`, `fix:`, `chore:`, `docs:`, `test:`, and `security:`.

## Pull Requests

- Create a PR for changes going to `master` or `main`.
- Never force-push `master` or `main`.
- PR descriptions must include what changed, why it changed, and testing notes.

## Security

- No inline secrets. Put API keys and secrets in `.env` or the appropriate secret store.
- Do not pass user-supplied data directly into shell execution APIs such as `subprocess`.

## Migration Note

- User-level Codex skills live in `~/.agents/skills/`.
- User-level Codex subagents live in `~/.codex/agents/`.
- Legacy Claude assets under `~/.claude/` remain available as source material during the migration period.

---

## 2nd Brain Vault (Long-Term Memory Pipeline)

Henry's 2nd Brain lives at `C:\Users\cliao\Desktop\2nd_Brain\vault\`.
MCP server `secondBrain` is configured globally in `~/.codex/config.toml` and exposes `vault/inbox/` for writing.

### When Henry asks to "connect to vault", "init project with vault", or "set up session logging":

1. Confirm the `secondBrain` MCP is active (it is — configured globally).
2. Create a project-level skill at `.codex/skills/record-session.md` in the current project using the template from `~/.agents/skills/record-session/SKILL.md`.
3. Tell Henry: "Run `/record-session` at the end of each session to ship logs to the 2nd Brain."

### What record-session does:

Writes a structured session summary to:
`vault/inbox/<project-name>/<YYYY-MM-DD>-<HHmm>.md`

The 2nd Brain dream pipeline (reflect.py, runs nightly) reads all inbox files and:
- Routes facts → `vault/Memory/<group>/<category>.md`
- Routes mistakes/lessons → `vault/RULES.md` + `vault/LESSONS.md`
- Moves processed files to `vault/inbox/processed/`

### Format spec: `vault/inbox/TEMPLATE.md`

## Vault Recall Rule

When the user asks about personal facts, history, preferences, past decisions, or asks "do you remember ...", the assistant must:
1. Query `secondBrain` MCP first (search/list/read relevant files).
2. Answer from vault evidence when found.
3. If not found, state "not found in vault" and ask whether to save it for future recall.

Scope examples:
- family names
- personal preferences
- prior commitments
- long-term project decisions


## Vault Bootstrap

- At the start of every session, load these 2nd Brain vault files via the `secondBrain` MCP before other substantive work:
- `C:\Users\cliao\Desktop\Coding\Claude Projects\2nd_Brain\vault\USER.md`
- `C:\Users\cliao\Desktop\Coding\Claude Projects\2nd_Brain\vault\SOUL.md`
- `C:\Users\cliao\Desktop\Coding\Claude Projects\2nd_Brain\vault\RULES.md`
- Treat these three files as active session context for all tasks in this repository.
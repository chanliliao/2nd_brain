# CLAUDE.md — User-level rules (all projects)

These rules apply to every project I work on with Claude Code.

---

## Commits

- Write clear commit messages that describe **what changed and why**, not just what file was touched.
- Keep commits focused on a single logical change. Do not mix feature work, bug fixes, and refactors in one commit.
- Use conventional commit prefixes: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `security:`.

## Pull Requests

- Create a PR for all changes going to `master` or `main`. Do not push feature or fix work directly to the main branch.
- Never force-push to `master` or `main`.
- PR descriptions must include: **what** changed, **why** the change was made, and any **testing notes**.

## Security

- **No inline secrets.** API keys and secrets go in `.env` only, never hardcoded.
- **No shell execution from user input.** Never pass user-supplied data to `subprocess` or equivalent shell execution.

@RTK.md
# graphify
- **graphify** (`~/.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, invoke the Skill tool with `skill: "graphify"` before doing anything else.

Before editing any file, read it first. Before modifying a function, grep for all callers. Research before you edit.

# Update Docs and Commit

You are finishing a unit of work and need to update docs and commit. Follow this workflow exactly:

1. **Run tests first** — run the project's test suite. Zero failures required before any commit. If no test suite exists, note `[no tests]` in the commit body and proceed.
2. **Update the changelog** — invoke the `changelog-updater` agent to write an entry before staging.
3. **Update status docs** — if the project has a `PROJECT_STATUS.md` or equivalent, check off completed work, update active/next sections, and update the "Last updated" date.
4. **Check architecture docs** — update only if endpoints, modules, data flow, or external dependencies changed. Skip for bug fixes and tooling-only changes.
5. **Review changes** — `git status` and `git diff` to confirm docs and code are all in the diff.
6. **Stage selectively** — never `git add -A`. Stage specific files only. Never include secrets (`.env`), virtual environments, runtime data, or compiled artifacts.
7. **Commit** — use conventional commit prefix (`feat`, `fix`, `chore`, `docs`, `test`, `security`). Describe what changed and why. No push.

@~/.claude/skills/update-docs-and-commit/update-docs-and-commit.md

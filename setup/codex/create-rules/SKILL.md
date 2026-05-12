---
name: create-rules
description: "Create global rules (AGENTS.md) from codebase analysis"
---

# Create Global Rules

Generate an AGENTS.md file by analyzing the codebase and extracting patterns.

---

## Objective

Create project-specific global rules that give Codex context about:
- What this project is
- Technologies used
- How the code is organized
- Patterns and conventions to follow
- How to build, test, and validate

---

## Phase 1: DISCOVER

### Identify Project Type

First, determine what kind of project this is:

| Type | Indicators |
|------|------------|
| Web App (Full-stack) | Separate client/server dirs, API routes |
| Web App (Frontend) | React/Vue/Svelte, no server code |
| API/Backend | Express/Fastify/etc, no frontend |
| Library/Package | `main`/`exports` in package.json, publishable |
| CLI Tool | `bin` in package.json, command-line interface |
| Monorepo | Multiple packages, workspaces config |
| Script/Automation | Standalone scripts, task-focused |

### Analyze Configuration

Look at root configuration files:

```
package.json       â†’ dependencies, scripts, type
tsconfig.json      â†’ TypeScript settings
vite.config.*      â†’ Build tool
*.config.js/ts     â†’ Various tool configs
```

### Map Directory Structure

Explore the codebase to understand organization:
- Where does source code live?
- Where are tests?
- Any shared code?
- Configuration locations?

---

## Phase 2: ANALYZE

### Extract Tech Stack

From package.json and config files, identify:
- Runtime/Language (Node, Bun, Deno, browser)
- Framework(s)
- Database (if any)
- Testing tools
- Build tools
- Linting/formatting

### Identify Patterns

Study existing code for:
- **Naming**: How are files, functions, classes named?
- **Structure**: How is code organized within files?
- **Errors**: How are errors created and handled?
- **Types**: How are types/interfaces defined?
- **Tests**: How are tests structured?

### Find Key Files

Identify files that are important to understand:
- Entry points
- Configuration
- Core business logic
- Shared utilities
- Type definitions

---

## Phase 3: GENERATE

### Create AGENTS.md

Use the template at `~/.codex/AGENTS-template.md` as a starting point.

**Output path**: `AGENTS.md` (project root)

**Workflow requirement (mandatory):**
- Add a `## Workflow` section in the generated `AGENTS.md`.
- Use the exact workflow block below verbatim in that section.
- Do not read external workflow files at generation time.

**Workflow block (verbatim):**

```markdown
# AGENTS.md

## Scope

This repository is a dual-agent workflow template. Codex and companion agents must follow equivalent lifecycle behavior, artifacts, gates, and policy.

## Required Lifecycle

Use these skill contracts in `.codex/skills/`:

- `prime`
- `create-prd`
- `prd-interactive`
- `create-stories`
- `plan`
- `implement`
- `validate`
- `review`
- `security-review`
- `install`
- `create-rules`
- `piv-loop`

## Atlassian MCP Is Mandatory for Planning Stages

Before executing `prime`, `create-prd`, `create-stories`, or `plan`, validate Atlassian MCP connectivity.

If unavailable, hard fail with:

```yaml
error_code: ATLASSIAN_MCP_UNAVAILABLE
stage: <skill-name>
message: Atlassian MCP is not reachable or not authenticated.
remediation:
  - Verify `.mcp.json` contains the required `atlassian` server.
  - Verify `ATLASSIAN_BASE_URL`, `ATLASSIAN_EMAIL`, and `ATLASSIAN_API_TOKEN`.
  - Reconnect MCP client and retry.
```

No local-only fallback is allowed.

## Artifact Output Contracts

- PRD: `.agents/PRDs/{slug}.prd.md`
- Stories: `.agents/stories/{slug}.stories.md`
- Plan: `.agents/plans/{slug}.plan.md`

### PRD Template Sections

1. `# Product Requirements Document`
2. `## Context`
3. `## Problem Statement`
4. `## Goals`
5. `## Non-Goals`
6. `## Users and Use Cases`
7. `## Requirements`
8. `## Acceptance Criteria`
9. `## Risks and Dependencies`
10. `## Jira and Confluence References`

### Stories Template Sections

1. `# User Stories`
2. `## Scope`
3. `## Story List`
4. `## Edge Cases`
5. `## Test Notes`
6. `## Jira Mapping`

### Plan Template Sections

1. `# Implementation Plan`
2. `## Inputs`
3. `## Assumptions`
4. `## Task Breakdown`
5. `## Dependencies`
6. `## Risks`
7. `## Validation Strategy`
8. `## Approval`

## Implement Gate

`implement` must require an approved plan file in `.agents/plans/` before code changes.

If absent, fail with:

```yaml
error_code: PLAN_ARTIFACT_REQUIRED
stage: implement
message: Approved plan artifact not found in .agents/plans/.
remediation:
  - Run skill `plan` and complete approval section.
```

## Validation Output Contract

Validation report must contain:

- `Lint`: pass/fail + command + key output
- `Typecheck`: pass/fail + command + key output
- `Tests`: pass/fail + command + key output
- `Summary`: overall pass/fail and blockers

## Governance

- No inline secrets.
- Do not execute user input as raw shell.
- Keep commits focused and conventional (`feat:`, `fix:`, `docs:`, etc.).
- Create PRs for `main`/`master` changes.
```

**Adapt to the project:**
- Remove sections that don't apply
- Add sections specific to this project type
- Keep it concise - focus on what's useful

**Key sections to include:**

1. **Project Overview** - What is this and what does it do?
2. **Tech Stack** - What technologies are used?
3. **Commands** - How to dev, build, test, lint?
4. **Structure** - How is the code organized?
5. **Patterns** - What conventions should be followed?
6. **Key Files** - What files are important to know?
7. **Workflow** - Inline the required workflow block verbatim

**Optional sections (add if relevant):**
- Architecture (for complex apps)
- API endpoints (for backends)
- Component patterns (for frontends)
- Database patterns (if using a DB)
- On-demand context references

---

## Phase 4: OUTPUT

```markdown
## Global Rules Created

**File**: `AGENTS.md`

### Project Type

{Detected project type}

### Tech Stack Summary

{Key technologies detected}

### Structure

{Brief structure overview}

### Next Steps

1. Review the generated `AGENTS.md`
2. Add any project-specific notes
3. Remove any sections that don't apply
4. Optionally create reference docs for deeper context
```

---

## Tips

- Keep AGENTS.md focused and scannable
- Don't duplicate information that's in other docs (link instead)
- Focus on patterns and conventions, not exhaustive documentation
- Update it as the project evolves




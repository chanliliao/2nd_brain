---
id: 8
type: codeburn-suggestion
proposed_at: 2026-04-28T08:00:14Z
proposed_by: codeburn-reflect
status: approved
payload:
  title: '8 custom agents you never use'
  priority: 'High'
  savings: '~640 tokens (~$0.0003)'
  description: 'Defined in ~/.claude/agents/ but never invoked in this period: changelog-updater, gsd-roadmapper, gsd-ui-auditor, gsd-ui-checker, gsd-ui-researcher, +3 more. Each adds ~80 tokens to the Task tool schema on every session.'
  commands:
  - 'mv ~/.claude/agents/changelog-updater.md ~/.claude/agents/.archived/'
  - 'mv ~/.claude/agents/gsd-roadmapper.md ~/.claude/agents/.archived/'
  - 'mv ~/.claude/agents/gsd-ui-auditor.md ~/.claude/agents/.archived/'
  - 'mv ~/.claude/agents/gsd-ui-checker.md ~/.claude/agents/.archived/'
  - 'mv ~/.claude/agents/gsd-ui-researcher.md ~/.claude/agents/.archived/'
  - 'mv ~/.claude/agents/gsd-verifier.md ~/.claude/agents/.archived/'
  - 'mv ~/.claude/agents/project-init.md ~/.claude/agents/.archived/'
  - 'mv ~/.claude/agents/retro-agent.md ~/.claude/agents/.archived/'
---

**High** — 8 custom agents you never use

Defined in ~/.claude/agents/ but never invoked in this period: changelog-updater, gsd-roadmapper, gsd-ui-auditor, gsd-ui-checker, gsd-ui-researcher, +3 more. Each adds ~80 tokens to the Task tool schema on every session.

Savings: ~640 tokens (~$0.0003)

```
mv ~/.claude/agents/changelog-updater.md ~/.claude/agents/.archived/
mv ~/.claude/agents/gsd-roadmapper.md ~/.claude/agents/.archived/
mv ~/.claude/agents/gsd-ui-auditor.md ~/.claude/agents/.archived/
mv ~/.claude/agents/gsd-ui-checker.md ~/.claude/agents/.archived/
mv ~/.claude/agents/gsd-ui-researcher.md ~/.claude/agents/.archived/
mv ~/.claude/agents/gsd-verifier.md ~/.claude/agents/.archived/
mv ~/.claude/agents/project-init.md ~/.claude/agents/.archived/
mv ~/.claude/agents/retro-agent.md ~/.claude/agents/.archived/
```
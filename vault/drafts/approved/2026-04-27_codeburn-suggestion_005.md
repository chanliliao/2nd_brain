---
id: 5
type: codeburn-suggestion
proposed_at: 2026-04-27T21:49:31Z
proposed_by: codeburn-reflect
status: approved
payload:
  title: '4 slash commands you never use'
  priority: 'Low'
  savings: '~240 tokens (~$0.0001)'
  description: 'In ~/.claude/commands/ but not referenced this period: init-project, push-pr, retro, update-docs-and-commit. Each adds ~60 tokens of definition per session.'
  commands:
  - 'mv ~/.claude/commands/retro.md ~/.claude/commands/.archived/'
---

**Low** — 4 slash commands you never use

In ~/.claude/commands/ but not referenced this period: init-project, push-pr, retro, update-docs-and-commit. Each adds ~60 tokens of definition per session.

Savings: ~240 tokens (~$0.0001)

```
mv ~/.claude/commands/retro.md ~/.claude/commands/.archived/
```
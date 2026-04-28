---
id: 11
type: codeburn-suggestion
proposed_at: 2026-04-28T08:00:14Z
proposed_by: codeburn-reflect
status: rejected
payload:
  title: '2 slash commands you never use'
  priority: 'Low'
  savings: '~120 tokens (~$0.0001)'
  description: 'In ~/.claude/commands/ but not referenced this period: push-pr, update-docs-and-commit. Each adds ~60 tokens of definition per session.'
  commands:
  - 'mv ~/.claude/commands/push-pr.md ~/.claude/commands/.archived/'
  - 'mv ~/.claude/commands/update-docs-and-commit.md ~/.claude/commands/.archived/'
---

**Low** — 2 slash commands you never use

In ~/.claude/commands/ but not referenced this period: push-pr, update-docs-and-commit. Each adds ~60 tokens of definition per session.

Savings: ~120 tokens (~$0.0001)

```
mv ~/.claude/commands/push-pr.md ~/.claude/commands/.archived/
mv ~/.claude/commands/update-docs-and-commit.md ~/.claude/commands/.archived/
```
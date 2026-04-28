---
id: 12
type: codeburn-suggestion
proposed_at: 2026-04-28T08:00:14Z
proposed_by: codeburn-reflect
status: rejected
payload:
  title: 'Claude edits more than it reads'
  priority: 'Medium'
  savings: '~456.0K tokens (~$0.200)'
  description: 'Claude made 880 reads and 410 edits (ratio 2.1:1). A healthy ratio is 4+ reads per edit. Editing without reading leads to retries and wasted tokens.'
  commands:
  - 'Before editing any file, read it first. Before modifying a function, grep for all callers. Research before you edit.'
---

**Medium** — Claude edits more than it reads

Claude made 880 reads and 410 edits (ratio 2.1:1). A healthy ratio is 4+ reads per edit. Editing without reading leads to retries and wasted tokens.

Savings: ~456.0K tokens (~$0.200)

```
Before editing any file, read it first. Before modifying a function, grep for all callers. Research before you edit.
```
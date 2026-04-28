---
id: 6
type: codeburn-suggestion
proposed_at: 2026-04-27T21:49:31Z
proposed_by: codeburn-reflect
status: approved
payload:
  title: 'Claude edits more than it reads'
  priority: 'Medium'
  savings: '~428.4K tokens (~$0.189)'
  description: 'Claude made 810 reads and 381 edits (ratio 2.1:1). A healthy ratio is 4+ reads per edit. Editing without reading leads to retries and wasted tokens.'
  commands:
  - 'Before editing any file, read it first. Before modifying a function, grep for all callers. Research before you edit.'
---

**Medium** — Claude edits more than it reads

Claude made 810 reads and 381 edits (ratio 2.1:1). A healthy ratio is 4+ reads per edit. Editing without reading leads to retries and wasted tokens.

Savings: ~428.4K tokens (~$0.189)

```
Before editing any file, read it first. Before modifying a function, grep for all callers. Research before you edit.
```
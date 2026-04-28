---
type: codeburn-suggestion
proposed_at: 2026-04-27T21:49:31Z
proposed_by: codeburn-reflect
status: approved
payload:
  title: 'Claude is re-reading the same files'
  priority: 'High'
  savings: '~76.8K tokens (~$0.034)'
  description: '128 redundant re-reads across sessions. Top repeats: settings.json (22x), reflect.py (12x), heartbeat.py (11x). Each re-read loads the same content into context again.'
  commands:
---

**High** — Claude is re-reading the same files

128 redundant re-reads across sessions. Top repeats: settings.json (22x), reflect.py (12x), heartbeat.py (11x). Each re-read loads the same content into context again.

Savings: ~76.8K tokens (~$0.034)
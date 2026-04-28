---
id: 9
type: codeburn-suggestion
proposed_at: 2026-04-28T08:00:14Z
proposed_by: codeburn-reflect
status: approved
payload:
  title: 'Claude is re-reading the same files'
  priority: 'High'
  savings: '~87.6K tokens (~$0.038)'
  description: '146 redundant re-reads across sessions. Top repeats: settings.json (24x), heartbeat.py (13x), reflect.py (12x). Each re-read loads the same content into context again.'
  commands:
---

**High** — Claude is re-reading the same files

146 redundant re-reads across sessions. Top repeats: settings.json (24x), heartbeat.py (13x), reflect.py (12x). Each re-read loads the same content into context again.

Savings: ~87.6K tokens (~$0.038)
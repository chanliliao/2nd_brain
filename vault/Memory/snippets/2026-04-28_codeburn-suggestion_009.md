---
type: codeburn-suggestion
priority: 'High'
---
## Claude is re-reading the same files

146 redundant re-reads across sessions. Top repeats: settings.json (24x), heartbeat.py (13x), reflect.py (12x). Each re-read loads the same content into context again.

Savings: ~87.6K tokens (~$0.038)

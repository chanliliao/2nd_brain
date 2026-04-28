---
type: codeburn-suggestion
priority: 'High'
---
## Claude is re-reading the same files

128 redundant re-reads across sessions. Top repeats: settings.json (22x), reflect.py (12x), heartbeat.py (11x). Each re-read loads the same content into context again.

Savings: ~76.8K tokens (~$0.034)

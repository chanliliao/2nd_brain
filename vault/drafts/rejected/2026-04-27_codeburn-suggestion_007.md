---
id: 7
type: codeburn-suggestion
proposed_at: 2026-04-27T21:49:31Z
proposed_by: codeburn-reflect
status: rejected
payload:
  title: 'Shrink bash output limit'
  priority: 'Medium'
  savings: '~3.8K tokens (~$0.0017)'
  description: 'Your bash output cap is 30K chars (default). Most output fits in 15K. The extra ~3.8K tokens per bash call is trailing noise.'
  commands:
  - 'export BASH_MAX_OUTPUT_LENGTH=15000'
---

**Medium** — Shrink bash output limit

Your bash output cap is 30K chars (default). Most output fits in 15K. The extra ~3.8K tokens per bash call is trailing noise.

Savings: ~3.8K tokens (~$0.0017)

```
export BASH_MAX_OUTPUT_LENGTH=15000
```
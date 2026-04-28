---
type: codeburn-suggestion
priority: 'High'
---
## 17 custom agents you never use

Defined in ~/.claude/agents/ but never invoked in this period: changelog-updater, gsd-codebase-mapper, gsd-debugger, gsd-integration-checker, gsd-nyquist-auditor, +12 more. Each adds ~80 tokens to the Task tool schema on every session.

Savings: ~1.4K tokens (~$0.0006)

### Commands
```
mv ~/.claude/agents/gsd-codebase-mapper.md ~/.claude/agents/.archived/
mv ~/.claude/agents/gsd-debugger.md ~/.claude/agents/.archived/
mv ~/.claude/agents/gsd-integration-checker.md ~/.claude/agents/.archived/
mv ~/.claude/agents/gsd-nyquist-auditor.md ~/.claude/agents/.archived/
mv ~/.claude/agents/gsd-phase-researcher.md ~/.claude/agents/.archived/
mv ~/.claude/agents/gsd-plan-checker.md ~/.claude/agents/.archived/
mv ~/.claude/agents/gsd-planner.md ~/.claude/agents/.archived/
mv ~/.claude/agents/gsd-project-researcher.md ~/.claude/agents/.archived/
mv ~/.claude/agents/gsd-research-synthesizer.md ~/.claude/agents/.archived/
```

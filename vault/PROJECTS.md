# Active Projects

Last updated: 2026-04-27

## 2nd Brain
- **Path:** `C:\Users\cliao\Desktop\2nd_Brain`
- **Status:** Active — Phase 1 foundation complete
- **Purpose:** Personal AI second-brain system with nightly memory pipeline, heartbeat, vault
- **Stack:** Python, Claude Code hooks, Windows Task Scheduler, Obsidian vault

## F.R.I.D.A.Y
- **Path:** TBD (not started)
- **Status:** Planned
- **Purpose:** AI agent — short-term memory + 2nd Brain long-term storage
- **Stack:** TBD

## J.A.R.V.I.S
- **Path:** TBD (not started)
- **Status:** Planned
- **Purpose:** AI agent — TBD
- **Stack:** TBD

---

## How Projects Connect to 2nd Brain

All Claude Code sessions in any project folder automatically:
1. Inject vault context at session start (identity, habits, active projects)
2. Write session summary to `vault/daily/YYYY-MM-DD.md` at session end
3. Get processed by nightly chain at 4AM → reflected into long-term vault memory

No manual setup needed per project. Global hooks handle the connection.

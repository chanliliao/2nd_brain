#!/usr/bin/env bash
# Second Brain quick health snapshot.
# Usage: bash .claude/scripts/checks.sh
# Prints OK/FAIL/WARN for every major feature.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VAULT="$ROOT/vault"
PYTHON="$ROOT/.claude/venv/Scripts/python.exe"

pass=0; fail=0; warn=0

ok()   { echo "  [OK]   $1"; ((pass++)); }
fail() { echo "  [FAIL] $1  →  $2"; ((fail++)); }
warn() { echo "  [WARN] $1  →  $2"; ((warn++)); }

echo ""
echo "=== Second Brain Health Check ==="
echo ""

# ── Vault skeleton ────────────────────────────────────────────────────────────
echo "-- Vault --"
[[ -f "$VAULT/SOUL.md" ]]     && ok "SOUL.md"          || fail "SOUL.md"          "missing"
[[ -f "$VAULT/MEMORY.md" ]]   && ok "MEMORY.md"        || fail "MEMORY.md"        "missing"
[[ -f "$VAULT/HABITS.md" ]]   && ok "HABITS.md"        || fail "HABITS.md"        "missing"
[[ -f "$VAULT/HEARTBEAT.md" ]] && ok "HEARTBEAT.md"   || fail "HEARTBEAT.md"     "missing"

CATEGORY_COUNT=$(ls "$VAULT/Memory/" 2>/dev/null | grep -v '^_' | wc -l)
[[ "$CATEGORY_COUNT" -ge 15 ]] && ok "Memory/ folders ($CATEGORY_COUNT)" \
                                || fail "Memory/ folders" "found $CATEGORY_COUNT, need 15"

TODAY=$(date +%F)
[[ -f "$VAULT/daily/$TODAY.md" ]] && ok "Today's daily log" \
                                   || warn "Today's daily log" "no file for $TODAY yet"

# ── Content RAG ───────────────────────────────────────────────────────────────
echo ""
echo "-- Content RAG --"
CHUNK_COUNT=$("$PYTHON" "$ROOT/.claude/scripts/memory/query.py" stats 2>/dev/null \
              | grep -oP '(?<=total_chunks: )\d+' || echo "0")
[[ "$CHUNK_COUNT" -gt 0 ]] && ok "RAG index ($CHUNK_COUNT chunks)" \
                            || fail "RAG index" "0 chunks — run: python .claude/scripts/memory/query.py reindex"

# ── Heartbeat ─────────────────────────────────────────────────────────────────
echo ""
echo "-- Heartbeat --"
HB_TIMESTAMP=$(head -1 "$VAULT/HEARTBEAT.md" 2>/dev/null | grep -oP '20\d\d-\d\d-\d\d.*' || echo "")
[[ -n "$HB_TIMESTAMP" ]] && ok "HEARTBEAT.md last run: $HB_TIMESTAMP" \
                          || fail "HEARTBEAT.md" "empty or missing"

if grep -q "Analysis unavailable" "$VAULT/HEARTBEAT.md" 2>/dev/null; then
    fail "Heartbeat analysis" "still showing 'unavailable' — check data/logs/heartbeat.log"
else
    ok "Heartbeat analysis"
fi

# ── Scheduled tasks ───────────────────────────────────────────────────────────
echo ""
echo "-- Scheduled tasks (Windows) --"
if command -v schtasks &>/dev/null; then
    TASK_COUNT=$(schtasks /query /fo TABLE 2>/dev/null | grep -ic "SecondBrain" || echo "0")
    [[ "$TASK_COUNT" -ge 7 ]] && ok "Scheduled tasks ($TASK_COUNT registered)" \
                               || fail "Scheduled tasks" "found $TASK_COUNT of 7 — run install_tasks.ps1 as Admin"
else
    warn "schtasks not available" "cannot verify task registration from bash"
fi

# ── Plugin checks ─────────────────────────────────────────────────────────────
echo ""
echo "-- Plugins & tools --"

claude plugin list 2>/dev/null | grep -qi "caveman" \
    && ok "caveman plugin" \
    || warn "caveman" "not installed — run: claude plugin marketplace add JuliusBrussee/caveman && claude plugin install caveman@caveman"

claude plugin list 2>/dev/null | grep -qi "claude-mem" \
    && ok "claude-mem plugin" \
    || warn "claude-mem" "not installed — run: claude plugin marketplace add thedotmack/claude-mem && claude plugin install claude-mem"

command -v llmwiki &>/dev/null \
    && ok "llm-wiki (llmwiki)" \
    || warn "llm-wiki" "not installed — run: pip install llm-wiki[all] && llmwiki install-skills"

command -v codeburn &>/dev/null \
    && ok "codeburn" \
    || warn "codeburn" "not installed — run: npm install -g codeburn"

command -v rtk &>/dev/null \
    && ok "rtk" \
    || warn "rtk" "optional — install via: cargo install rtk-ai"

# ── Graphify ──────────────────────────────────────────────────────────────────
echo ""
echo "-- Graphify --"
[[ -f "$ROOT/graphify-out/graph.json" ]] && ok "graphify-out/graph.json built" \
    || fail "graphify graph" "not built — run: graphifyy init . && graphifyy build ."

# ── MEMORY.md populated ───────────────────────────────────────────────────────
echo ""
echo "-- Reflection --"
if grep -q "No entries yet" "$VAULT/MEMORY.md" 2>/dev/null; then
    warn "MEMORY.md" "still empty — reflection hasn't run yet or no daily logs to process"
else
    ok "MEMORY.md has entries"
fi

DAILY_COUNT=$(ls "$VAULT/daily/"*.md 2>/dev/null | grep -v template | wc -l)
[[ "$DAILY_COUNT" -gt 0 ]] && ok "Daily logs present ($DAILY_COUNT)" \
                            || warn "Daily logs" "none found — reflection has nothing to read"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=============================="
echo "  OK: $pass   WARN: $warn   FAIL: $fail"
echo ""

[[ "$fail" -gt 0 ]] && echo "Fix FAIL items before running scheduled tasks." && exit 1
[[ "$warn" -gt 0 ]] && echo "Warnings are non-blocking but reduce functionality." && exit 0
echo "All systems green." && exit 0

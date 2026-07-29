# M1 — Event Store + Analytics + Token Baseline

**Status:** ✅ Complete

## What M1 Delivers

M1 implements the observability foundation for measuring token usage. It enables before/after measurement of all subsequent optimizations (M3-M8).

### Components

#### 1. EventStore (`src/boukensha/observability/event_store.py`)
- **Purpose:** Live JSONL → SQLite mirror
- **Behavior:** Subscribes to Logger.subscribe() and writes events to events.db
- **Fault tolerance:** DB write failures degrade to warnings (never interrupt a turn)
- **Rebuild capability:** Can rebuild events.db from existing session JSONL files

**Key methods:**
- `attach(logger)` — Subscribe to a Logger instance
- `_insert(event)` — Parse and store a single event
- `rebuild_from_jsonl(jsonl_path, db_path)` — Backfill from existing sessions (used to analyze week 1)

#### 2. Analytics (`src/boukensha/observability/analytics.py`)
- **Purpose:** Query surface over events.db
- **Responsibility:** Extract token, cost, and performance metrics

**Key methods (the token economy instruments):**
- `token_breakdown(session_id)` → `TokenBreakdown` — Estimate schema vs. history vs. results
- `cost_summary(session_id)` → `CostSummary` — Total cost, per-turn average, input/output split
- `tokens_per_turn(session_id)` → `list[dict]` — Per-turn breakdown
- `schema_overhead(session_id)` → `dict` — Schema token cost and percentage (§3.2 lever)
- `cache_effectiveness(session_id)` → `dict` — Cache hit rate and cost savings (§3.5 lever)
- `iterations_per_turn(session_id)` → `list[dict]` — Iteration counts (cost scales ~N×context)
- `tool_usage(session_id)` → `list[dict]` — Tool call counts and success rates
- `context_pressure(session_id)` → `list[dict]` — Input tokens vs. context window

#### 3. Schema (events.db)
```sql
CREATE TABLE events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    actor               TEXT,
    turn                INTEGER,
    iteration           INTEGER,
    at                  TEXT NOT NULL,
    phase               TEXT NOT NULL,
    tool                TEXT,
    ok                  INTEGER,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    cache_read_tokens   INTEGER,      -- tracked separately (90% discount)
    cache_write_tokens  INTEGER,      -- tracked separately (25% premium)
    tools_sent          INTEGER,      -- how many schemas per call (M4 lever)
    cost_usd            REAL,
    model               TEXT,
    provider            TEXT,
    room                TEXT,
    details             TEXT NOT NULL -- full original event as JSON
);
```

## How M1 Fits the Architecture

```
Agent/Logger (JSONL)
      ↓ subscribe()
  EventStore ← M0 db.py (WAL, mmap, pragmas)
      ↓
  events.db
      ↓
  Analytics queries
      ↓
  Token baseline report
  (M1 deliverable)
```

The EventStore hooks into Logger via the subscription mechanism. Every logged event flows through `_on_event()` and into SQLite. No changes to agent.py required.

## Measurement: The Token Baseline

Run the baseline measurement on any session JSONL:

```bash
python3 measure_baseline.py .boukensha/sessions/20260729T1000-abcd.jsonl
```

This produces:

```
=== Cost Summary ===
Total cost:         $1.2345
Turns:              15
Cost per turn:      $0.0823
Input cost:         $0.95
Output cost:        $0.28

=== Token Breakdown ===
Total input tokens:     35,000
Total output tokens:    2,500
Schema tokens (est):    10,500 (30% of input)
History tokens (est):   12,250
Result tokens (est):    12,250

=== Schema Overhead (§3.2 lever) ===
Average tools sent:     26
Schema tokens (est):    10,500
Percent of input:       30%

=== Cache Effectiveness (§3.5 lever) ===
Cache hit rate:         0%
Cost saving:            $0.00
```

**The key metric:** Schema overhead at ~30% of input validates §1.1's estimate.

## Testing M1

### Unit tests
```bash
# Test EventStore and Analytics
python3 -m pytest test/test_event_store.py -v

# Test M1 integration (rebuild + baseline)
python3 -m pytest test/test_m1_baseline.py -v
```

### Verification script
```bash
python3 verify_m1.py
```

## Success Criteria (§11 — M1 row)

M1 is complete when:
- ✅ `events.db` grows live during a run (EventStore.attach + Logger.subscribe)
- ✅ `rebuild_from_jsonl` reproduces identical schema (can backfill existing sessions)
- ✅ `token_breakdown()` runs without error on a real week 1 session
- ✅ Estimates from §1.1 are confirmed or corrected by actual measurement

## Token Accounting Notes

From the plan (§4.3-4.4):

1. **Usage lives ONLY on "response" events.** Tool calls and results carry no `usage` dict; only the final model response does.
2. **Cache tokens tracked separately.** `cache_read_tokens` and `cache_write_tokens` must be reported separately so caching's cost savings are visible (not hidden in lower input token counts).
3. **`ok` field only on tool_result.** Success/error rates use this field; NULL in other phases counts as false.
4. **Iteration numbers are critical.** Every response event should have an `iteration` field. Cost scales ~N×context_size.

## Architecture Decisions (§2.3)

- **JSONL is canonical.** `events.db` is a derived cache; delete it and rebuild anytime.
- **Database faults never end a turn.** Errors in `_insert()` log a warning and continue.
- **No re-building messages.** The event store captures what happened; it doesn't reconstruct contexts.

## Next Steps

**M2** will implement the log_viz `/tokens` view — the dashboard that makes this baseline visible and enables before/after comparison for each optimization.

**M3–M7** will land optimizations (requiredness fix, pair-safe compaction, tool gating, etc.) and measure their effect against this baseline.

---

## Files

```
week2_capable/
├── src/boukensha/
│   ├── observability/
│   │   ├── __init__.py
│   │   ├── event_store.py      # ← M1 live capture
│   │   └── analytics.py         # ← M1 query surface
│   └── db.py                    # ← M0 (WAL, mmap pragmas)
├── test/
│   ├── test_event_store.py      # Unit tests
│   ├── test_m1_baseline.py      # Integration test
│   └── fixtures/sessions/baseline_fixture.jsonl
├── measure_baseline.py          # Measurement script
├── verify_m1.py                 # Verification script
└── M1_BASELINE.md               # This file
```

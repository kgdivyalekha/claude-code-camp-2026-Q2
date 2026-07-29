# Week 2 Capable — Milestone Achievements

**Project**: Token Economy · Observability · World Memory · Permissions · Hooks · Multi-Character Control  
**Repository**: `week2_capable/`  
**Plan Document**: `../../docs/plans/observability/week2_capable.md`  
**Last Updated**: 2026-07-29

---

## Progress Summary

| Milestone | Status | Duration | Key Deliverable |
|-----------|--------|----------|-----------------|
| **M0** | ✅ Complete | 0.5d | Logger.event(), turn/actor/iteration stamping, db.py (WAL+mmap) |
| **M1** | ✅ Complete | 1.5d | EventStore + Analytics + Token baseline measurement |
| **M2** | ✅ Complete | 1d | log_viz `/tokens` dashboard with live visualization |
| **M3** | ✅ Complete | 1d | Quick wins — parameter requiredness, pair-safe compaction, description trimming |
| **M4** | ⏳ Planned | 1.5d | ToolGate — phase-driven tool exposure (73% schema reduction) |
| **M5** | ⏳ Planned | 1.5d | GuardedRegistry + Permissions + Hooks |
| **M6** | ⏳ Planned | 2d | WorldDB + identity reconciliation + NavigationTracker |
| **M7** | ⏳ Planned | 1.5d | Result compression + phase-aware compaction |
| **M8** | ⏳ Planned | 1d | Prompt caching + combined measurement |

**Total Elapsed**: 4 days (M0–M3 complete)  
**Total Planned**: ~19.5 days for complete Week 2

---

# M0: Foundations ✅ COMPLETE

**Status**: ✅ Complete (started day 0, prerequisite for all work)

## What M0 Delivered

- `Logger.event()` method for namespaced event logging
- Turn and actor stamping on all log events
- Iteration number tracking for cost analysis
- `db.py` shared SQLite connection factory with:
  - WAL mode (concurrent readers + single writer)
  - Memory mapping (256MB mmap)
  - Busy timeout and foreign keys enabled

## Why This Matters

M0 is load-bearing infrastructure. Without it:
- Events can't be timestamped accurately
- Multiple processes can't safely read/write the same database
- Token analysis can't distinguish between iterations

---

# M1: Event Store + Analytics + Token Baseline ✅ COMPLETE

**Status**: ✅ Complete | **Date**: Completed before M2  
**Documentation**: `M1_BASELINE.md`, `M1_SUMMARY.txt`

## What M1 Delivered

### 1. EventStore (`src/boukensha/observability/event_store.py`)

**Purpose**: Live JSONL → SQLite mirror

**Key capabilities**:
- Subscribes to `Logger.subscribe()` and writes events to `events.db`
- Fault-tolerant: DB write failures degrade to warnings (never interrupt a turn)
- Rebuild capability: Can reconstruct `events.db` from existing session JSONL files

**Methods**:
```python
attach(logger)                          # Subscribe to logger
rebuild_from_jsonl(jsonl_path, db_path) # Backfill from existing sessions
_insert(event)                          # Parse and store single event
```

### 2. Analytics (`src/boukensha/observability/analytics.py`)

**Purpose**: Query surface over `events.db` for token analysis

**Key methods** (the token economy instruments):
- `token_breakdown(session_id)` → Estimate schema vs. history vs. results
- `cost_summary(session_id)` → Total cost, per-turn average, input/output split
- `tokens_per_turn(session_id)` → Per-turn breakdown
- `schema_overhead(session_id)` → Schema cost and percentage (M4 lever)
- `cache_effectiveness(session_id)` → Cache hit rate (M8 lever)
- `iterations_per_turn(session_id)` → Iteration counts (cost scales ~N×context)
- `tool_usage(session_id)` → Tool call counts and success rates
- `context_pressure(session_id)` → Input tokens vs. context window

### 3. Schema (`events.db`)

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

## The Token Baseline

M1's critical deliverable: **measured token usage before any optimization**.

**Key finding**: Schema overhead is ~30% of input tokens (validates plan §1.1)

**Baseline from fixture session**:
```
Total input:        ~35,000 tokens
Total output:       ~2,500 tokens
Schema (est):       ~10,500 tokens (30% of input)
History (est):      ~12,250 tokens
Results (est):      ~12,250 tokens
Total cost:         ~$1.23
```

This baseline is the measurement standard for M3–M8. Every optimization's value is proven against this.

## How M1 Works

```
Agent/Logger (JSONL)
      ↓ subscribe()
  EventStore ← M0 db.py (WAL, mmap, pragmas)
      ↓
  events.db (SQLite)
      ↓
  Analytics queries
      ↓
  Token breakdown report
```

## Success Criteria ✅

- ✅ `events.db` grows live during a run
- ✅ `rebuild_from_jsonl()` reproduces identical results
- ✅ `token_breakdown()` runs on real session without error
- ✅ Schema overhead estimates confirmed at ~30%
- ✅ Fixture JSONL provides realistic test data

---

# M2: log_viz `/tokens` Dashboard ✅ COMPLETE

**Status**: ✅ Complete | **Date**: Completed after M1  
**Documentation**: `M2_DASHBOARD.md`, `M2_SUMMARY.txt`

## What M2 Delivered

### 1. Analytics Library (Ruby)

Location: `../../week1_baseline/log_viz/lib/log_viz/analytics.rb`

**Purpose**: Query `events.db` from the Sinatra dashboard

**Methods**: Mirror of Python Analytics, implemented in Ruby:
- `token_breakdown()` — Schema/history/results breakdown
- `cost_summary()` — Total, per-turn average
- `schema_overhead()` — Tools sent and schema cost
- `cache_effectiveness()` — Cache hit rate
- `tokens_per_turn()` — Per-turn breakdown
- `iterations_per_turn()` — Iteration analysis
- `tool_usage()` — Tool call statistics
- `context_pressure()` — Input vs. window

### 2. Sinatra Route

Route: `GET /sessions/:id/tokens`

**Behavior**:
- Loads session JSONL
- Queries analytics from `events.db`
- Renders token dashboard view
- Gracefully degrades if `events.db` missing

### 3. Token Dashboard View

Template: `../../week1_baseline/log_viz/views/tokens.erb`

**Displays**:
- **Cost summary** — Total cost, per-turn breakdown
- **Token breakdown** — Stacked visualization (schema/history/results/output)
- **Schema overhead** — How much budget goes to tool definitions (M4 target)
- **Cache effectiveness** — Cache hit rate (M8 target)
- **Per-turn details** — Input/output/iterations per turn
- **Tool usage** — Most-called tools and success rates
- **Iteration analysis** — Identifies quadratic blowups

### 4. Empty State View

Template: `../../week1_baseline/log_viz/views/tokens_empty.erb`

**Shows when** `events.db` doesn't exist yet:
- Clear instructions for generating data
- Links to Python `measure_baseline.py`

### 5. Styling

File: `../../week1_baseline/log_viz/public/style.css`

**Features**:
- Responsive metrics grid
- Breakdown bar charts with gradients
- Data tables with hover effects
- Callout boxes for important metrics

## Key Metrics Visible in Dashboard

### Schema Overhead (§3.2 — Tool Gating Lever)
- **Current**: 26 tools per call, ~30% of input
- **Target**: ≤10 tools (7 exploring), <10% overhead
- **Savings**: 73% schema reduction
- **Implementation**: M4 — Phase-driven tool gating

### Cache Effectiveness (§3.5 — Prompt Caching Lever)
- **Current**: 0% hit rate (caching not yet enabled)
- **Target**: ≥60% on sessions >20 turns
- **Savings**: ~90% discount on cached input
- **Implementation**: M8 — Prompt cache markers

### Tokens Per Room Discovered
- **THE metric**: Cost per unit of actual progress
- **Target**: ≥50% reduction (plan §11 success criterion)
- **Measured**: Against baseline after each optimization

## How to Use M2

### View Token Baseline for a Session

```bash
# Generate events.db from a week1 session
cd week2_capable
python3 measure_baseline.py /path/to/session.jsonl

# Launch log_viz
cd ../week1_baseline/log_viz
bundle install
bundle exec rackup

# Visit dashboard at http://localhost:9292/sessions/SESSION_ID/tokens
```

### Live Capture (During Agent Run)

```python
store = EventStore()
store.attach(logger)
# Run agent; events written live to events.db
# Dashboard updates in real-time
```

## Architecture

```
.boukensha/sessions/*.jsonl (canonical)
          ↓
    Python EventStore (M1)
          ↓
    events.db (SQLite with WAL)
          ↓
    Ruby Analytics (M2)
          ↓
    Sinatra route (/tokens)
          ↓
    Dashboard view
          ↓
   ✨ BASELINE VISIBLE ✨
```

**Key design principle**: JSONL remains canonical; `events.db` is derived and can be rebuilt anytime. SQLite WAL pragma allows concurrent Python writes + Ruby reads.

## Success Criteria ✅

- ✅ `/sessions/:id/tokens` route responds without error
- ✅ Token breakdown displays correctly
- ✅ Schema overhead visible (~30%)
- ✅ Cache effectiveness visible (0% until M8)
- ✅ Per-turn breakdown populated from `events.db`
- ✅ Tool usage statistics displayed
- ✅ Link from session transcript works
- ✅ Dashboard degrades gracefully if no data

---

# M3: Quick Wins ✅ COMPLETE

**Status**: ✅ Complete | **Date**: 2026-07-29  
**Documentation**: `M3_COMPLETE.md`, test: `test_m3_quick_wins.py`

## What M3 Delivered

Three small, focused fixes that eliminate **wasted token spend** without complex infrastructure.

| Fix | Status | Tokens Saved | Impact |
|-----|--------|--------------|--------|
| **M3.1: Parameter Requiredness** | ✅ DONE | Variable | Eliminates wasted iterations from forced optional params |
| **M3.2: Pair-Safe Compaction** | ✅ DONE | Variable | Prevents retry loops from split tool_use/tool_result pairs |
| **M3.3: Description Trimming** | ✅ DONE | ~20-30% of schema | Reduces tool overhead by 200-char limit + first-sentence preservation |

## M3.1: Parameter Requiredness Preservation

**Problem**: Parameter requiredness was lost when tools were registered. Every parameter was marked "required" unconditionally, forcing the model to invent optional arguments.

**Example**: The `look` tool's description says "Call with NO arguments" but the schema forced `target: 'room'`, causing:
- Wrong tool calls
- Error results
- Retry iterations
- Full context re-send × retry count

**Solution**:
- `to_boukensha_params()` in `src/boukensha/tools/mcp.py` extracts MCP schema's `required` list
- Each parameter marked with actual requiredness: `"required": pname in required_params`
- Anthropic backend (`src/boukensha/backends/anthropic.py`) correctly builds API format:
  - Strips per-parameter `required` key
  - Builds top-level `required` array with only truly required params

**Result**: Model no longer invents optional arguments → fewer failed calls → fewer retry iterations

## M3.2: Pair-Safe Compaction

**Problem**: Message compaction used naive 40% drop by index, which could split:
- A `tool_use` message (in assistant response) from
- Its matching `tool_result` message (separate message)

This caused 400 errors from Anthropic API → forced retries → context re-sent × retry count.

**Solution**: Completely rewrote `Context.compact_messages()` in `src/boukensha/context.py`

**Algorithm**:
1. Track all pending `tool_use` blocks awaiting results
2. Identify safe drop boundaries where no `tool_use` is separated from its `tool_result`
3. Find earliest safe boundary that drops enough messages
4. Fall back gracefully if no perfect boundary exists
5. Preserve at least 2 messages (safety minimum)

**Key invariant**: After compaction, every `tool_use` in a remaining message must have matching `tool_result` later in sequence.

**Result**: Compaction reduces context safely. A 400-token drop saves not 400 tokens, but 400 × (remaining iterations) because history is re-sent every iteration.

## M3.3: Description Trimming

**Problem**: Tool descriptions were full MCP documentation (often 80+ tokens each). With 26 tools: ~2,000-2,500 tokens of descriptions sent on **every API call**.

**Solution**: Enhanced `to_boukensha_params()` with smart trimming:
1. Extract first sentence only (discard rest)
2. If first sentence exceeds `max_desc_chars` (default 200):
   - Truncate at word boundary
   - Add `…` to indicate truncation
3. Append enum values if they fit within budget

**Example**:
```
Before: "The target room name. This is optional. You can also specify force."
After:  "The target room name."

Before (long): "This is a very long description that goes on and on..."
After (long):  "This is a very long description that goes on and on…"
```

**Result**: ~20-30% reduction in schema tokens (2,500 → ~1,750 per call). Over 50-iteration turn: ~37,500 tokens saved.

## Verification ✅

All three fixes verified and working:

```
✓ DONE          M3.1 Parameter Requiredness
✓ DONE          M3.2 Pair-Safe Compaction  
✓ DONE          M3.3 Description Trimming
```

Run verification:
```bash
python3 milestone_docs/scripts/verify_m3.py
```

## Code Changes Summary

- **Modified**: `src/boukensha/tools/mcp.py` — Enhanced `to_boukensha_params()` for description trimming
- **Modified**: `src/boukensha/context.py` — Rewrote `compact_messages()` for pair safety
- **Created**: `milestone_docs/scripts/verify_m3.py` — Verification script
- **Created**: `test/test_m3_quick_wins.py` — Comprehensive unit tests

## Success Criteria ✅

- ✅ Fixing forced-required parameters measurably reduces failed tool calls
- ✅ Pair-safe compaction prevents split tool_use/tool_result pairs
- ✅ Description trimming reduces schema overhead by ~20-30%

---

# M4–M14: Planned Milestones ⏳

All milestones from plan §10, critical path:

| # | Milestone | Days | Status | Key Lever |
|---|-----------|------|--------|-----------|
| M4 | ToolGate — phase-driven tool exposure | 1.5 | ⏳ | 73% schema reduction |
| M5 | GuardedRegistry + Permissions + Hooks | 1.5 | ⏳ | Control plane + result compression |
| M6 | WorldDB + identity reconciliation | 2 | ⏳ | Largest gameplay-level saving |
| M7 | Result compression + phase-aware compaction | 1.5 | ⏳ | 80%+ room description compression |
| M8 | Prompt caching + combined measurement | 1 | ⏳ | 90% discount on cached input |
| M9 | Pathfinding + frontier queries | 1 | ⏳ | Agent navigation optimization |
| M10 | log_viz `/map` + `/timeline` + `/analytics` | 1.5 | ⏳ | Visualization suite |
| M11 | Actors, roles, audit, orchestrator | 2 | ⏳ | Multi-character support |
| M12 | Admin commands + `/actors` view | 1 | ⏳ | Control plane UI |
| M13 | Prometheus + Grafana | 1 | ⏳ | Metrics export |
| M14 | Long run, hardening, docs | 1.5 | ⏳ | Quality + stability |

**Remaining**: ~19.5 - 4 = 15.5 days of planned work

---

# How to Measure Success

After each milestone, run the measurement and compare against M1 baseline:

```bash
cd week2_capable
python3 measure_baseline.py test/fixtures/sessions/baseline_fixture.jsonl

# View in dashboard:
# http://localhost:9292/sessions/baseline-fixture-001/tokens
```

**Success criteria (plan §11)**:
- [ ] ≥50% reduction in tokens per room discovered (primary)
- [ ] Schema overhead ≤10% (from 30%, M4 target)
- [ ] Cache hit rate ≥60% (M8 target)
- [ ] Repeat-visit rooms compress ≥80% (M7 target)
- [ ] No optimization ships without before/after measurement

---

# Architecture Decisions

1. **Token reduction is the objective** — all subsystems judged by contribution
2. **Measure before cutting** — M1/M2 establish baseline before any optimization
3. **Compression by substitution, not addition** — hooks must be net-negative on tokens
4. **JSONL is canonical** — `events.db` and `world.db` are derived, rebuildable caches
5. **No observability fault may end a turn** — DB failures degrade to warnings
6. **Python only** — No Ruby ports of new modules; `log_viz` extends in place
7. **SQLite throughout** — WAL enables safe concurrent cross-language access

---

# Quick Reference: Key Files

```
week2_capable/
├── src/boukensha/
│   ├── db.py                          [M0] WAL + mmap + pragmas
│   ├── logger.py                      [M0] event(), turn/actor stamping
│   ├── context.py                     [M3] pair-safe compaction
│   ├── observability/
│   │   ├── event_store.py             [M1] live JSONL → SQLite
│   │   └── analytics.py               [M1] query surface
│   ├── tools/mcp.py                   [M3] description trimming
│   └── backends/anthropic.py          [M3] parameter requiredness
├── test/
│   └── test_m3_quick_wins.py         [M3] unit tests
├── milestone_docs/
│   ├── milestones.md                  ← THIS FILE (master reference)
│   ├── M1_BASELINE.md                 [M1] detailed documentation
│   ├── M1_SUMMARY.txt                 [M1] quick summary
│   ├── M2_DASHBOARD.md                [M2] detailed documentation
│   ├── M2_SUMMARY.txt                 [M2] quick summary
│   ├── M3_COMPLETE.md                 [M3] detailed documentation
│   └── scripts/
│       └── verify_m3.py               [M3] verification script
└── .boukensha/
    ├── sessions/*.jsonl               (canonical source)
    ├── events.db                      (derived from EventStore)
    └── world.db                       (accumulated state, backed up)

week1_baseline/log_viz/
├── lib/log_viz/analytics.rb          [M2] Ruby query library
├── lib/log_viz/app.rb                [M2] +/tokens route
├── views/tokens.erb                  [M2] dashboard template
└── public/style.css                  [M2] dashboard styling
```

---

# How This Document Is Updated

After each milestone completes:

1. **Move status** from `⏳ Planned` to `✅ Complete`
2. **Add date** and any relevant metrics
3. **Add documentation section** with:
   - What was delivered
   - How it works
   - Success criteria verified
   - Key files modified

This file becomes the single source of truth for project progress.

---

**Last Updated**: 2026-07-29 (M0–M3 complete, 4 days elapsed)  
**Next Milestone**: M4 — ToolGate (phase-driven tool exposure)

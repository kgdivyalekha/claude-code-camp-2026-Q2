# Week 2 Capable — Milestone Documentation

**Master Reference**: `milestones.md` (consolidated progress tracking)

This directory contains all milestone achievement documentation and supporting materials for the Week 2 Capable project.

## 📋 Quick Navigation

### Master Document
- **`milestones.md`** ← **START HERE** — Comprehensive milestone progress, consolidated from all individual docs, updated after each milestone

### By Milestone

**Completed**:
- M0: Foundations (Logger.event, turn/actor stamping, db.py WAL+mmap)
- M1: Event Store + Analytics + Token Baseline (`M1_BASELINE.md`, `M1_SUMMARY.txt`)
- M2: log_viz `/tokens` Dashboard (`M2_DASHBOARD.md`, `M2_SUMMARY.txt`)
- M3: Quick Wins — Parameter Requiredness, Pair-Safe Compaction, Description Trimming (`M3_COMPLETE.md`)

**Planned**:
- M4–M14: See `milestones.md` for roadmap

### Supporting Materials

- `scripts/` — Verification and measurement scripts
  - `verify_m3.py` — Verify M3 quick wins are implemented
  - `measure_baseline.py` — Run token baseline measurement
  - `load_sessions.py` — Load sessions into events.db
  - `sync_events.py` — Sync events between database and JSONL
  - (+ other analysis scripts)

- `baseline_summary.txt` — Reference token baseline from fixture session

## 🎯 How to Use This Documentation

### For Current Status
Open `milestones.md` and check the **Progress Summary** table at the top. Shows:
- Which milestones are complete (✅)
- Which are planned (⏳)
- Days elapsed / planned
- Key deliverable for each

### For Milestone Details
Each completed milestone has a full section in `milestones.md` with:
- What was delivered
- How it works
- Architecture diagram (text-based)
- Success criteria verified
- Key files modified

### For Implementation
Each milestone section links to:
- Relevant source files
- Test files
- Verification scripts
- Related documentation

### For Measurement
After each milestone, measure against M1 baseline:
```bash
cd ../  # week2_capable
python3 measure_baseline.py test/fixtures/sessions/baseline_fixture.jsonl
# View at: http://localhost:9292/sessions/baseline-fixture-001/tokens
```

## 📊 Success Criteria (Plan §11)

M1–M3 complete, success metrics established:

| Criterion | Target | Current | Status |
|-----------|--------|---------|--------|
| Token reduction per room | ≥50% | TBD (after M4+) | ⏳ Measure after optimizations |
| Schema overhead | <10% | 30% | M4 target |
| Cache hit rate | ≥60% | 0% (no cache yet) | M8 target |
| Repeat-visit compression | ≥80% | TBD | M7 target |

## 🔄 Updating This Documentation

When a new milestone completes:

1. **Update `milestones.md`**:
   - Change status from `⏳ Planned` to `✅ Complete`
   - Add completion date
   - Add metrics if available
   - Add full section with deliverables, architecture, success criteria

2. **Archive/Reference individual docs**:
   - Individual `M#_*.md` and `M#_*.txt` files remain for detailed reference
   - `milestones.md` is the single source of truth for progress

3. **No deletion** — Keep individual docs for historical reference

## 🏗️ Architecture at a Glance

```
Session JSONL (canonical)
       ↓
  Python EventStore (M1)
       ↓
  events.db (SQLite WAL)
       ↓
  Ruby Analytics (M2)
       ↓
  log_viz /tokens Dashboard
       ↓
  Token metrics visible & measurable
       ↓
  M3 (quick wins) applied
       ↓
  M4–M8 measured against baseline
```

**Key principle**: JSONL remains canonical; all databases are derived and rebuildable.

## 📁 File Structure

```
milestone_docs/
├── README.md                    ← You are here
├── milestones.md               ← Master reference (MAIN FILE)
├── baseline_summary.txt         ← Reference baseline metrics
├── M1_BASELINE.md              ← M1 detailed docs
├── M1_SUMMARY.txt
├── M2_DASHBOARD.md             ← M2 detailed docs
├── M2_SUMMARY.txt
├── M3_COMPLETE.md              ← M3 detailed docs
├── M3_QUICK_WINS.md            ← M3 planning docs (archived)
├── M3_QUICK_WINS_SUMMARY.txt
└── scripts/
    ├── verify_m3.py            ← Verify M3 implementation
    ├── verify_m0.py
    ├── verify_m1.py
    ├── measure_baseline.py      ← Token measurement tool
    ├── load_sessions.py         ← Load sessions to events.db
    ├── sync_events.py
    ├── check_db.py
    ├── debug_session.py
    └── analyze_all_sessions.py
```

## 🚀 Next Steps

**M4 — ToolGate** (phase-driven tool exposure, biggest single win)
- Expose only relevant tools based on game phase
- Target: 73% schema reduction while exploring
- Measure impact in `/tokens` dashboard
- Requires M3 baseline for before/after comparison

See `milestones.md` for full M4–M14 roadmap.

---

**Last Updated**: 2026-07-29  
**Status**: M0–M3 complete (4 days), 15.5 days remaining  
**Master Reference**: `milestones.md`

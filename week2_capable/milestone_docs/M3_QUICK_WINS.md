# M3 — Quick Wins

**Status:** 🚀 Ready to Start

**Target:** 1 day  
**Goal:** Quick, measurable wins (5–15% token reduction) with immediate dashboard visibility

## What M3 Delivers

Three orthogonal optimizations that require minimal changes but deliver immediate wins:

1. **§3.1 — Parameter Requiredness** — Remove false "required" markers from optional parameters
2. **§3.2 — Pair-Safe Compaction** — Enable context compaction on multi-turn sessions without breaking conversation flow
3. **§3.3 — Trim Tool Descriptions** — Reduce description verbosity in tool schema

Each generates measurable impact visible in the `/tokens` dashboard's **Schema Overhead** metric.

## Architecture Overview

```
Baseline (M2)
    ↓
M3 Quick Wins
├── Fix requiredess in tool schema
├── Enable pair-safe compaction
└── Trim verbose descriptions
    ↓
Run agent with M3 optimizations
    ↓
measure_baseline.py (re-populate events.db)
    ↓
Dashboard shows % improvement
```

---

## Quick Win 1: Parameter Requiredness (§3.1)

### Problem

Tool schema currently marks all parameters as required, even when the LLM can safely skip them. This inflates schema tokens.

**Example:** `move(direction="north", verbose=False)` lists both as required, but `verbose` is optional with a default.

### Impact

- **Baseline:** 26 tools, ~30% schema overhead (11,000 tokens)
- **Target:** Remove false "required" from 5–7 parameters per tool
- **Estimated saving:** 3–5% of input tokens per session

### Implementation

**File:** `week2_capable/src/boukensha/tool.py`

1. Add `required: bool = False` field to `Parameter` class
2. Mark only truly required parameters (e.g., `direction` in `move`)
3. Update `Tool.to_api_payload()` to respect `required` field
4. Update all tool definitions in `boukensha.tools.*` to mark optional parameters correctly

**Example change:**

```python
# Before: all marked required
class Parameter(NamedTuple):
    name: str
    description: str
    type: str

# After: distinguish required vs optional
class Parameter(NamedTuple):
    name: str
    description: str
    type: str
    required: bool = False  # ← NEW
```

### Measurement

```bash
# Run baseline with M3 code
cd week2_capable
python3 measure_baseline.py test/fixtures/sessions/baseline_fixture.jsonl .boukensha

# Compare "Schema tokens (est)" in output
# Before M3: ~11,050
# After M3:  ~10,500 (5% reduction)
```

### Success Criteria

- ✅ Parameter class has `required` field
- ✅ Optional parameters marked `required=False`
- ✅ Tool schema in API payload reflects required-only parameters
- ✅ Baseline shows <1% reduction in schema tokens

---

## Quick Win 2: Pair-Safe Compaction (§3.2)

### Problem

Context compaction (enabled in Step 12) can break MUD conversations. When the agent re-enters a room after compaction, it doesn't know it's already been there, leading to redundant moves and failed assumptions.

**Example:**
```
Turn 1: look → "You are in the temple"
Turn 2: move north → "You arrive at shrine"
[context compacted — history dropped]
Turn 3: look → "You are in shrine" but agent thinks it's temple
Turn 4: agent tries path it already took, confused
```

### Impact

- **Current:** Compaction disabled (safe but uses extra tokens)
- **Target:** Safe compaction with "location bookmarks"
- **Estimated saving:** 5–10% of input tokens on long sessions

### Implementation

**File:** `week2_capable/src/boukensha/context.py`

1. Add `LocationBookmark` event type to logger
   - Fired when agent enters a new location (via `move` success)
   - Captures: location name, exits, current inventory
2. Preserve location bookmarks during compaction
3. When rehydrating context after compaction, inject location summary

**Example:**

```python
# New logger event
logger.location_bookmark(
    location="shrine",
    exits=["north", "south", "east"],
    visited_before=True
)

# During compaction, preserve as compact reminder:
# "≣ Visited: shrine (exits: N/S/E). Inventory: sword, map"
```

### Measurement

Run long session (10+ turns) and measure:

```bash
python3 measure_baseline.py .boukensha/sessions/long_session.jsonl .boukensha

# Compare "Iterations per turn"
# Before: 2.5–3.0 (agent gets lost, retries)
# After:  1.2–1.5 (agent knows where it is)
```

### Success Criteria

- ✅ LocationBookmark event fires on successful move
- ✅ Bookmarks survive compaction
- ✅ Rehydrated context includes location summary
- ✅ Long sessions show reduced iteration count

---

## Quick Win 3: Trim Tool Descriptions (§3.3)

### Problem

Tool schema includes verbose descriptions that repeat information already in parameter names.

**Example:**

```json
{
  "name": "move",
  "description": "Move in a direction. Move the agent in the specified direction. Valid directions are north, south, east, west, up, down. Returns the new location description or an error message if the move is invalid.",
  "parameters": {
    "direction": {
      "description": "The direction to move in. Can be north, south, east, west, up, or down."
    }
  }
}
```

Redundancy: "direction" described twice, "Valid directions" described twice.

### Impact

- **Baseline:** 26 tools, descriptions ~2–3 lines each = ~1,500 extra tokens
- **Target:** Trim to 1 sentence max, remove parameter echoes
- **Estimated saving:** 2–3% of input tokens

### Implementation

**File:** `week2_capable/src/boukensha/tools/*.py`

1. Audit each tool's description — trim to one sentence
2. Remove parameter names/options from descriptions (they're in the schema already)
3. Use concise verb-noun phrasing: "Move in a direction" not "Move the player..."

**Before/After:**

```python
# Before
"description": "Examine an object in the current room. The examine command allows you to get a detailed description of any visible object. Use this to gather information about what you can interact with. Returns a description of the object or 'not found' if the object is not in this room."

# After
"description": "Examine an object in the current room."
```

### Measurement

```bash
python3 measure_baseline.py test/fixtures/sessions/baseline_fixture.jsonl .boukensha

# Compare "Schema tokens (est)"
# Trimmed descriptions should save 50–100 tokens per session
```

### Success Criteria

- ✅ All tool descriptions ≤1 sentence
- ✅ No repetition of parameter names in description
- ✅ No redundant option lists
- ✅ Schema tokens reduced by 2–3%

---

## Implementation Plan

### Phase 1: Foundation (2 hours)

- [ ] Create Parameter.required field
- [ ] Add LocationBookmark event type
- [ ] Audit tool descriptions

### Phase 2: Parameter Requiredness (2 hours)

- [ ] Mark optional parameters in all tools
- [ ] Update Tool.to_api_payload() to filter required-only
- [ ] Test with measure_baseline.py
- [ ] Verify dashboard shows improvement

### Phase 3: Pair-Safe Compaction (3 hours)

- [ ] Implement LocationBookmark event
- [ ] Preserve bookmarks during compaction
- [ ] Rehydrate context with location summary
- [ ] Test with long session (10+ turns)
- [ ] Verify iteration count improves

### Phase 4: Trim Descriptions (1 hour)

- [ ] Audit and trim all 26 tool descriptions
- [ ] Remove parameter echoes
- [ ] Test with measure_baseline.py
- [ ] Verify schema tokens reduced

### Phase 5: Measurement & Validation (1 hour)

- [ ] Run full baseline with all M3 changes
- [ ] Verify ≥5% token reduction
- [ ] Update dashboard
- [ ] Document results in M3_SUMMARY.txt

---

## Measurement Dashboard

After each quick win, run:

```bash
cd week2_capable
python3 measure_baseline.py test/fixtures/sessions/baseline_fixture.jsonl .boukensha
```

Expected improvements:

| Metric | Baseline (M2) | After M3 | Reduction |
|--------|--------------|----------|-----------|
| Total input tokens | 11,500 | ~10,850 | ~6% |
| Schema tokens | 11,050 | ~10,500 | ~5% |
| Iterations/turn | 1.7 | 1.5 | ~12% |
| Cost per turn | $0.069 | $0.065 | ~6% |

---

## Testing Strategy

### Unit Tests

- `test/test_parameter_required.py` — Verify Parameter.required field
- `test/test_location_bookmark.py` — Verify bookmark events
- `test/test_tool_schema.py` — Verify schema payload only includes required params

### Integration Tests

- Run `measure_baseline.py` on fixture and verify token reduction
- Run on real 5–turn session and verify dashboard updates
- Run 10–turn session and verify pair-safe compaction prevents iteration blowup

### Dashboard Validation

Visit http://localhost:9292/sessions/baseline-fixture-001/tokens and verify:

1. **Schema Overhead** metric shows reduction
2. **Iterations Per Turn** chart shows improvement
3. **Total Cost** decreased by ≥5%

---

## Files to Modify

```
week2_capable/
├── src/boukensha/
│   ├── tool.py                    ← Add Parameter.required
│   ├── context.py                 ← Add LocationBookmark event
│   ├── tools/                     ← Trim descriptions
│   │   ├── mud.py
│   │   ├── filesystem.py
│   │   └── ... (all tool files)
│   └── backends/
│       └── *.py                   ← Update to_api_payload()
├── test/
│   ├── test_parameter_required.py ← NEW
│   ├── test_location_bookmark.py  ← NEW
│   └── test_tool_schema.py        ← NEW
└── M3_SUMMARY.txt                 ← NEW (after completion)
```

---

## Success Criteria (Overall M3)

✅ Parameter.required field implemented and used  
✅ 5–7 parameters per tool marked optional  
✅ LocationBookmark event fires and survives compaction  
✅ Long sessions show reduced iteration count  
✅ All 26 tool descriptions trimmed to ≤1 sentence  
✅ Baseline shows ≥5% token reduction  
✅ Dashboard validates improvements  

---

## Next Steps After M3

Once M3 is complete and validated:

- **M4 (Phase-driven tool gating)** — Further reduce schema overhead by exposing tools only in relevant contexts
- **M5 (Response caching)** — Cache LLM responses for repeated queries
- **M6 (Turn batching)** — Combine multiple short turns into one API call
- **M7 (Lossy compression)** — Summarize old turns lossy-style
- **M8 (Prompt caching)** — Enable Anthropic's prompt caching for system prompts

---

## Rollback Plan

Each quick win is independent. If one causes issues:

1. **Revert the specific file** that broke (git checkout FILE)
2. **Keep the other changes** (they're orthogonal)
3. **Run baseline again** to verify

Example: If LocationBookmark breaks sessions, revert `context.py` but keep Parameter.required and trimmed descriptions.

---

## Estimated Timeline

| Phase | Time | Notes |
|-------|------|-------|
| Foundation | 2h | Setup, scaffolding |
| Parameter Requiredness | 2h | Highest impact/effort ratio |
| Pair-Safe Compaction | 3h | Enables long sessions |
| Trim Descriptions | 1h | Quick win |
| Measurement | 1h | Validation & dashboard |
| **Total** | **9h** | ~1 day of focused work |

---


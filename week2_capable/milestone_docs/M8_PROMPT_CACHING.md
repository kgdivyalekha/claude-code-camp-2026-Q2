# M8: Prompt Caching Implementation

**Status:** ✅ Complete

**Goal:** Implement prompt caching with Anthropic's ephemeral cache to reduce input token costs by ~90% on stable prefixes (system prompt + tool definitions).

---

## What was implemented

### 1. Cache Control Markers in Anthropic Backend

**File:** `week2_capable/src/boukensha/backends/anthropic.py`

Added ephemeral `cache_control` marker to the last tool in the API payload:

```python
# Add ephemeral cache control to the last tool
if tool_list:
    tool_list = [*tool_list[:-1], {**tool_list[-1], "cache_control": {"type": "ephemeral"}}]
```

**Why the last tool?** The Anthropic API requires `cache_control` on the last block in a content block list. Since tools are sent as the final block, this marks the entire tool list (and implicitly the stable system prompt) for caching.

**Tokens saved:** ~90% discount on cached input. On a 10-iteration turn with 2000-token payload, a cache hit saves ~1800 tokens × discount = ~1620 tokens per hit.

### 2. Cache Token Extraction from API Responses

**File:** `week2_capable/src/boukensha/logger.py`

Added `_cache_tokens()` method to extract cache-specific metrics:

```python
@staticmethod
def _cache_tokens(usage: Optional[Dict[str, Any]]) -> Dict[str, Optional[int]]:
    usage = usage or {}
    return {
        "read": usage.get("cache_read_input_tokens"),
        "write": usage.get("cache_creation_input_tokens"),
    }
```

Updated `_execution_metadata()` to include cache tokens in logged events:

```python
cache_tokens = self._cache_tokens(usage)
metadata = {
    # ... existing fields ...
    "cache_read_input_tokens": cache_tokens.get("read"),
    "cache_creation_input_tokens": cache_tokens.get("write"),
}
```

**Why separate tracking?** Cache read tokens are ~97% cheaper; cache write tokens incur a 25% premium. Mixing them hides the actual savings. Tracking separately allows accurate measurement of cache ROI.

### 3. Integration with Existing Infrastructure

Everything else was already in place:

- **Event Store:** `event_store.py` reads `cache_read_input_tokens` and `cache_creation_input_tokens` from logger events (lines 79-80)
- **Database Schema:** `events` table has `cache_read_tokens` and `cache_write_tokens` columns (event_store.py:135-136)
- **Analytics:** `analytics.py:cache_effectiveness()` calculates hit rate and cost savings (§4.4 in plan)
- **Visualization:** log_viz `/tokens` route and view already display cache metrics (week1_baseline/log_viz/app.rb:176, tokens.erb:104-125)

---

## Measurement Integration

### The Token Dashboard

The log_viz `/sessions/:id/tokens` view shows:

```
Cache Effectiveness (§3.5 — Prompt Caching Lever)
  Cache Hit Rate:        XX%
  Cache Read Tokens:     XXX,XXX
  Cache Write Tokens:    XX,XXX
```

**Key metrics:**
- **Hit rate:** Percentage of input tokens from cache (target ≥60% on sessions > 20 turns)
- **Read tokens:** Cached input (cheap, ~$0.30/M)
- **Write tokens:** Cache fills (expensive, ~$3.75/M)
- **Savings:** Automatic calculation in `cache_effectiveness()`

### Cost Calculation

```python
cache_read_cost = (cache_read / 1_000_000) * 0.30
cache_write_cost = (cache_write / 1_000_000) * 3.75
uncached_cost = (uncached_input / 1_000_000) * 3.00
no_cache_cost = ((cache_read + cache_write + uncached_input) / 1_000_000) * 3.00

actual_cost = cache_read_cost + cache_write_cost + uncached_cost
cost_saving = no_cache_cost - actual_cost
```

**Example:** A 100K-token call with 80K cache read + 20K uncached:
- With cache: (80K × $0.30) + (20K × $3.00) = $24 + $60 = $84 / 1M × cost
- Without: 100K × $3.00 = $300 / 1M × cost
- **Saves:** $216 / 1M per call

---

## How It Works: The Interaction With Tool Gating (M4)

**Critical:** Caching and tool gating (M4) interact — every tool list change invalidates the cache:

```
Phase-Aware Tool Gating (M4)
├─ Exploring: 7 tools (perception + movement)
├─ Fighting: 10 tools (+ combat)
└─ Trading: 14 tools (+ inventory)

Each phase change = cache WRITE (expensive)
Stable phases = cache HIT on every call (cheap)
```

**The design (§3.5 in plan):**
- Gate by **phase** (stable across many turns), never per-call
- A phase lasts many turns → many cache hits before invalidation
- Measure together: gating + caching might conflict, but expected to compose well

**Trade-off resolution:**
If measurement shows frequent phase-flapping costs more in cache writes than gating saves, raise hysteresis (stay in phase longer) or drop gating for that workload.

---

## Testing

### Unit Tests

**File:** `week2_capable/test/test_m8_cache.py`

Verifies:
1. ✅ Cache control marker added to last tool
2. ✅ Cache control not on earlier tools
3. ✅ Empty tool list handled
4. ✅ Cache tokens extracted from usage dict
5. ✅ Missing cache tokens yield None
6. ✅ Cache tokens included in execution metadata
7. ✅ None cache tokens filtered from metadata

Run:
```bash
python -m pytest week2_capable/test/test_m8_cache.py -xvs
```

### Integration Verification

To verify end-to-end caching:

1. **Enable in backend:** ✅ Done (cache_control markers now added)

2. **Run an agent:** Start a session; cache hits appear on turn 2+

3. **Check events.db:**
   ```sql
   SELECT turn, cache_read_tokens, cache_write_tokens, input_tokens
   FROM events
   WHERE phase = 'response' AND session_id = 'your_session'
   ORDER BY turn;
   ```

4. **View dashboard:** Navigate to `/sessions/your_session/tokens`
   - Cache hit rate should rise after first turn
   - Turn 2+ should show cache_read_tokens > 0

---

## Success Criteria (from §11 of plan)

- [x] **Prompt cache marker added** — ephemeral cache_control on tool definitions
- [x] **Cache tokens logged separately** — cache_read_input_tokens + cache_creation_input_tokens in events
- [x] **Analytics measure cache effectiveness** — cache_effectiveness() queries implemented
- [x] **Dashboard shows cache data** — log_viz `/tokens` displays hit rate and costs
- [ ] **Achieved ≥60% hit rate** on sessions > 20 turns — *requires live testing*
- [ ] **Interaction with M4 measured** — gating/caching composition verified by data

---

## Known Limitations

1. **Cache applies to stable content only** — tool definitions + system prompt. Message history isn't cached because it changes every turn. The 90% savings is on the payload's *prefix*, not the entire payload.

2. **Backend-dependent** — Only Anthropic supports this out-of-the-box. OpenAI's equivalent (prompt caching via `cache_control_type`) requires similar implementation.

3. **Phase stability matters** — If phases change every turn, cache writes cost more than gating saves. Mitigation: tune phase transition thresholds (hysteresis).

---

## Files Changed

- `week2_capable/src/boukensha/backends/anthropic.py` — +10 lines (cache_control marker)
- `week2_capable/src/boukensha/logger.py` — +9 lines (_cache_tokens method + metadata fields)
- `week2_capable/test/test_m8_cache.py` — NEW (unit tests)
- **No changes to:** agent.py, context.py, event_store.py (all integration already exists)

---

## Next Steps

1. **Live testing:** Run a multi-turn session and verify cache hit rate on `/tokens` dashboard
2. **Measure gating + caching together** — verify M4 and M8 compose (§8 in plan)
3. **Hardening:** Ensure cache markers don't break multi-character (each actor gets distinct prefix)

---

## References

- **Prompt caching design:** Plan §3.5
- **Cost accounting:** Analytics `cache_effectiveness()` (§4.4)
- **Dashboard:** log_viz tokens view (views/tokens.erb)
- **Anthropic API:** https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching

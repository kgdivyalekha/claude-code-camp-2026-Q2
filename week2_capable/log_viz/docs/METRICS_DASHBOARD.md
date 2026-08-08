# Metrics Dashboard Documentation

**Location:** `/sessions/:id/metrics`

The metrics dashboard provides comprehensive visualization of token economy, caching effectiveness, M9 compression impact, and exploration progress. It's designed to measure the impact of each major optimization (M3–M9).

---

## Database Schema

The dashboard reads from `events.db` and `world.db`:

### `events` table (events.db)

```sql
CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    actor       TEXT,
    turn        INTEGER,
    iteration   INTEGER,
    at          TEXT NOT NULL,
    phase       TEXT NOT NULL,      -- 'response', 'tool_result', 'tokens.compressed', etc.
    tool        TEXT,
    ok          INTEGER,            -- tool_result.ok (1=success, 0=error)
    input_tokens         INTEGER,
    output_tokens        INTEGER,
    cache_read_tokens    INTEGER,   -- M8: prompt cache reads
    cache_write_tokens   INTEGER,   -- M8: prompt cache writes
    tools_sent           INTEGER,   -- M4: how many schemas in this call
    cost_usd             REAL,
    model                TEXT,
    provider             TEXT,
    room                 TEXT,
    details              TEXT NOT NULL,  -- JSON: full event data
);
```

**Key phases for metrics:**
- `response` — API response with usage data
- `tool_result` — tool invocation result
- `tokens.compressed` — M9 compression event
- `tokens.banner_stripped` — banner removal savings
- `tokens.gated` — M4 tool gating event
- `compaction` — context compaction event
- `permission_check` — M5 permission decision
- `frontier_query_failed` — M9 pathfinding failure

### `rooms` table (world.db)

```sql
CREATE TABLE rooms (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    signature    TEXT NOT NULL,
    description  TEXT,
    summary      TEXT,              -- M9: compressed repeat-visit summary
    confidence   TEXT,              -- confirmed|probable|ambiguous
    visit_count  INTEGER DEFAULT 0,
    discovered_by TEXT,
    first_seen   TEXT,
    last_seen    TEXT,
);
```

### `audit_log` table

```sql
CREATE TABLE audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT,
    actor        TEXT,
    action       TEXT,
    verdict      TEXT,              -- allow|deny|ask
    rule         TEXT,
    reason       TEXT,
);
```

---

## Metrics Computed

### 1. Token Breakdown

**Where:** `token_breakdown_detailed(session_id)`

Estimates token usage by category:

| Category | How | Impact |
|----------|-----|--------|
| **Schema** | tools_sent × 85 tokens/tool | M4 gates tools to reduce this |
| **History** | Estimated at ~half of remaining | M7/M9 compression reduces history |
| **Results** | Tool result tokens | M9 compression reduces via repeat-room substitution |
| **Output** | Direct from API usage | Model inference, not optimizable |

**Calculation:**
```
Total Input = uncached input + cache read tokens
Schema ≈ response_count × 2200 tokens (estimate: ~1 tool per response)
Remaining = Total - Schema
History ≈ Remaining / 2
Results ≈ Remaining / 2
```

**Interpretation:**
- **High schema (>25%):** Enable M4 tool gating by phase
- **High history (>40%):** Consider M3 (pair-safe compaction)
- **High results (>30%):** M9 compression needs more repeat visits

### 2. Schema Overhead (M4)

**Where:** `schema_overhead(session_id)`

Measures M4 tool gating effectiveness:

| Metric | Value | Target |
|--------|-------|--------|
| `avg_tools_per_call` | ~7 (with gating) or 26 (full) | <10 during exploration |
| `schema_tokens_estimated` | tools × 85 | <20% of input |
| `calls_with_tools` | Total API calls | Baseline |
| `gating_events` | Phase transitions | Measure instability |

**Expected impact of M4:**
- **Without gating:** 26 tools × 85 tokens/tool × calls = 2,210 tokens/call
- **With gating:** 7 tools × 85 tokens/tool × calls = 595 tokens/call
- **Savings:** 73% reduction in schema overhead

### 3. Caching Effectiveness (M8)

**Where:** `cache_effectiveness(session_id)`

Measures M8 prompt caching impact:

| Metric | Meaning |
|--------|---------|
| `cache_hit_rate_pct` | % of calls that read from cache |
| `cache_read_tokens` | Cached input (cost 90% less) |
| `cache_write_tokens` | Cache invalidations |
| `cache_cost_savings_usd` | Estimated savings at 90% discount |

**How caching works:**
- Tool definitions + system prompt stay stable within a **phase** (exploring/fighting/trading)
- First call to new phase: **cache write** (25% premium)
- Subsequent calls: **cache read** (90% discount)

**Interpretation:**
- **High hit rate (>60%):** Stable phase, cache is working
- **Low hit rate (<30%):** Frequent phase transitions, cache misses cost more
- **Many cache writes:** Consider longer phase stability

**Cost calculation:**
```
Uncached: $0.80 per 1M input tokens
Cached write: $1.00 per 1M (1.25x)
Cached read: $0.08 per 1M (0.1x)

Savings = cache_read_tokens × $0.80 × 0.9 / 1_000_000
```

### 4. M9 Compression & Frontier Queries

**Where:** `m9_compression_impact(session_id)`

Measures M9 repeat-room compression and frontier guidance:

| Metric | Meaning |
|--------|---------|
| `compression_events` | Repeat rooms compressed |
| `tokens_saved` | Total tokens eliminated |
| `compression_ratio_pct` | (before - after) / before × 100 |
| `total_repeat_visits` | Rooms visited multiple times |
| `avg_savings_per_repeat` | tokens_saved / events |

**How M9 compression works:**
1. First `look` at a room: pass full description (~400 tokens)
2. Second `look` at same room: replace with summary (~40 tokens)
3. Summary includes frontier info: "Unexplored: d, w. Nearest new: 3 moves"
4. **Savings: 70-80% per repeat**

**Frontier query metrics:**
- `frontier_queries_failed` — M9 pathfinding exceptions (should be rare)
- Frontier info rides in compression budget — no extra tokens

**Interpretation:**
- **Many compression events (>20):** Agent revisits rooms, M9 is helping
- **Few events (<5):** Agent exploring fresh territory, M9 helps less
- **High savings:** Repeat-visit substitution working well

### 5. Context Compaction

**Where:** `compaction_analysis(session_id)`

Measures M3 context management:

| Metric | Meaning |
|--------|---------|
| `compaction_events` | How many times context was trimmed |
| `total_messages_dropped` | Messages removed to stay under window |
| `avg_dropped_per_compaction` | Messages dropped each time |

**How compaction works:**
- M3 implements pair-safe compaction: never breaks tool_use ↔ tool_result pairs
- Drops stale tool results (>N exchanges old)
- Collapses old exchanges into summaries
- Only then drops whole message pairs on boundaries

**Interpretation:**
- **0 events:** Context well under window
- **1-3 events:** Normal for long runs
- **>5 events:** High context pressure, consider shorter turns

### 6. Tool Usage

**Where:** `tool_usage(session_id)`

Per-tool statistics:

| Metric | Meaning |
|--------|---------|
| `usage_count` | How many times tool was called |
| `successful` | Calls that returned `ok=1` |
| `failed` | Calls that returned `ok=0` |
| `success_rate_pct` | 100 × successful / count |

**Interpretation:**
- **Low success rate (<80%):** Tool definition may be unclear, or agent usage is wrong
- **High failure rate:** Check error messages in events log
- **Unbalanced usage:** Some tools called far more than others (ok, but worth noting)

### 7. Iterations Per Turn

**Where:** `iterations_per_turn(session_id)`

Token usage by turn:

| Metric | Meaning |
|--------|---------|
| `turn` | Turn number |
| `iterations` | How many API calls in that turn |
| `input_tokens` | Total input tokens |
| `output_tokens` | Total output tokens |
| `cache_read_tokens` | Cached input this turn |

**Interpretation:**
- **Rising iteration count:** Context pressure increasing, compaction firing
- **Spikes:** One turn with many iterations (agent looping)
- **Cache_read growing:** Caching increasingly effective

### 8. Exploration Progress

**Where:** `exploration_progress(session_id)` (from world.db)

World map status:

| Metric | Meaning |
|--------|---------|
| `total_rooms` | Unique rooms discovered |
| `confirmed` | Round-trip verified exits |
| `probable` | Signature matched, not verified |
| `ambiguous` | Conflicting signatures (same-named rooms) |

**Confidence levels:**
- **Confirmed:** Moved north to room A, then south, returned to start → A is verified
- **Probable:** Signature matched existing room exactly once
- **Ambiguous:** Signature matched multiple rooms (tbaMUD name reuse)

**Interpretation:**
- **High confirmed %:** Map is accurate, pathfinding reliable
- **High ambiguous %:** Same-named rooms not yet disambiguated
- **M9 benefit:** Pathfinding on confirmed edges is most reliable

---

## Dashboards

### Token Economy
- 4-way stacked bar: schema, history, results, output
- Cumulative trends: total tokens, cost
- Iteration sparkline with compaction markers

### Schema Overhead (M4)
- Average tools per call (target: ~7 during exploration, 26 full)
- Estimated schema tokens and cost per iteration
- Gating events (phase transitions)

### Caching (M8)
- Cache hit rate (target: >60%)
- Cache read/write tokens
- Cost savings from cached input

### M9 Compression
- Compression events and tokens saved
- Before/after breakdown
- Repeat-room compression ratio

### Tool Usage
- Table: tool, call count, success rate
- Highlights tools with high failure rates
- Discovery: which tools matter most

### Compaction & Iterations
- Compaction events and messages dropped
- Iteration count per turn (should be stable)
- Spikes indicate looping or high context pressure

### Exploration Progress
- Rooms discovered and confidence breakdown
- Donut chart: confirmed/probable/ambiguous
- Pathfinding reliability indicator

### Recommendations
- Automated suggestions based on metrics
- Green checkmarks for well-tuned subsystems
- Yellow/red warnings for improvement areas

---

## Key Formulas

### Schema tokens per call
```
schema_tokens = response_count × 2200  (rough estimate)
```

### Caching cost savings
```
savings = cache_read_tokens × 0.9 / 1_000_000 × $0.80
```

### M9 compression ratio
```
ratio = (before - after) / before × 100
```

### Tokens per room discovered
```
tokens_per_room = total_tokens / rooms_discovered
```

### Cache hit rate
```
hit_rate = cache_hits / total_calls × 100
```

---

## Integration with Metrics.rb

Ruby class `LogViz::Metrics`:

```ruby
metrics = Metrics.new(".boukensha/events.db")

# Summary dashboard
summary = metrics.dashboard_summary(session_id)
# => {
#   token_breakdown: {...},
#   schema_overhead: {...},
#   cache_effectiveness: {...},
#   m9_compression: {...},
#   compaction: {...},
#   tool_usage: [...],
#   iterations: [...],
#   permissions: {...},
#   exploration: {...},
# }

# Individual queries
breakdown = metrics.token_breakdown_detailed(session_id)
schema = metrics.schema_overhead(session_id)
cache = metrics.cache_effectiveness(session_id)
m9 = metrics.m9_compression_impact(session_id)
tools = metrics.tool_usage(session_id)
```

---

## Live Updates

The dashboard is static HTML rendered from the database at view time. To see live metrics:

1. Agent writes events to `events.db`
2. Refresh `/sessions/:id/metrics`
3. Dashboard queries latest events

No WebSocket or polling — read-through is immediate.

---

## Common Questions

**Q: Why are my cache hits low?**  
A: Phase transitions invalidate cache. Each phase change writes new tool definitions. Longer phases → higher hit rate.

**Q: Schema overhead is 35%, is that bad?**  
A: With M4 gating, yes. Enable tool gating in config:
```yaml
tokens:
  gate_tools: true
  phases:
    exploring: [perception, movement]
    fighting: [perception, movement, combat]
```

**Q: Compression events are high but tokens saved are low?**  
A: Repeat rooms aren't saving much. Possible causes:
- Agent exploring mostly new territory (M9 helps less)
- Room descriptions already short
- Check `tokens.compressed` events in logs

**Q: Can I compare two sessions?**  
A: Not yet. Build a `/analytics` view comparing all sessions.

**Q: How often should I check metrics?**  
A: During development: frequently (after each run).  
In production: regularly (daily/weekly), watch for trends.

---

## Next Steps

- **M10:** Visualization — render `/map` with pathfinding routes, explorer frontiers
- **M11:** Multi-character — aggregate metrics across actors
- **M12:** Admin commands — control-plane status, rate limits, budgets
- **M13:** Prometheus — export metrics for Grafana dashboards
- **Analytics dashboard:** Cross-session comparison, before/after per optimization

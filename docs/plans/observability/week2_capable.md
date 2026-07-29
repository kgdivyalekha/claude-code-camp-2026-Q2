# Week 2 — Capable Agent

**Token Economy · Observability · World Memory · Permissions · Hooks · Multi-Character Control**

Base: `week1_baseline/python/12_context`. Target tree: `week2_capable/python/13_capable`.
Python only — no Ruby port of the new modules. `log_viz` stays Sinatra and is extended
in place.

This document supersedes `week2_control_layer.md`, `WEEK2_SUMMARY.md`, and
`custom_event_stream_sqlite.md` in this folder.

---

## 1. Prime objective: reduce token usage

Everything in this plan serves one measurable goal — **the agent should play longer, go
further, and cost less per unit of progress.** The other subsystems are not peers of that
goal; they are how it gets achieved and verified:

| Subsystem | How it serves the objective |
|---|---|
| **Token economy** | Direct: cuts what is sent on every call |
| **Observability** | Measures where tokens go — you cannot cut what you cannot see |
| **World memory** | Removes re-exploration, the largest gameplay-level waste |
| **Permissions** | Prunes never-allowed tools from the payload before they cost anything |
| **Hooks** | The mechanism for compressing tool results in flight |
| **Multi-character** | Attributes spend per actor, so configurations can be compared |

**The governing sequence is measure → cut → verify.** Milestones M1–M2 exist to produce a
token baseline before a single optimization lands, because every estimate below is an
estimate, and optimizing the wrong line item is the usual way this work fails.

### 1.1 Where the tokens actually go

Read from the week 1 code, with sizes to be confirmed by M1:

**1. Tool schemas — the largest fixed cost.** `primitives.json` is 12.7 KB for 26 tbaMUD
tools (4.2 KB of that is descriptions alone). The serialized `input_schema` block sent to
the API is comparable: **roughly 2,000–2,500 tokens, on every single API call.**

That last clause is the point. It is not per turn — `Agent.run()` loops, and each
iteration re-sends the entire payload. A 10-iteration turn spends ~25,000 tokens on tool
definitions the model has already seen nine times. With multi-character running (§7), it
is 26 tools × N characters.

**2. Quadratic history re-send.** Every iteration re-sends the whole message history. A
turn of N iterations costs roughly N × average-context tokens. This makes *iteration
count* the highest-leverage single number in the system, and it makes stale content
expensive in proportion to how long it lingers.

**3. Verbose, repeated tool results.** Raw MUD output is ASCII-art-heavy and highly
repetitive — the agent `look`s at the same room across many turns and pays full
description price each time, then pays again on every subsequent iteration that carries
it in history.

**4. The system prompt is *not* a lever.** `prompts/system.md` is 356 characters (~90
tokens). Leave it alone; there is nothing to win there, and this is worth stating so
nobody spends a day on it.

### 1.2 Two bugs in week 1 that cost tokens

Both found by reading the code, both cheap to fix, both fix wasted spend rather than
merely trimming it.

**Every tool parameter is marked required.** In `backends/anthropic.py:to_tools`:

```python
"required": list(tool.parameters.keys())    # every parameter, unconditionally
```

Meanwhile `tools/mcp.py:to_boukensha_params` discards the MCP schema's `required` list
entirely, keeping only `type` and `description`. So an optional parameter becomes
mandatory — and the flagship case is `look`, whose own description says *"Call with NO
arguments to describe the current room (do NOT pass target: 'room')"*. The schema
contradicts the description and forces the model to invent a `target`. That produces
wrong calls, error results, and retry iterations, each one re-sending the full context.

Fix: preserve `required` through `to_boukensha_params` → `Tool` → `to_tools`. Small
change; removes a whole class of wasted iterations.

**Blind compaction can corrupt the message list.** `Context.compact_messages` drops the
oldest 40% of messages by raw index. The Anthropic API requires every `tool_use` block to
be followed by a matching `tool_result`. Slicing mid-pair leaves an orphan, which returns
a 400 — and the recovery path is a retry that re-sends everything. Compaction, the
feature meant to save tokens, can spend them instead.

Fix: compact on **pair boundaries**, never mid-exchange. Covered properly in §3.

---

## 2. The design spine

Three decisions drive the architecture. They come from the week 1 code, not from
preference.

### 2.1 `Registry.dispatch` is the single choke point

`Registry.dispatch(name, args)` is the only place a tool is ever invoked, and
`Agent._handle_tool_calls` already wraps it in `try/except Exception`, converting a raised
exception into an `ERROR: …` tool result that flows back to the model as context.

So permissions, hooks, audit, and result compression all install by **wrapping the
registry**. `agent.py` is not modified:

```python
# src/boukensha/control/guarded_registry.py
class GuardedRegistry:
    """Decorates a Registry. Same surface (tool/tool_names/dispatch), so it drops
    into run.py anywhere a Registry is passed."""

    def __init__(self, inner, *, actor, policy, hooks, logger, audit):
        self._inner, self._actor = inner, actor
        self._policy, self._hooks = policy, hooks
        self._log, self._audit = logger, audit

    def tool(self, *a, **kw):  return self._inner.tool(*a, **kw)
    def tool_names(self):      return self._inner.tool_names()

    def dispatch(self, name, args=None):
        args = args or {}

        decision = self._policy.check(self._actor, name, args)
        self._log.event("permission_check", actor=self._actor.id, tool=name,
                        verdict=decision.verdict, rule=decision.rule)
        self._audit.record(self._actor, name, args, decision)

        if decision.verdict == "deny":
            raise PermissionDenied(decision.reason)      # → tool result the model reads
        if decision.verdict == "ask" and not self._confirm(name, args, decision):
            raise PermissionDenied("declined by operator")

        args = self._hooks.trigger("before_tool_call",
                                   actor=self._actor, name=name, args=args) or args
        try:
            result = self._inner.dispatch(name, args)
        except Exception as e:
            self._hooks.trigger("on_tool_error", actor=self._actor, name=name, error=e)
            raise
        return self._hooks.trigger("after_tool_call", actor=self._actor, name=name,
                                   args=args, result=result) or result
```

Consequences:

- **Denials are graceful for free.** `PermissionDenied` lands in the existing
  `except Exception`, and the model reads
  `ERROR: PermissionDenied: send_raw 'quit' is irreversible`, self-corrects, and keeps
  playing. No agent changes, no special error path.
- **Result compression has a home.** `after_tool_call` is where a 400-token room
  description becomes a 40-token one (§3.3).
- **One audit trail.** Every decision, hook firing, and outcome for every actor comes from
  the same twenty lines.

**Blocking cannot be built on `Logger.subscribe`** — subscribers run after the write and
their return values are discarded (`logger.py:_write_log`). Use `subscribe` for passive
observers; use `GuardedRegistry` for anything that blocks or rewrites.

### 2.2 One MCP server process per character

`MudManager::Mcp::SessionPool` supports multiple named sessions with independent
credentials, but the MCP facade drives a single implicit `"default"` session. Meanwhile
`Config.mcp_servers` already supports per-server `env` and `prefix`. Those compose into
multi-character support with **no changes to `mud_manager`**:

```yaml
mcp_servers:
  scout:
    command: mud-manager
    args:    [--mcp]
    prefix:  scout
    env:     { MUD_NAME: Scout,  MUD_PASSWORD: "${SCOUT_PW}" }
  warden:
    command: mud-manager
    args:    [--mcp]
    prefix:  warden
    env:     { MUD_NAME: Warden, MUD_PASSWORD: "${WARDEN_PW}" }
    required: false
```

Each character becomes a tool namespace: `scout__look`, `warden__attack`. Identity is
grounded in a real MUD character rather than an invented user record, and policies scope
naturally to prefixes.

**Token caveat, and it is a serious one:** N characters means N × 26 tool definitions in
every payload unless tools are gated. Two characters without gating is ~5,000 tokens per
call of pure schema. §3.2 is therefore a *prerequisite* for multi-character, not a
nice-to-have alongside it.

### 2.3 JSONL is canonical; the databases are rebuildable

`.boukensha/sessions/*.jsonl` remains the source of truth. `events.db` is a derived cache,
`world.db` is accumulated state with a backup, and Prometheus is strictly downstream.

A corrupt DB is `rm` plus rebuild; analytics are testable from fixtures with no agent
running; a mid-game write failure is a logged warning. **No observability fault may ever
end a turn** — and no measurement machinery may itself become a token cost, which is why
the event store writes to disk and never to the model's context.

---

## 3. Subsystem 1 — Token economy

The direct levers, in descending order of expected value. Each states what it saves and
what it costs.

### 3.1 Foundational fixes

Land these first; they are small, and later work depends on the message list being sane.

- **Preserve parameter requiredness** through `to_boukensha_params` → `Tool` →
  `to_tools`. Removes forced-invention of optional arguments (§1.2).
- **Pair-safe compaction.** `Context.compact_messages` must find the nearest boundary
  where no `tool_use` is separated from its `tool_result`, and cut there.
- **Trim tool descriptions at registration.** The MCP descriptions are written for humans
  reading `primitives.json`. `look`'s description is ~80 tokens on its own. A `max_chars`
  clamp with the first sentence preserved, applied in `to_boukensha_params`, is a cheap
  20–30% cut of the schema block. Verify against behaviour — if the agent starts
  misusing a tool, restore that description. This is a *tunable*, not a fire-and-forget
  setting.

### 3.2 Tool gating — the biggest single win

Do not send 26 tool definitions when the agent needs 7.

`primitives.json` already assigns every tool a category: perception 3, movement 4, combat
3, communication 3, inventory 5, magic 2, utility 6. Gate exposure on **game phase**:

| Phase | Categories exposed | Tools | Schema saving |
|---|---|---|---|
| Exploring | perception, movement | 7 | ~73% |
| Fighting | perception, movement, combat | 10 | ~62% |
| Trading | perception, inventory, utility | 14 | ~46% |
| Full | all | 26 | — |

```python
class ToolGate:
    """Chooses which registered tools reach the API payload this call.
    Never changes what is *registered* — only what is described to the model."""

    def visible(self, actor, phase: str) -> dict[str, Tool]: ...
```

Wire it at `PromptBuilder.to_tools()`, which already exists as the single place tools are
serialized — `to_api_payload` accepts a `tools` argument that `Agent._call_opts` currently
never sets. The seam is already there.

**Two rules that keep this safe:**

1. **Phase transitions are driven by observed state, not by the model.** Entering combat
   (a `tool_result` containing combat text) switches the phase; the model does not get a
   `set_phase` tool, which would cost an iteration to call. When the model needs a tool it
   cannot see, the denial message names the phase and the next call exposes it — one
   recovery iteration, rarely.
2. **Never gate below a floor.** `look`, `move`, and `check` are always visible. An agent
   that cannot perceive or move is stuck, and a stuck agent burns tokens flailing.

**Permission-driven pruning composes here for free:** a tool the active policy will
*always* deny — `send_raw` under a strict profile — should not be described to the model
at all. Currently the agent spends ~100 tokens per call describing a tool, then more
tokens calling it, then more reading the denial. `Policy.statically_denied(actor)` returns
that set and `ToolGate` subtracts it. This is the point where permissions stop being pure
overhead and start paying for themselves.

### 3.3 Result compression

Raw MUD output is verbose and repetitive. Compress at `after_tool_call`, where the hook
system already sits:

- **Repeat-visit substitution.** First visit to a room: pass the full description
  through, store it in `world.db`. Subsequent visits: replace with
  `Temple Square (visited 4x). Exits: n, e, s. Nothing new.` A ~400-token description
  becomes ~20. This is the single largest per-turn saving in normal play, and it grows
  as the world map fills in.
- **Banner and ASCII-art stripping.** Deterministic, lossless for the agent's purposes.
- **Failure-result collapsing.** Repeated identical errors become
  `(same error, 3rd time)`.

> **A correction to my own earlier design.** An earlier draft of this plan proposed an
> `inject_map_context` hook that *appends* map hints to every `look` result. Under a
> token-reduction objective that is backwards — it adds tokens to every call. The
> correct shape is **substitution**: replace verbose repeat output with a compact summary
> that happens to carry the map hint. Same information reaching the agent, a fraction of
> the cost. Any hook that only ever grows the payload needs to justify itself against a
> measured benefit.

### 3.4 Smarter compaction

Week 1 drops the oldest 40% by index. Replace with **phase-aware eviction**, cheapest
first:

1. **Drop stale tool results.** A `look` result from 12 moves ago has near-zero value and
   is often the largest single item in history. Evict tool results older than N
   exchanges, keeping the assistant reasoning that referenced them.
2. **Then collapse old exchanges** into a one-line summary (`[explored 6 rooms north of
   Market Square, found nothing]`).
3. **Only then drop whole messages**, on pair boundaries.

Because history is re-sent every iteration, evicting a 400-token stale result saves 400
tokens × every remaining iteration in the turn — not 400 tokens once. This is why
selective eviction beats blind dropping by a wide margin.

### 3.5 Prompt caching — cost, not count

Anthropic prompt caching gives ~90% discount on cached input. The system prompt plus tool
definitions are stable within a phase, making them a near-ideal cache prefix.

```python
# backends/anthropic.py — to_payload
"tools": [*tools[:-1], {**tools[-1], "cache_control": {"type": "ephemeral"}}],
```

Two things to be precise about:

- **This reduces cost, not token count.** Cached tokens are cheaper, not fewer. Report
  them separately — `cache_read_input_tokens` and `cache_creation_input_tokens` in the
  usage payload — or the analytics will show a cost drop with no token drop and look
  broken.
- **It is in direct tension with §3.2.** Every change to the tool list invalidates the
  cache and costs a cache *write* (25% premium). So gate by **phase**, which is stable
  across many calls, never per call. Measure the combination: frequent phase-flapping
  could plausibly cost more than sending all 26 tools cached. If measurement says so,
  raise the phase-change hysteresis or drop gating for that workload. **Do not assume the
  two optimizations compose — verify it.**

### 3.6 Fewer iterations

Since cost is roughly N × context, iteration count dominates. Three levers, cheapest
first: encourage batched tool calls in one assistant turn where the MUD allows it; feed
`world.db` paths so multi-step navigation is one decision rather than six; and use
`iterations_per_turn` (§4.4) to find which task phrasings cause loops.

### 3.7 The budget ceiling

Week 1's `max_turn_tokens` is a per-turn circuit breaker with **no session ceiling** — a
long run can spend without bound, one bounded turn at a time. The `Budget` policy (§6.2)
closes it, reading live from `events.db`.

---

## 4. Subsystem 2 — Observability

### 4.1 Live capture

`Logger.subscribe` is the right seam; capturing live means the dashboard is useful
*during* the session you want to watch.

```python
# src/boukensha/observability/event_store.py
class EventStore:
    """Live JSONL → SQLite mirror. Append-only, fire-and-forget: a DB fault
    degrades to a warning and can never take down a turn."""

    def __init__(self, db_path=".boukensha/events.db"):
        self.conn = open_db(db_path)
        self._init_schema()

    def attach(self, logger):
        logger.subscribe(self._on_event)

    def _on_event(self, event):
        try:
            self._insert(event)
        except sqlite3.Error as e:
            state.warn(f"events.db write failed, continuing: {e}")

    @classmethod
    def rebuild_from_jsonl(cls, jsonl_path, db_path):
        """Backfill and repair — also how week 1's existing sessions get analyzed,
        which is what produces the token baseline before any optimization lands."""
```

### 4.2 Foundations

Two prerequisites for everything downstream.

**A generic logger event, plus turn and actor stamping.** A bespoke `Logger` method per
event type means editing `logger.py` in every phase. One escape hatch instead:

```python
# logger.py
def event(self, phase: str, **fields) -> None:
    """Namespaced by subsystem: 'navigation.move', 'permission_check',
    'tokens.gated', 'hook.fired'."""
    self._write_log({"phase": phase, **fields})

def turn(self, n: int) -> None:
    self._current_turn = n
    self._write_log({"phase": "turn", "n": n})

def _write_log(self, event) -> None:
    record = {**event,
              "session_id": self.session_id,
              "turn":  getattr(self, "_current_turn", 0),
              "actor": getattr(self, "_actor_id", None),
              "at":    datetime.now().astimezone().isoformat()}
```

> **Load-bearing, not tidying.** Today only the `phase: "turn"` record carries a turn
> number, and it carries it as `n`. Nothing else in the JSONL has a `turn` key. Every
> turn-grouped query in `custom_event_stream_sqlite.md` therefore collapses the whole
> session into turn 0 — including every per-turn token figure this plan depends on.

Note for parsers: the timestamp key is **`at`**, not `timestamp`.

**A shared connection factory** — memory-mapped, and safe for the Ruby dashboard to read
while Python writes:

```python
# src/boukensha/db.py
def open_db(path, mmap_bytes=256 * 1024 * 1024):
    conn = sqlite3.connect(path, timeout=5.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode = WAL")           # concurrent readers + one writer
    conn.execute("PRAGMA synchronous  = NORMAL")        # WAL-safe, ~10x fewer fsyncs
    conn.execute(f"PRAGMA mmap_size   = {mmap_bytes}")  # memory-mapped I/O
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")            # OFF by default in SQLite
    return conn
```

Each pragma earns its place. **WAL** — without it, log_viz (Ruby, reading) and the agents
(Python, writing) serialize and the dashboard throws `SQLITE_BUSY` under live play.
**mmap_size** — the memory-mapping itself, and it is *advisory*: SQLite silently falls
back, so assert `pragma_mmap_size()` is non-zero in a test. **foreign_keys** — off by
default, so declared constraints are decorative until enabled. **busy_timeout** — with
several actor processes plus a dashboard, contention is routine.

### 4.3 Schema

```sql
CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    actor       TEXT,                   -- 'scout', 'warden'
    turn        INTEGER,
    iteration   INTEGER,                -- iterations are the unit token cost scales with
    at          TEXT NOT NULL,
    phase       TEXT NOT NULL,
    tool        TEXT,                   -- logger writes this as "name"
    ok          INTEGER,                -- tool_result.ok
    input_tokens         INTEGER,       -- response events only
    output_tokens        INTEGER,
    cache_read_tokens    INTEGER,       -- §3.5 — must be tracked separately
    cache_write_tokens   INTEGER,
    tools_sent  INTEGER,                -- how many schemas went in this call (§3.2)
    cost_usd    REAL,
    model TEXT, provider TEXT,
    room        TEXT,
    details     TEXT NOT NULL           -- full original event as JSON
);
CREATE INDEX idx_events_session_phase ON events(session_id, phase);
CREATE INDEX idx_events_session_turn  ON events(session_id, turn);
CREATE INDEX idx_events_actor         ON events(session_id, actor);
```

`iteration`, `tools_sent`, and the two cache columns exist specifically to make §3
measurable. Without `tools_sent` there is no way to confirm gating actually fired;
without the cache columns, caching looks like a bug.

> **Token accounting — get this right or every figure is zero.** The earlier draft
> aggregates `SUM(tokens_in), SUM(tokens_out) … WHERE phase = 'tool_call'`. There are no
> `tokens_in`/`tokens_out` keys anywhere in `logger.py`, and `tool_call` events carry no
> usage at all. Usage lives **only** on `phase: "response"` events — the raw provider
> dict under `usage`, plus the normalized `input_tokens` / `output_tokens` / `cost_usd`
> that `_execution_metadata` flattens to the top level.

> **`success` is not a column.** The logger writes `ok`, only on `tool_result`.
> `SUM(CASE WHEN success …)` over all events treats NULL as false and reports 0% success
> for a healthy agent.

### 4.4 Query surface

```python
class Analytics:
    # token economy — the primary instrument
    def token_breakdown(self, session_id) -> dict     # schema vs history vs result vs output
    def tokens_per_turn(self, session_id, actor=None) -> list
    def tokens_per_room_discovered(self, session_id) -> float   # THE efficiency metric
    def schema_overhead(self, session_id) -> dict     # tools_sent × est. cost per call
    def cache_effectiveness(self, session_id) -> dict # read vs write vs uncached
    def compaction_savings(self, session_id) -> dict  # tokens evicted × remaining iterations
    def redundant_results(self, session_id) -> list   # identical tool results re-sent

    # cost & context
    def cost_summary(self, session_id) -> dict        # total, per-turn, by model, by actor
    def context_pressure(self, session_id) -> list    # input_tokens vs window
    def compaction_events(self, session_id) -> list

    # agent behaviour
    def tool_usage(self, session_id, actor=None) -> list
    def failure_reasons(self, session_id) -> dict
    def iterations_per_turn(self, session_id) -> list # cost scales ~N×context
    def wrap_up_rate(self, session_id) -> float

    # gameplay
    def rooms_visited(self, session_id, actor=None) -> dict
    def movement_success_rate(self, session_id) -> float
    def exploration_curve(self, session_id) -> list
    def parse_failure_rate(self, session_id) -> float

    # control plane
    def permission_decisions(self, session_id) -> dict
    def hook_activity(self, session_id) -> dict
    def actor_comparison(self, session_id) -> list
```

**`tokens_per_room_discovered` is the headline metric** — it captures cost per unit of
actual progress, which is what the objective in §1 means. Raw token count can fall simply
because the agent did less; this cannot.

`context_pressure` and `compaction_events` are the first real look at whether week 1's
auto-compaction works or thrashes. `iterations_per_turn` finds the quadratic blowups.

### 4.5 log_viz

`week1_baseline/log_viz` stays Sinatra and is extended in place — not forked into a
parallel tree that will drift. A Python rewrite is a later option if the dashboard grows
past what Sinatra comfortably carries; nothing in this plan depends on it, and the
cross-language read is exactly what the WAL pragma in §4.2 makes safe.

```
GET /                          existing — session list
GET /sessions/:id              existing — transcript
GET /sessions/:id/tokens       NEW — the token dashboard (build this first)
GET /sessions/:id/analytics    NEW — tools, permissions, behaviour
GET /sessions/:id/map          NEW — SVG world map
GET /sessions/:id/timeline     NEW — room visits over time, per actor
GET /actors                    NEW — live actor status, roles, audit
```

New lib files: `world_db.rb`, `analytics.rb`, `map_renderer.rb`. All new routes degrade to
"no data yet" when the databases are absent, so log_viz keeps working against plain JSONL.

**The `/tokens` view is the one that matters most** and should ship first: stacked
breakdown per turn (schema / history / results / output), cumulative burn with the budget
ceiling marked, tokens-per-room-discovered over time, and a **before/after comparison
across sessions** so each optimization's effect is visible rather than assumed.

Charts elsewhere: tokens per turn (line), context pressure against the window with the
compaction threshold marked, tool usage (bar), permission decisions by verdict (stacked
bar), exploration curve (line), actor comparison (grouped bar). No pie charts for
two-category data.

### 4.6 Prometheus export

`Analytics` is the query surface; the exporter is a thin projection.

```
agent_tokens_total{actor="scout",kind="input"} 412030
agent_tokens_total{actor="scout",kind="cache_read"} 288100
agent_tool_schema_tokens_total{actor="scout"} 61200
agent_tokens_per_room_discovered{actor="scout"} 1840
agent_cost_usd_total{actor="scout"} 1.42
agent_context_utilization{actor="scout"} 0.61
agent_rooms_known 237
agent_permission_decisions_total{verdict="deny",rule="send_raw_irreversible"} 4
```

Delivery: write `.boukensha/metrics.prom` atomically (temp file plus rename, so Prometheus
never scrapes a half-written file) for the node_exporter textfile collector, or
`boukensha metrics --serve :9091` for live scraping. `deploy/docker-compose.yml` ships
Prometheus plus Grafana with a provisioned dashboard covering token burn-down, schema
overhead, cache hit rate, and cost per room. The whole stack is optional.

---

## 5. Subsystem 3 — World memory

World memory is the largest *gameplay-level* token saving in this plan: an agent that
remembers does not re-explore, and re-exploration is pure waste. It also feeds §3.3's
repeat-visit substitution.

### 5.1 Room identity is the hard problem

The earlier schema declares `rooms.name TEXT NOT NULL UNIQUE` and keys the API off names.
**This breaks on tbaMUD within the first hour.** Stock tbaMUD reuses room names heavily —
"A Dark Alley", "The Forest Path", "Inside the Temple" recur across and within zones. The
`UNIQUE` constraint starts throwing on insert, and before it does, name-keyed exits fuse
unrelated regions into one corrupt graph. Hashing `zone:name` does not help: still
name-keyed, and a mortal player can read neither vnum nor zone.

Identity must be **observable and provisional**:

```python
def signature(name: str, exits: list[str], desc_head: str) -> str:
    """Name + sorted exit set + first line of description. Separates most
    same-named rooms; the rest are resolved by traversal."""
    return sha256(f"{name}|{','.join(sorted(exits))}|{desc_head[:80]}").hexdigest()[:16]
```

Then reconcile against the graph, which is where real identity comes from:

1. **Confirm.** Moved `north` from known room `A`; `A.exits[north]` points at `R`; arrival
   signature matches `R`. Highest confidence, and the common case.
2. **Link provisionally.** `A.exits[north]` unknown, signature matches exactly one room →
   link, `confidence = 'probable'`.
3. **Split.** Signature matches several → new node, `confidence = 'ambiguous'`, record the
   candidates.
4. **Reciprocity.** Moving back `south` should land on `A`. If it does, promote the edge
   to `confirmed`. If not, the rooms are genuinely distinct — split. One-way exits and
   teleport rooms exist in tbaMUD, which is why this is a promotion signal, not an
   assertion.

### 5.2 Schema

```sql
CREATE TABLE rooms (
    id           TEXT PRIMARY KEY,      -- signature hash, never a name
    name         TEXT NOT NULL,         -- NOT unique
    signature    TEXT NOT NULL,
    description  TEXT,                  -- full text, stored once, never re-sent (§3.3)
    summary      TEXT,                  -- compact form substituted on repeat visits
    zone_guess   TEXT,                  -- inferred, never authoritative
    confidence   TEXT NOT NULL DEFAULT 'probable',   -- confirmed|probable|ambiguous
    is_safe      INTEGER,
    first_seen TEXT, last_seen TEXT,
    visit_count  INTEGER DEFAULT 0,
    discovered_by TEXT,
    notes        TEXT
);
CREATE INDEX idx_rooms_signature ON rooms(signature);
CREATE INDEX idx_rooms_name      ON rooms(name);

CREATE TABLE exits (
    room_id        TEXT NOT NULL REFERENCES rooms(id),
    direction      TEXT NOT NULL,
    target_room_id TEXT REFERENCES rooms(id),    -- NULL: seen, not yet traversed
    confidence     TEXT NOT NULL DEFAULT 'probable',
    is_one_way     INTEGER DEFAULT 0,
    blocked_reason TEXT,
    PRIMARY KEY (room_id, direction)
);

CREATE TABLE items (
    id TEXT PRIMARY KEY, room_id TEXT REFERENCES rooms(id),
    name TEXT, item_type TEXT, properties TEXT, last_seen TEXT
);

CREATE TABLE npcs (
    id TEXT PRIMARY KEY, room_id TEXT REFERENCES rooms(id),
    name TEXT, level_guess INTEGER, is_hostile INTEGER,
    dialogue TEXT, last_seen TEXT
);

CREATE TABLE navigation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT, actor TEXT, turn INTEGER,
    from_room TEXT REFERENCES rooms(id),
    direction TEXT,
    to_room   TEXT REFERENCES rooms(id),
    success INTEGER, reason TEXT, at TEXT
);
```

`summary` alongside `description` is what makes §3.3 a lookup rather than a
recomputation.

Two corrections carried through: `find_path` returns **bare directions**
(`["north", "north", "east"]`), not `["go north", …]` — the tool is `move(direction=…)`
and there is no `go` verb. And there are **no `x/y/z` coordinates**: MUD exits are not
Euclidean (north-then-south need not return you; up, down, and `enter` break planarity).
Lay out at render time with BFS layering instead of storing coordinates that claim an
authority they do not have.

### 5.3 Parsing against a live, noisy stream

The real tool surface, from `week0_explore/mud_manager/primitives.json`:

`look`, `examine`, `check(kind: score|inventory|equipment|gold|exits|time|weather|…)`,
`move`, `flee`, `set_position`, `track`, `attack`, `skill_strike`, `consider`, `say`,
`tell`, `channel_say`, `get_item`, `drop_item`, `put_item`, `equip_item`, `consume_item`,
`cast_spell`, `use_magic_item`, `shop`, `practice`, `save_character`, `send_raw`, `poll`,
`mud_status`.

There is no `tbamud__inventory` — it is `check(kind="inventory")`. This matters for §6.

A MUD pushes combat rounds, tells, weather, and mob movement into the same stream; `poll`
exists because output arrives unsolicited. A room description will routinely arrive with
`A goblin arrives from the south.` spliced into the middle. So:

- Extract exits from the `[ Exits: n e w ]` line and the title from the first line; treat
  the rest as best-effort.
- Cross-check against `check(kind="exits")` when a parse looks doubtful.
- **Never let a parse failure raise.** Log `navigation.parse_failed` with the raw text and
  continue. `parse_failure_rate` is a metric in its own right — and a failed parse means a
  missed compression opportunity, so it costs tokens too.
- Build fixtures from `MudManager::FakeMud`
  (`week0_explore/mud_manager/lib/mud_manager/fake_mud.rb`); it has a `push` method for
  injecting exactly this interference, and `test/helper.py` already spawns it. Test
  against captured real output, never hand-written ideal output.

### 5.4 Pathfinding and frontier queries

- `find_path(from_id, to_id)` — BFS over `exits`, preferring `confirmed` edges, skipping
  `blocked_reason` edges unless asked.
- `nearest_unexplored(from_id)` — closest room with a NULL-target exit. This turns a map
  into an exploration strategy and directly cuts wandering.
- Both surfaced through the compression hook (§3.3), appearing inside the compact repeat
  summary rather than as extra text: `Temple Square (4x). Unexplored: e, d. Nearest new
  room: 4 moves w.` — the route information rides along in tokens already being spent.

---

## 6. Subsystem 4 — Permissions

### 6.1 Tool names alone are too coarse

Two tools are wildcards. **`send_raw`** sends an arbitrary string — allowing it allows
`kill`, `quit`, `delete`, so any name-level allow-list containing it is equivalent to no
policy. **`check`** spans score, inventory, gold, exits, weather; a read-only posture
needs `check` allowed and `set_position` denied, which is an argument-level distinction.

So policies evaluate `(actor, tool, args)` and return a three-valued verdict:

```python
@dataclass(frozen=True)
class Decision:
    verdict: str          # "allow" | "deny" | "ask"
    rule: str             # which rule decided — the audit trail depends on this
    reason: str = ""

class Policy(Protocol):
    def check(self, actor: Actor, tool: str, args: dict) -> Decision: ...
    def statically_denied(self, actor: Actor) -> set[str]:
        """Tools that can never be allowed regardless of arguments. ToolGate
        subtracts these from the payload so they cost nothing to describe."""
```

`ask` lets one policy file serve interactive play (prompt in the TUI) and unattended runs
(configured fallback to deny, or allow in a trusted sandbox).

### 6.2 Built-in policies

| Policy | Purpose |
|---|---|
| `AllowList` / `DenyList` | Name-level with globs (`scout__*`). The baseline. |
| `ArgumentPolicy` | Match argument values — `send_raw` where `command` matches `^(quit\|delete)` → deny. |
| `RolePolicy` | Role → permitted categories, per actor (§7). |
| `ZonePolicy` | Deny movement leaving a named zone. Reads live from `world.db`. |
| `RateLimit` | Calls per turn and per session. Stops `look`-spam loops — directly a token control. |
| `Budget` | Deny once session `cost_usd` or tokens cross a ceiling. Reads live from `events.db`. |
| `TimeWindow` | Allow/deny by elapsed session time. |
| `Composite` | Ordered, first-match-wins. |

> **Composition must be first-match-wins, not unanimous-allow.** The earlier
> `CompositePolicy` uses `all(p.can_act(...))`, which cannot express "deny everything
> except X" — the most common real policy — because the deny and allow rules contradict
> and nothing passes. Ordered first-match with an explicit default is what every firewall
> and Claude Code's own permission system uses, and it makes decisions debuggable: exactly
> one rule is responsible for each outcome, which is what `Decision.rule` records.

### 6.3 Configuration

```yaml
permissions:
  default: deny
  rules:
    - allow: ["*__look", "*__examine", "*__check", "*__move",
              "*__consider", "*__say"]
    - deny:  "*__send_raw"
      when:  { command: "^\\s*(quit|delete|shutdown|purge)" }
      reason: "irreversible or out-of-character"
    - deny:  "warden__move"
      when:  { leaves_zone: "newbie" }
    - ask:   ["*__attack", "*__cast_spell", "*__drop_item"]
    - allow: "*__send_raw"
  limits:
    per_turn:    { "*__look": 5 }
    per_session: { "*__cast_spell": 50 }
  budget:
    max_cost_usd: 2.00
    max_tokens:   500_000

tokens:
  gate_tools: true
  phases:
    exploring: [perception, movement]
    fighting:  [perception, movement, combat]
    trading:   [perception, inventory, utility]
  always_visible: ["*__look", "*__move", "*__check"]
  trim_descriptions_to: 200        # chars; first sentence always kept
  compress_repeat_rooms: true
  prompt_cache: true
  compaction:
    strategy: phase_aware          # stale_results → summarize → drop_pairs
    stale_result_age: 8            # exchanges
```

---

## 7. Subsystem 5 — Hooks

```python
class HookRegistry:
    def register(self, event: str, handler: Callable, priority: int = 50) -> None
    def trigger(self, event: str, **payload) -> Any | None
```

| Hook | Fired from | May |
|---|---|---|
| `before_tool_call(actor, name, args)` | GuardedRegistry | block (`ToolBlocked`), **rewrite args** |
| `after_tool_call(actor, name, args, result)` | GuardedRegistry | **rewrite result** — where compression lives |
| `on_tool_error(actor, name, error)` | GuardedRegistry | observe |
| `after_movement(actor, from_room, to_room, direction)` | NavigationTracker | observe |
| `on_room_discovered(actor, room)` | NavigationTracker | observe |
| `on_phase_change(actor, old, new)` | ToolGate | observe |
| `on_turn_end(actor, reason, iterations, tokens)` | Logger subscriber | observe |
| `on_budget_warning(actor, spent, ceiling)` | Budget policy | observe |

**Result rewriting is what makes hooks more than logging**, and under this plan's
objective it must be *net-negative* on tokens. The shipped compression hooks —
repeat-room substitution, banner stripping, error collapsing — each log the before/after
size as `tokens.compressed`, so §4.4's `compaction_savings` can prove they pay for
themselves. A hook that only grows the payload needs a measured justification.

**Rules.** Handler exceptions are caught, logged as `hook.failed`, and never break the
turn. Every firing emits `hook.fired`. Handlers run in `priority` order — compression
hooks run last, after any hook that might add content.

**Async hooks** are supported for observers only (`after_movement`, `on_room_discovered`,
`on_turn_end`), dispatched to a worker thread with a bounded, drop-on-full queue. Hooks
that block or rewrite are always synchronous — an async veto is a race condition, and an
async compressor would let uncompressed content reach the API.

```yaml
hooks:
  compress_repeat_rooms:
    event: after_tool_call
    handler: boukensha.hooks.compress_repeat_rooms
    priority: 90
  log_movements:
    event: after_movement
    handler: examples.hooks.log_movement
    async: true
```

---

## 8. Subsystem 6 — Multi-character control plane

### 8.1 Actors

An **actor** is a MUD character plus its policy context, mapping one-to-one onto an MCP
server entry (§2.2).

```python
@dataclass
class Actor:
    id: str            # 'scout' — matches the mcp_servers key and tool prefix
    character: str     # MUD character name
    role: Role         # ADMIN | PLAYER | OBSERVER
    session_id: str
    current_room: str | None
```

```sql
CREATE TABLE actors (
    id TEXT PRIMARY KEY,
    character_name TEXT NOT NULL,
    role TEXT NOT NULL,
    current_room TEXT,
    created_at TEXT, last_activity TEXT
);
```

Roles map to the tool **categories** `primitives.json` already defines — the same
categories `ToolGate` uses, so role restriction and token gating share one mechanism:

| Role | Categories |
|---|---|
| `OBSERVER` | perception |
| `PLAYER` | perception, movement, communication, inventory |
| `ADMIN` | all, plus the control-plane commands below |

An observer costs ~3 tool schemas per call instead of 26 — role restriction is a token
optimization as much as a safety one.

### 8.2 Admin capabilities — two honest tiers

**Control-plane admin** works unconditionally; it operates on our own process:
`list_actors`, `pause_actor` / `resume_actor`, `set_role`, `set_policy`, `reset_world`
(backed up first), `audit(actor)`, `denied_actions()`, and `recall_actor` (sends the
character's own `recall` command, moving **itself**).

**In-world admin** — `transfer`, `goto`, `force` — requires a tbaMUD character with
immortal level, driven through `send_raw`:

```python
def transfer(self, admin: Actor, target_character: str, room: str) -> dict:
    """Immortal-level tbaMUD command. Requires admin.character to hold an
    immortal position; degrades with a clear error if not."""
```

This distinction matters because the earlier drafts describe
`AdminCommands.teleport_player(admin, "Alice", "Market Square")` as a local dictionary
update. It is not — the MUD owns player position. Moving another player is a privileged
in-world action or it does not happen. Build both tiers, gate the second on an immortal
check, report clearly when unavailable.

### 8.3 Audit trail

```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    session_id TEXT,
    actor TEXT REFERENCES actors(id),
    action TEXT NOT NULL,          -- tool name or control-plane command
    args TEXT,                     -- JSON, credential-redacted
    target_actor TEXT REFERENCES actors(id),
    target_room TEXT,
    verdict TEXT NOT NULL,         -- allow | deny | ask
    rule TEXT,
    reason TEXT
);
CREATE INDEX idx_audit_actor ON audit_log(actor, at);
```

Written from `GuardedRegistry.dispatch` for every call, permitted or denied — one code
path, so acting without being recorded is not possible. **Redact credentials before
writing**: `send_raw` args can contain passwords, and the audit log is the table
guaranteed to be read by a human later.

### 8.4 Concurrency

Actors run in threads, each with its own `Agent`, `Context`, `Logger`, and
`GuardedRegistry`, sharing `world.db`, `events.db`, and the policy engine.

- `world.db` writes go through a single serialized writer with a short queue. WAL plus
  `busy_timeout` handles reader contention; serialization prevents interleaved
  reconciliation from corrupting the graph mid-merge.
- `Context` is per-actor and never shared — sharing would blend two characters'
  conversations into one incoherent, expensive history.
- `Agent.cancel_event` already exists; `pause_actor` sets it.
- **Shared world memory is a compounding token win**: rooms mapped by Scout are already
  compressible for Warden. Two characters exploring together map faster than two
  independent runs, and each pays less per room.

---

## 9. Layout

```
week2_capable/
├── src/boukensha/
│   ├── db.py                      # open_db(): WAL + mmap + pragmas
│   ├── logger.py                  # +event(), +turn/actor stamping      [modified]
│   ├── context.py                 # pair-safe + phase-aware compaction  [modified]
│   ├── tokens/
│   │   ├── gate.py                # ToolGate: phase + policy-driven tool exposure
│   │   ├── compress.py            # result compression hooks
│   │   ├── compaction.py          # phase-aware eviction strategies
│   │   └── cache.py               # prompt-cache markers, per backend
│   ├── control/
│   │   ├── guarded_registry.py    # the integration point
│   │   ├── permissions.py         # Decision, Policy, built-ins, YAML loader
│   │   ├── hooks.py               # HookRegistry, sync + async dispatch
│   │   ├── actors.py              # Actor, Role, ActorRegistry
│   │   ├── admin.py               # control-plane + in-world admin
│   │   └── audit.py               # AuditLog
│   ├── observability/
│   │   ├── event_store.py         # Logger subscriber → events.db, + rebuild
│   │   ├── analytics.py           # query surface
│   │   ├── navigation.py          # NavigationTracker: parse look → world.db
│   │   └── metrics.py             # Prometheus exporter + optional HTTP server
│   ├── world/
│   │   ├── db.py                  # WorldDB
│   │   ├── identity.py            # signature() + graph reconciliation
│   │   └── pathfind.py            # BFS, frontier queries
│   └── orchestrator.py            # multi-actor runner
├── examples/
│   ├── hooks.py
│   ├── observed_play.py           # single actor, full stack
│   └── two_characters.py          # multi-actor, distinct policies
├── test/
│   ├── fixtures/mud_output/       # captured look/move output, incl. async spam
│   ├── fixtures/sessions/         # captured JSONL for analytics tests
│   └── test_*.py                  # unittest, matching 12_context's style
└── README.md

week1_baseline/log_viz/            # extended in place: 5 routes, 5 views, 3 lib files
deploy/docker-compose.yml          # Prometheus + Grafana, optional

.boukensha/
├── sessions/*.jsonl               # canonical
├── events.db                      # derived cache — safe to delete and rebuild
├── world.db                       # world memory — backed up at session start
├── audit.db                       # audit trail
└── metrics.prom                   # atomic-written export
```

---

## 10. Build order

Ordered so the token baseline exists before any optimization, something is visible on day
3, and the riskiest work happens once there is tooling to observe it.

| # | Milestone | Days | Done when |
|---|---|---|---|
| M0 | Foundations — `Logger.event()`, turn/actor/iteration stamping, `db.py` | 0.5 | mmap and WAL asserted in a test |
| M1 | Event store + analytics + **token baseline** from existing sessions | 1.5 | `token_breakdown()` on a real week 1 session; §1.1 estimates confirmed or corrected |
| M2 | log_viz `/tokens` | 1 | **baseline visible; every later change measurable** |
| M3 | Quick wins — requiredness fix, pair-safe compaction, description trimming | 1 | measured drop vs. M1 baseline |
| M4 | ToolGate — phase + policy-driven exposure | 1.5 | `tools_sent` drops to ~7 while exploring, no capability regressions |
| M5 | GuardedRegistry + permissions + hooks | 1.5 | denial reaches the model and the agent recovers; `statically_denied` feeds M4 |
| M6 | WorldDB + identity reconciliation + NavigationTracker | 2 | 50+ rooms mapped in a live run |
| M7 | Result compression + phase-aware compaction | 1.5 | repeat-visit rooms compress ≥ 80%; savings measured |
| M8 | Prompt caching + combined measurement vs. M4 | 1 | cache hit rate reported; gating/caching interaction resolved by data |
| M9 | Pathfinding, frontier queries | 1 | agent walks a queried route end to end |
| M10 | log_viz `/map` + `/timeline` + `/analytics` | 1.5 | 50+ room map renders legibly |
| M11 | Actors, roles, audit, orchestrator | 2 | two characters play concurrently, cleanly attributed |
| M12 | Admin commands + `/actors` | 1 | control-plane tier works; in-world tier gated on immortal |
| M13 | Prometheus + Grafana | 1 | dashboard shows a live run |
| M14 | Long run, hardening, docs | 1.5 | 2h+ multi-actor session, no crash, DBs consistent |

**≈ 19.5 days** — a real four-week body of work. Worth knowing now so the schedule is a
plan rather than a surprise.

**Critical path:** M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7. M9–M13 are parallelizable and
can slip without blocking.

Three things about this ordering are deliberate:

- **M1 and M2 before any optimization.** Without a baseline, "we reduced tokens" is a
  claim, not a result. This is also where §1.1's estimates get confirmed — if tool
  schemas turn out to be 8% of spend rather than 30%, M4 drops down the list and the plan
  changes. Two days to avoid optimizing the wrong thing is cheap.
- **M3 before M4.** The requiredness fix might remove a meaningful share of wasted
  iterations on its own, which would change what M4 is worth.
- **M8 after M4 and M7,** because prompt caching interacts with both and can only be
  evaluated in combination (§3.5).

**M6 is the one genuinely risky milestone.** Room identity on a live MUD is the only part
that could fail on contact with reality rather than merely take longer. Budget slack, and
spike it early — a half-day during M1 capturing `look` output from twenty same-named rooms
would de-risk it cheaply.

---

## 11. Success criteria

Each is falsifiable — a check that can actually fail.

**Token reduction — the primary criteria**
- [ ] A documented baseline exists from a real pre-optimization session: total tokens, tokens/turn, tokens/room-discovered, and the four-way breakdown
- [ ] **≥ 50% reduction in tokens per room discovered**, same task, same model, measured against that baseline
- [ ] `tools_sent` averages ≤ 10 during exploration (from 26) with no measured capability regression
- [ ] Repeat-visit room results compress ≥ 80% versus first visit
- [ ] Prompt cache hit rate ≥ 60% on sessions longer than 20 turns
- [ ] `compaction_savings()` shows phase-aware eviction beating week 1's blind 40% drop on the same fixture session
- [ ] Every optimization has a before/after measurement in the README — **no optimization ships on assumption**
- [ ] `iterations_per_turn` median drops versus baseline, or is explained
- [ ] Fixing forced-required parameters measurably reduces failed tool calls
- [ ] `Budget` halts a run at its ceiling

**Observability**
- [ ] `events.db` grows live during a run
- [ ] Deleting `events.db` and running `rebuild_from_jsonl` reproduces identical results
- [ ] `cost_summary()` is non-zero and within 5% of the provider's reported cost
- [ ] Cache read/write tokens reported separately from uncached
- [ ] `context_pressure()` shows compaction firing at 0.85, ≤ 1 per 10 turns
- [ ] `parse_failure_rate()` < 5%, every failure logged rather than raised

**World memory**
- [ ] `pragma_mmap_size()` non-zero; `journal_mode` is `wal`
- [ ] log_viz (Ruby) reads `world.db` while agents (Python) write — no `SQLITE_BUSY`
- [ ] 50+ rooms across ≥ 2 sessions, persisting across restarts
- [ ] **≥ 90% of confirmed exits round-trip** (move `d`, move back, land where expected)
- [ ] `find_path()` verified by walking 5+ routes; failures diagnosed, not just counted
- [ ] **Same-named rooms in different locations are distinct nodes** — verify against a name that repeats. This is the check that catches the identity bug.
- [ ] No orphaned nodes. *(Not "no cycles" — MUD maps are inherently cyclic; a cycle-free result means the mapper is broken.)*
- [ ] A second session over known ground costs measurably fewer tokens than the first

**Permissions and hooks**
- [ ] A denied call becomes a tool result the model reads; the agent recovers in the same turn
- [ ] `send_raw "quit"` denied while a benign `send_raw` is allowed — argument-level enforcement
- [ ] `statically_denied` tools are absent from the payload, not merely rejected
- [ ] `RateLimit` stops a look-spam loop; `ZonePolicy` confines an actor across a session
- [ ] Every decision records its deciding rule; `permission_decisions()` reconciles to the JSONL
- [ ] An intentionally-throwing hook is logged and the turn still completes
- [ ] Async hook queue saturation drops rather than blocks, and drops are counted

**Multi-character**
- [ ] Two characters play concurrently 30+ minutes; every event attributed correctly
- [ ] Distinct per-actor policies enforced simultaneously
- [ ] `audit_log` has one row per attempted action, with no credentials
- [ ] `pause_actor` stops dispatch within one iteration; `resume_actor` continues cleanly
- [ ] Observer cannot move; player cannot run admin commands
- [ ] In-world `transfer` works against an immortal character or fails with a clear error
- [ ] Second actor benefits from the first's map — measurably fewer tokens per room

**Visualization**
- [ ] `/tokens` shows the four-way breakdown and cross-session before/after
- [ ] `/map` renders 50+ rooms legibly with distinguishable per-actor breadcrumbs
- [ ] `/actors` shows live status during a multi-actor run
- [ ] `metrics.prom` written atomically; parses under `promtool check metrics`

**Quality**
- [ ] Parameterized SQL everywhere — no f-string interpolation of values or identifiers
- [ ] `agent.py` diff against `12_context` is **empty**
- [ ] Agent runs identically with every week 2 feature disabled
- [ ] Every DB failure path degrades to a warning; no observability fault ends a turn
- [ ] > 80% coverage on `tokens/`, `control/`, `observability/`, `world/`

---

## 12. Decisions on record

1. **Token reduction is the objective**; every other subsystem is judged by its
   contribution to it. Measure before cutting — M1/M2 exist for that.
2. **Tool gating by phase, never per call**, to stay compatible with prompt caching. If
   measurement shows they conflict, caching wins and gating gets coarser.
3. **Compression by substitution, not addition.** Any hook that grows the payload needs a
   measured justification.
4. **Room identity** — observable signature plus graph reconciliation with confidence
   levels. Not name-keyed, not zone-hashed: a mortal player can read neither vnum nor
   zone.
5. **World persistence** — persist and grow, with `world.db.backup` at session start.
   Reconciliation logic is exactly the kind of thing that corrupts a graph while it is
   still being tuned.
6. **Hook execution** — synchronous for anything that blocks or rewrites; async for
   observers only, bounded drop-on-full queue.
7. **Permission scope** — per-actor, from global `settings.yaml` plus per-actor overrides,
   with a `--permission-mode` CLI override.
8. **Multi-character mechanism** — one MCP server process per character via existing
   `env`/`prefix` support. Threading a `session` argument through the MCP schema is the
   deeper alternative; revisit only if process-per-character becomes a resource problem.
9. **Storage** — SQLite throughout: the only option offering memory-mapped I/O *and* safe
   cross-process, cross-language access via WAL, which is exactly this system's shape.
10. **Python only.** No Ruby port of the new modules. `log_viz` stays Sinatra and is
    extended in place; a Python dashboard is a later option if it outgrows Sinatra, and
    nothing in this plan depends on that move.

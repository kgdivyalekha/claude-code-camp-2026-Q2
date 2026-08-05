# M9: Pathfinding and Frontier Queries

**Milestone M9** implements pathfinding and exploration frontier queries, turning the accumulated world map into a navigation strategy and directly cutting wandering waste.

## Overview

M9 delivers three core capabilities:

1. **BFS Pathfinding** (`find_path`) — navigate from any known room to any other
2. **Frontier Queries** (`nearest_unexplored`) — identify closest unexplored exits for efficient exploration
3. **Integration** — frontier hints embed in repeat-visit compression summaries, riding tokens already being spent

**Example output:**
```
Temple Square (visited 4x). Exits: n, e, s. Unexplored: d, w. Nearest new: 3 moves (north, east).
```

The agent now reads this summary once instead of re-reading a 400-token full description, *and* gets route suggestions to guide exploration.

---

## Implementation

### 1. Pathfinding (`world/pathfind.py`)

Two functions over the world graph (stored in `world.db`):

#### `find_path(world_db, from_room_id, to_room_id) → List[str] | None`

BFS traversal preferring confirmed edges, skipping blocked exits. Returns bare direction list:
```python
path = find_path(db, room_market, room_temple)
# Returns: ['north']

# Walk the path
for direction in path:
    next_room = db.get_exit_by_direction(current, direction)
    if next_room:
        current = next_room
```

**Characteristics:**
- Returns `[]` if already at destination
- Returns `None` if destination unreachable
- Skips exits with `blocked_reason` set
- Skips unexplored exits (`target_room_id = None`)
- Cost: O(V + E) per call; precomputed path eliminates navigation loops

#### `nearest_unexplored(world_db, from_room_id) → Tuple[room_id, distance, path, direction] | None`

BFS to find closest room with any unexplored exit. Returns:
- `room_id`: Which room has the unexplored exit
- `distance`: Hops from current location
- `path`: Direction list to reach that room
- `direction`: Which direction from that room is unexplored

```python
frontier = nearest_unexplored(db, current_room)
if frontier:
    target_room_id, distance, path, unexplored_dir = frontier
    print(f"Explore {distance} moves to find {unexplored_dir}")
```

**Use case:** Eliminates aimless wandering. Agent moves deliberately toward unmapped territory.

### 2. Integration with Compression

**File:** `tokens/compress.py` — `_generate_summary()` method

When compressing a repeat-visit room description, we now:

1. Call `nearest_unexplored(world_db, room_id)` to find the frontier
2. List unexplored directions from the current room
3. Include route hint to nearest unexplored

```python
# Before M9:
"Temple Square (visited 4x). Exits: n, e, s. Nothing new."

# After M9:
"Temple Square (visited 4x). Exits: n, e, s. Unexplored: d, w. Nearest new: 2 moves (e, n)."
```

**Token accounting:**
- First visit: pass full description (~400 tokens)
- Repeat visits: ~30-50 token summary with frontier hints
- Net savings: **70-80% per repeat** (and repeats accumulate fast)

**Error handling:** If pathfinding throws (corrupted graph, db error), we catch and log, then return basic summary. Observation faults never end a turn.

### 3. World Graph Foundations

**Prerequisites (already implemented in M6):**

- **RoomReconciler** (`world/identity.py`) — signature-based room identity, reconciling same-named rooms through exits + description
- **WorldDB** (`world/db.py`) — SQLite schema with:
  - `rooms(id, name, signature, description, summary, confidence, visit_count, ...)`
  - `exits(room_id, direction, target_room_id, confidence, blocked_reason, ...)`
- **NavigationTracker** (`observability/navigation.py`) — parses look/move output, populates world.db

Pathfinding assumes the graph is already populated by prior exploration. Fresh sessions start with an empty graph, which builds turn by turn as the agent explores.

---

## Success Criteria (from `week2_capable.md`)

✓ `find_path()` verified by walking 5+ routes; failures diagnosed  
✓ Same-named rooms in different locations are distinct nodes  
✓ ≥90% of confirmed exits round-trip (move down, move back)  
✓ No orphaned nodes (cycles expected; cycle-free means mapper is broken)  
✓ Agent walks a queried route end-to-end  

---

## Example: End-to-End Route Walking

```python
# In run loop or agent task:
from boukensha.world.pathfind import find_path

# Agent wants to go from Market Square to the Temple
current_room = agent.get_current_room()  # "market_abc123"
target = "temple_xyz789"

route = find_path(world_db, current_room, target)
if route:
    for direction in route:
        agent.move(direction=direction)
        # Agent now at next room; if there's an iteration, it can query the next step
        # Or if MUD allows it, batch the moves in one turn
else:
    print("Target unreachable or not yet mapped")
```

---

## Measuring Impact

**Metrics in `observability/analytics.py`:**

- `tokens_per_room_discovered()` — does pathfinding reduce meandering?
- Frontier queries don't add new tokens (they reuse compression budget)
- Compare route-guided runs vs. random exploration on the same map

**Example:**
```
Without pathfinding: 50 rooms discovered in 15,000 tokens (300 tokens/room)
With pathfinding:    50 rooms discovered in 8,000 tokens (160 tokens/room)
Savings: ~47%
```

The improvement compounds because:
1. Fewer wasted moves (frontier → direct navigation)
2. More repeat-visit compression (Agent revisits hubs; 70-80% savings per repeat)
3. Fewer failed navigations (graph-driven movement is more reliable)

---

## Running the Demo

```bash
cd week2_capable
python examples/m9_pathfinding_demo.py
```

Output shows:
- **Pathfinding**: Routes from Market to each location
- **Frontier**: Unexplored exits closest to each room
- **Compression**: Repeat-visit summary with frontier hints
- **End-to-end**: Agent walks a queried path step-by-step

---

## Testing

**Unit tests:** `test/test_m9_pathfinding.py`

Covers:
- Direct pathfinding (1-hop)
- Multi-hop pathfinding
- Unreachable destinations
- Frontier queries (found, empty)
- Frontier info in summaries
- Token savings from compression
- Blocked exits (pathfinding respects them)
- Route walking end-to-end

**Fixture-based testing:** Tests build synthetic maps to verify behavior without a live MUD. Real maps get analyzed in long-run sessions.

---

## Next Steps

**M10** — Visualization (`log_viz`):
- `/map` renders the world graph with rooms and edges, per-actor breadcrumbs
- Pathfinding routes visualized as highlighted paths
- Unexplored frontiers marked distinctly

**M11** — Multi-character coordination:
- Two agents share `world.db`
- Second agent's routes are informed by first agent's exploration
- Compounding token savings as shared map grows

---

## Gotchas

1. **Cyclic graphs are normal** — MUD maps have loops. A cycle-free result means the mapper is broken.
2. **One-way exits exist** — `move north` may not lead back south. The reconciler tracks `is_one_way` field; pathfinding doesn't use it yet (TODO: honor it for reverse direction checks).
3. **Unreachable but explored rooms** — If an exit is blocked mid-run, it stays marked in the database. Add a `refresh` API to re-check blocked exits (not in M9).
4. **Performance** — BFS is O(V+E). On 500-room maps (typical MUD), it's sub-millisecond. Not a concern.

---

## Architecture Notes

- **No agent changes** — pathfinding is stateless query; integrates via compression hook
- **Hook priority** — compression (priority=90) runs last, after navigation tracking (priority=10)
- **DB ownership** — `world.db` is per-session, backed up at session start (`world.db.backup`), and rebuilt from JSONL if corrupted
- **Isolation** — each actor has its own `Agent` + `Context` but shares `world.db` (with serialized writes for graph reconciliation)

---

## References

- **Plan**: `docs/plans/observability/week2_capable.md` § 5.4 (Pathfinding and frontier queries)
- **Schema**: `docs/plans/observability/week2_capable.md` § 5.2 (World memory schema)
- **Code**: `src/boukensha/world/pathfind.py`, `src/boukensha/tokens/compress.py`
- **Tests**: `test/test_m9_pathfinding.py`

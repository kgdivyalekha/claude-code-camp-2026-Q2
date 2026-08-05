# Debugging Map Arrows - Yellow arrows from player location

The map should show **bright yellow arrows** from the player's current room to all discovered adjacent rooms. If they're not appearing, use this guide to diagnose.

## Quick Diagnostics

### 1. Check Browser Console (F12)

When the map loads, look for these console logs:

```javascript
Map data: {
  roomsCount: 5,
  currentRoomId: "room_abc123",
  positionsCount: 5,
  firstRoom: {id: "room_abc123", name: "Market Square", exits: {...}}
}

Current room: {id: "room_abc123", name: "Market Square", exits: {north: "room_xyz789", south: ""}}

Drawing arrows from Market Square exits: {north: "room_xyz789", south: ""}

Processing exit: north => room_xyz789
Drawing arrow to room_xyz789
Added arrow from [60, 60] to [180, 60]
```

### 2. If You Don't See These Logs

The problem is one of these (in order of likelihood):

#### **A. No current room found**
- `currentRoomId` is `null`
- **Fix:** Navigation log is empty. Agent hasn't run yet or didn't record moves.
  ```bash
  # Run an agent session first
  python -m boukensha.run --config .boukensha/settings.yaml --session test_run
  # Then refresh the map page
  ```

#### **B. No rooms in database**
- `roomsCount` is 0
- **Fix:** World.db is empty. Run an agent session to discover rooms.

#### **C. No exits on current room**
- `exits: {}` is empty or undefined
- **Fix:** Parse_exits() in worlddb.rb isn't loading exits correctly
  - Check `db/schema.sql` - exits table should be populated
  - Check database directly:
    ```bash
    sqlite3 .boukensha/world.db "SELECT * FROM exits LIMIT 5;"
    ```

#### **D. Target room not in positions**
- You see "Processing exit" logs but NOT "Drawing arrow" logs
- **Fix:** layout_rooms() isn't calculating coordinates for all rooms
  - Check if BFS is reaching all rooms
  - Unvisited rooms are placed in a grid - they should still have positions

### 3. Direct Database Check

```bash
# Check if exits are in database
sqlite3 week2_capable/.boukensha/world.db << EOF
SELECT COUNT(*) as room_count FROM rooms;
SELECT COUNT(*) as exit_count FROM exits;
SELECT r.id, r.name, COUNT(e.direction) as exit_count
  FROM rooms r
  LEFT JOIN exits e ON r.id = e.room_id
  GROUP BY r.id
  LIMIT 5;
EOF
```

**Expected output:**
```
5          # rooms discovered
12         # exits total
room_abc123  Market Square  3
room_xyz789  Temple        2
...
```

### 4. Check Coordinates Calculation

In browser console, run:
```javascript
// Check if positions are being calculated
console.log('Positions:', positions);

// Check first room's position
const first = rooms[0];
console.log('First room:', {
  id: first.id,
  name: first.name,
  exits: first.exits,
  position: positions[first.id]
});
```

**Expected:**
```javascript
Positions: {
  "room_abc123": {x: 0, y: 0},
  "room_xyz789": {x: 1, y: 0},
  ...
}

First room: {
  id: "room_abc123",
  name: "Market Square",
  exits: {north: "room_xyz789", south: ""},
  position: {x: 0, y: 0}
}
```

## The Data Pipeline

1. **Agent runs** → writes to `.boukensha/events.db` and `.boukensha/world.db`
2. **world.db gets populated:**
   - `rooms` table: room data
   - `exits` table: direction → target_room_id
   - `navigation_log` table: movement history
3. **log_viz reads world.db:**
   - `WorldDB.all_rooms()` fetches rooms with exits (GROUP_CONCAT via SQL)
   - `parse_exits()` converts "north:room_id,south:room_id2" → {north: "room_id", south: "room_id2"}
   - `layout_rooms()` calculates BFS coordinates for each room
4. **map_live.erb renders:**
   - Calls `highlightPlayerPosition()`
   - Finds current room from `currentRoomId`
   - Iterates room.exits and draws arrows for non-empty target_ids

## Common Issues & Fixes

### Issue: Empty Exits Hash
**Symptom:** `exits: {}` in console

**Cause:** `parse_exits()` returning empty or GROUP_CONCAT failing

**Fix:** Check SQL:
```ruby
# In world_db.rb, line 93:
# This should create: "north:room_123,south:room_456"
"GROUP_CONCAT(e.direction || ':' || COALESCE(e.target_room_id, '')) as exits_raw"
```

Verify in database:
```bash
sqlite3 week2_capable/.boukensha/world.db \
  "SELECT GROUP_CONCAT(direction || ':' || COALESCE(target_room_id, '')) FROM exits WHERE room_id = 'room_abc123';"
```

### Issue: Arrow Coordinates Are (NaN, NaN)
**Symptom:** Arrow exists but is invisible/at wrong position

**Cause:** `positions[targetId]` is undefined

**Fix:** Target room not in `layout_rooms()` output
- Check if unvisited rooms are being placed (lines 245-257)
- Verify BFS queue is exploring all reachable rooms

### Issue: Yellow Arrowhead Missing
**Symptom:** Arrow line exists but no triangle at end

**Cause:** arrowhead-yellow marker not in SVG defs

**Fix:** Verify marker is defined (should be around line 100):
```svg
<marker id="arrowhead-yellow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
  <polygon points="0 0, 10 3, 0 6" fill="#FFD700" />
</marker>
```

## Full Debug Checklist

- [ ] Agent session has run (`events.db` has size > 0)
- [ ] World.db has rooms and exits (check with sqlite3)
- [ ] Map page loads without errors (check console for exceptions)
- [ ] Browser console shows "Map data:" with rooms and currentRoomId
- [ ] current_room_id is not null
- [ ] currentRoom.exits is not empty
- [ ] target rooms exist in positions hash
- [ ] Yellow arrowhead marker is in SVG defs
- [ ] No CSS filter is hiding the arrows (opacity: 0, display: none, etc.)

## Testing Without an Agent

If you don't want to run a full agent session, manually populate world.db:

```bash
# Use log_viz test endpoint (if available)
curl http://localhost:4567/sessions/20260804T003135Z-9c6c0214/populate-sample-world

# Or run Python script to populate
python -c "
from boukensha.world.db import WorldDB
db = WorldDB('.boukensha/world.db')

# Add rooms
db.add_room('r1', 'Market Square', 'sig1', 'A busy square', 'probable', 'test')
db.add_room('r2', 'Temple', 'sig2', 'A quiet temple', 'probable', 'test')

# Add exits
db.add_exit('r1', 'north', 'r2', 'confirmed')
db.add_exit('r2', 'south', 'r1', 'confirmed')

print('Database populated with 2 rooms and 2 exits')
"
```

Then check the map - it should show arrows between the rooms.

## Performance Notes

- **Large maps:** Layout calculation is O(V+E) BFS, should be instant for <1000 rooms
- **Positions caching:** Browser holds positions in memory, recalculated on each map load
- **SVG rendering:** All arrows drawn on page load, no dynamic updates yet

## Next Steps if Still Stuck

1. **Enable verbose logging:**
   - Edit `map_live.erb` to add more console.log calls
   - Add breakpoints in browser DevTools

2. **Check API response:**
   - Open Network tab in DevTools
   - Look for GET `/sessions/xxx` request
   - Check Response tab for @rooms, @positions JSON

3. **Compare with working example:**
   - Use the populate-sample-world endpoint
   - Check what a working setup looks like

---

**Last updated:** M9 implementation with M8 prompt caching enabled

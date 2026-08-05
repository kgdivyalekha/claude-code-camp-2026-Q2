# Test Map Arrows - Complete Guide

This guide walks through testing the map arrows with M8 caching enabled.

## Prerequisites

- log_viz running on `localhost:4567`
- `.boukensha/world.db` exists (auto-created if missing)
- Browser with DevTools support

## Step 1: Start log_viz Server

In a terminal:

```bash
cd week2_capable/log_viz
bundle install  # if needed
bundle exec rackup -p 4567
```

You should see:
```
[2026-08-05 16:00:00] INFO  WEBrick 1.8.1
[2026-08-05 16:00:00] INFO  WEBrick::HTTPServer#start: pid=12345 port=4567
```

## Step 2: Populate Test World

### Option A: Using log_viz endpoint (Recommended)

Open a new terminal and run:

```bash
# Populate test data
curl -X GET "http://localhost:4567/sessions/test_session_001/populate-sample-world"

# Should return JSON like:
# {"status":"populated","db_path":"...","rooms_saved":[...],"redirect_to":"/sessions/test_session_001/map"}
```

This creates:
- 5 rooms: Tavern, Forest, Cave, Village, Bridge
- Bidirectional exits between them
- Navigation history
- Visit count simulation

### Option B: Manual SQL (if curl fails)

```bash
cd week2_capable
sqlite3 .boukensha/world.db << 'EOF'
INSERT OR REPLACE INTO rooms (id, name, signature, confidence, discovered_by)
VALUES
  ('tavern', 'The Tavern', 'tavern_sig', 'confirmed', 'test'),
  ('forest', 'Dark Forest', 'forest_sig', 'probable', 'test'),
  ('cave', 'Entrance Cave', 'cave_sig', 'probable', 'test'),
  ('village', 'Small Village', 'village_sig', 'confirmed', 'test'),
  ('bridge', 'Stone Bridge', 'bridge_sig', 'confirmed', 'test');

INSERT OR REPLACE INTO exits (room_id, direction, target_room_id, confidence)
VALUES
  ('tavern', 'north', 'village', 'confirmed'),
  ('tavern', 'east', 'forest', 'probable'),
  ('tavern', 'south', 'bridge', 'probable'),
  ('forest', 'west', 'tavern', 'probable'),
  ('forest', 'north', 'cave', 'probable'),
  ('cave', 'south', 'forest', 'probable'),
  ('village', 'south', 'tavern', 'confirmed'),
  ('bridge', 'north', 'tavern', 'probable');

INSERT INTO navigation_log (session_id, actor, turn, from_room, direction, to_room, success)
VALUES ('test_session_001', 'scout', 1, 'tavern', 'look', 'tavern', 1);
EOF
```

## Step 3: Open Map in Browser

Navigate to:
```
http://localhost:4567/sessions/test_session_001/map
```

You should see:
- **5 colored room boxes** on the map
- **Blue arrows** connecting rooms (generic connections)
- **Red dashed circle** around the current room (Tavern)
- **Red "YOU ARE HERE" label** above current room
- **Yellow/gold arrows** FROM player location to adjacent rooms ← **THIS IS WHAT WE'RE TESTING**

## Step 4: Verify Arrows Render

### In Browser

1. **Open DevTools** (F12 or Ctrl+Shift+I)
2. **Go to Console tab**
3. **Look for these logs:**

```javascript
Map data: {
  roomsCount: 5,
  currentRoomId: "tavern",
  positionsCount: 5,
  firstRoom: {...}
}

Current room: {
  id: "tavern",
  name: "The Tavern",
  exits: {north: "village", east: "forest", south: "bridge"}
}

Drawing arrows from The Tavern exits: {north: "village", east: "forest", south: "bridge"}

Processing exit: north => village
Drawing arrow to village
Added arrow from [60, 60] to [180, 60]

Processing exit: east => forest
Drawing arrow to forest
Added arrow from [60, 60] to [240, 120]

Processing exit: south => bridge
Drawing arrow to bridge
Added arrow from [60, 60] to [120, 240]
```

### On Map

If logs show arrows being drawn:
- Look for **bright yellow/gold arrows** starting from the Tavern box
- Should point to: Village (north), Forest (east), Bridge (south)
- Yellow arrows should have **glowing effect**
- Yellow **triangle arrowheads** at the ends

## Step 5: Test M8 Prompt Caching

While the map is open, check if caching config is active:

```bash
# Verify config exists
cat week2_capable/.boukensha/settings.yaml | grep -A 3 "M8:"

# Should show:
# M8: PROMPT CACHING - 90% discount on cached input tokens
# prompt_cache: true
```

To see caching in action during an agent session:
```bash
cd week2_capable
python -m boukensha.run --config .boukensha/settings.yaml --session live_test
```

Monitor token usage in metrics:
```
http://localhost:4567/sessions/live_test/metrics
```

Look for:
- **Cache Hit Rate** > 60%
- **Cache Read Tokens** populated
- **Cost Savings** showing 90% discount on cached inputs

## Troubleshooting

### No arrows visible but console logs show "Added arrow..."

**Cause:** SVG arrowhead marker missing or CSS hiding the arrows

**Fix:**
```javascript
// In console, run:
const svg = document.getElementById('world-map-svg');
const lines = svg.querySelectorAll('line.player-arrow');
console.log('Player arrows found:', lines.length);
lines.forEach(line => console.log({
  x1: line.getAttribute('x1'),
  y1: line.getAttribute('y1'),
  x2: line.getAttribute('x2'),
  y2: line.getAttribute('y2'),
  stroke: line.getAttribute('stroke'),
  display: line.style.display
}));
```

All should show `stroke: "#FFD700"` and no `display: none`

### Console logs show empty exits: `exits: {}`

**Cause:** Exits not saved to database

**Fix:**
```bash
sqlite3 week2_capable/.boukensha/world.db "SELECT COUNT(*) FROM exits;"
# Should be > 0. If 0, populate data again with populate-sample-world endpoint
```

### `currentRoomId` is null

**Cause:** No navigation history in database

**Fix:**
```bash
sqlite3 week2_capable/.boukensha/world.db "SELECT COUNT(*) FROM navigation_log;"
# Should be > 0. If 0, the endpoint or SQL didn't run properly
```

## Expected Results

✅ **Success:** 
- 3 yellow arrows from Tavern to adjacent rooms
- Yellow glow effect visible
- Console shows all arrows being added
- Map displays correctly

❌ **Failure:**
- No yellow arrows (only blue generic connections)
- Console shows `exits: {}`  or `positions[targetId]` undefined
- currentRoomId is null

## Caching Verification

After running a test session with the config:

```bash
# Check events.db for cache events
sqlite3 week2_capable/.boukensha/events.db << 'EOF'
SELECT 
  COUNT(*) as total_calls,
  SUM(CASE WHEN cache_read_tokens > 0 THEN 1 ELSE 0 END) as cache_hits,
  SUM(COALESCE(cache_read_tokens, 0)) as cached_tokens,
  SUM(COALESCE(cache_write_tokens, 0)) as cache_writes
FROM events
WHERE phase = 'response';
EOF
```

**Expected:**
- `cache_hits` > 0 (means prompt cache was hit)
- `cached_tokens` in thousands (input that was cached and read cheaply)
- `cache_writes` present (initial cache creation)

## Clean Up

When done testing:

```bash
# Backup original
cp week2_capable/.boukensha/world.db week2_capable/.boukensha/world.db.backup

# Reset for next test
rm week2_capable/.boukensha/world.db
# world.db will be auto-created on next map load
```

---

**Test checklist:**
- [ ] log_viz server running on port 4567
- [ ] world.db populated (5 rooms, 8 exits)
- [ ] Map loads at http://localhost:4567/sessions/test_session_001/map
- [ ] Console shows map data logs
- [ ] Yellow arrows visible from current room
- [ ] Settings.yaml has `prompt_cache: true`
- [ ] Cache metrics show hits > 0 after session

**Last updated:** M8 prompt caching enabled, map arrows with M9 integration

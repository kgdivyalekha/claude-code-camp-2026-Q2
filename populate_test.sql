-- Populate test world.db with sample data for map testing
-- Run with: sqlite3 week2_capable/.boukensha/world.db < populate_test.sql

-- Insert test rooms
INSERT OR REPLACE INTO rooms (id, name, signature, description, summary, confidence, visit_count, discovered_by, first_seen, last_seen)
VALUES
  ('market', 'Market Square', 'market_sig', 'A bustling market with merchants and crowds', 'Market Square', 'probable', 3, 'test', datetime('now'), datetime('now')),
  ('temple', 'Sacred Temple', 'temple_sig', 'An ancient temple with towering columns', 'Sacred Temple', 'probable', 3, 'test', datetime('now'), datetime('now')),
  ('forest', 'Dark Forest', 'forest_sig', 'Dense trees block out the sunlight', 'Dark Forest', 'probable', 3, 'test', datetime('now'), datetime('now')),
  ('tavern', 'The Friendly Tavern', 'tavern_sig', 'A warm tavern with good ale and company', 'The Tavern', 'probable', 3, 'test', datetime('now'), datetime('now')),
  ('river', 'Crystal River', 'river_sig', 'Clear water flows peacefully northward', 'Crystal River', 'probable', 3, 'test', datetime('now'), datetime('now'));

-- Insert exits (connections between rooms)
INSERT OR REPLACE INTO exits (room_id, direction, target_room_id, confidence)
VALUES
  ('market', 'north', 'temple', 'confirmed'),
  ('temple', 'south', 'market', 'confirmed'),
  ('market', 'south', 'tavern', 'confirmed'),
  ('tavern', 'north', 'market', 'confirmed'),
  ('market', 'east', 'river', 'confirmed'),
  ('river', 'west', 'market', 'confirmed'),
  ('market', 'west', 'forest', 'confirmed'),
  ('forest', 'east', 'market', 'confirmed'),
  ('temple', 'east', NULL, 'probable'),
  ('forest', 'north', NULL, 'probable'),
  ('river', 'north', NULL, 'probable');

-- Insert navigation log to set current location
INSERT OR REPLACE INTO navigation_log (session_id, actor, turn, from_room, direction, to_room, success, at)
VALUES
  ('test_session_001', 'scout', 1, 'market', 'look', 'market', 1, datetime('now', '-5 minutes')),
  ('test_session_001', 'scout', 2, 'market', 'north', 'temple', 1, datetime('now', '-4 minutes')),
  ('test_session_001', 'scout', 3, 'temple', 'south', 'market', 1, datetime('now', '-3 minutes')),
  ('test_session_001', 'scout', 4, 'market', 'east', 'river', 1, datetime('now', '-2 minutes')),
  ('test_session_001', 'scout', 5, 'river', 'west', 'market', 1, datetime('now', '-1 minutes'));

-- Show what was created
.print ✅ Test world populated!
SELECT 'Rooms: ' || COUNT(*) FROM rooms;
SELECT 'Exits: ' || COUNT(*) FROM exits;
SELECT 'Movements: ' || COUNT(*) FROM navigation_log;
.print
.print 🗺️ Open map at:
.print http://localhost:4567/sessions/test_session_001/map

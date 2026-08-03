#!/usr/bin/env python3
import sqlite3
import json
from pathlib import Path

db_path = Path(".boukensha/events.db")
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

# Check if tools_sent is populated
cursor = conn.execute("""
SELECT
  phase,
  COUNT(*) as count,
  COUNT(CASE WHEN tools_sent IS NOT NULL THEN 1 END) as with_tools_sent
FROM events
WHERE session_id = '20260803T220918Z-7975a5d3'
GROUP BY phase
""")

print("Events by phase:")
for row in cursor:
    print(f"  {row['phase']:15} count={row['count']:4}  with_tools_sent={row['with_tools_sent']:4}")

# Check a sample prompt event to see tool_count
cursor = conn.execute("""
SELECT details FROM events
WHERE session_id = '20260803T220918Z-7975a5d3'
  AND phase = 'prompt'
LIMIT 1
""")
row = cursor.fetchone()
if row:
    event = json.loads(row['details'])
    print(f"\nSample prompt event tool_count: {event.get('tool_count')}")

# Check a sample response event
cursor = conn.execute("""
SELECT tools_sent, details FROM events
WHERE session_id = '20260803T220918Z-7975a5d3'
  AND phase = 'response'
LIMIT 1
""")
row = cursor.fetchone()
if row:
    event = json.loads(row['details'])
    print(f"Sample response event tools_sent (column): {row['tools_sent']}")
    print(f"Sample response event tools_sent (json):   {event.get('tools_sent')}")

conn.close()

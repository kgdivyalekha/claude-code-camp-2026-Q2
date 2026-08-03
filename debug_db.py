#!/usr/bin/env python3
import sqlite3
import json
from pathlib import Path

db_path = Path('.boukensha/events.db')
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

print("PROMPT EVENTS:")
cursor = conn.execute("""
SELECT session_id, turn, iteration, json_extract(details, '$.tool_count') as tool_count
FROM events
WHERE session_id = '20260803T220918Z-7975a5d3' AND phase = 'prompt'
LIMIT 5
""")
for row in cursor:
    print(f"  turn={row['turn']} iter={row['iteration']} tool_count={row['tool_count']}")

print("\nRESPONSE EVENTS:")
cursor = conn.execute("""
SELECT session_id, turn, iteration, tools_sent, json_extract(details, '$.tool_count') as tool_count_in_json
FROM events
WHERE session_id = '20260803T220918Z-7975a5d3' AND phase = 'response'
LIMIT 5
""")
for row in cursor:
    print(f"  turn={row['turn']} iter={row['iteration']} tools_sent={row['tools_sent']} tool_count_in_json={row['tool_count_in_json']}")

print("\nSUMMARY:")
cursor = conn.execute("""
SELECT COUNT(*) as total_response_events,
       COUNT(CASE WHEN tools_sent IS NULL THEN 1 END) as null_tools_sent
FROM events
WHERE session_id = '20260803T220918Z-7975a5d3' AND phase = 'response'
""")
row = cursor.fetchone()
print(f"  Total response events: {row['total_response_events']}")
print(f"  Response events with NULL tools_sent: {row['null_tools_sent']}")

conn.close()

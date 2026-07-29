#!/usr/bin/env python3
"""Debug script to check what's in events.db"""

import sqlite3
import json

db_path = ".boukensha/events.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check total events
cursor.execute("SELECT COUNT(*) FROM events")
total = cursor.fetchone()[0]
print(f"Total events: {total}")

# Check response events
cursor.execute("SELECT COUNT(*) FROM events WHERE phase='response'")
response_count = cursor.fetchone()[0]
print(f"Response events: {response_count}")

# Check response events with cost_usd
cursor.execute("SELECT COUNT(*) FROM events WHERE phase='response' AND cost_usd IS NOT NULL")
response_with_cost = cursor.fetchone()[0]
print(f"Response events with cost_usd: {response_with_cost}")

# Check actual cost values
cursor.execute("SELECT SUM(cost_usd) FROM events WHERE phase='response' AND session_id='baseline-fixture-001'")
total_cost = cursor.fetchone()[0]
print(f"Total cost for baseline-fixture-001: {total_cost}")

# Check a sample response event
cursor.execute("SELECT * FROM events WHERE phase='response' AND session_id='baseline-fixture-001' LIMIT 1")
cols = [description[0] for description in cursor.description]
row = cursor.fetchone()
if row:
    print(f"\nSample response event:")
    for col, val in zip(cols, row):
        if col in ['cost_usd', 'input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_write_tokens']:
            print(f"  {col}: {val}")

conn.close()

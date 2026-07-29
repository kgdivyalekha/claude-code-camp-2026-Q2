#!/usr/bin/env python3
"""Debug script to check a specific session in the database"""

import sqlite3
import sys
from pathlib import Path

session_id = sys.argv[1] if len(sys.argv) > 1 else "20260729T192414Z-d62d1112"
db_path = ".boukensha/events.db"

if not Path(db_path).exists():
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"Debugging session: {session_id}\n")
print("=" * 80)

# Check total events for this session
cursor.execute("SELECT COUNT(*) FROM events WHERE session_id = ?", (session_id,))
total = cursor.fetchone()[0]
print(f"Total events in database: {total}")

# Check response events
cursor.execute("SELECT COUNT(*) FROM events WHERE session_id = ? AND phase = 'response'", (session_id,))
response_count = cursor.fetchone()[0]
print(f"Response events: {response_count}")

if response_count == 0:
    print("\n❌ NO RESPONSE EVENTS FOUND!")
    print("The session has no response events, so there's no cost data.")

    # Check what events DO exist
    cursor.execute("""
        SELECT DISTINCT phase FROM events WHERE session_id = ? ORDER BY phase
    """, (session_id,))
    phases = [row[0] for row in cursor.fetchall()]
    print(f"\nPhases found: {phases}")

    conn.close()
    exit(1)

# Check cost values
cursor.execute("""
    SELECT
        COUNT(*) as count,
        COALESCE(SUM(cost_usd), 0) as total_cost,
        COALESCE(AVG(cost_usd), 0) as avg_cost
    FROM events
    WHERE session_id = ? AND phase = 'response'
""", (session_id,))

count, total_cost, avg_cost = cursor.fetchone()
print(f"Response events with cost data:")
print(f"  Count: {count}")
print(f"  Total cost: ${total_cost:.4f}")
print(f"  Avg cost: ${avg_cost:.4f}")

if total_cost == 0:
    print("\n❌ ZERO COST DETECTED!")
    print("Response events exist but have no cost data.")

    # Check what columns have data
    cursor.execute("""
        SELECT
            input_tokens,
            output_tokens,
            cost_usd,
            tools_sent,
            model,
            provider,
            turn,
            iteration
        FROM events
        WHERE session_id = ? AND phase = 'response'
        LIMIT 1
    """, (session_id,))

    row = cursor.fetchone()
    if row:
        print("\nSample response event:")
        cols = ["input_tokens", "output_tokens", "cost_usd", "tools_sent", "model", "provider", "turn", "iteration"]
        for col, val in zip(cols, row):
            print(f"  {col}: {val}")

# Check all turns and costs
print("\nPer-turn breakdown:")
cursor.execute("""
    SELECT
        turn,
        COUNT(*) as responses,
        COALESCE(SUM(input_tokens), 0) as input_tokens,
        COALESCE(SUM(output_tokens), 0) as output_tokens,
        COALESCE(SUM(cost_usd), 0) as cost_usd
    FROM events
    WHERE session_id = ? AND phase = 'response'
    GROUP BY turn
    ORDER BY turn
""", (session_id,))

turns = cursor.fetchall()
for turn, responses, input_tok, output_tok, cost in turns:
    print(f"  Turn {turn}: {responses} responses, {input_tok} in, {output_tok} out, ${cost:.4f}")

conn.close()
print("\n" + "=" * 80)

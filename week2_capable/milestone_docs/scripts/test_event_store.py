#!/usr/bin/env python3
"""Test script to verify EventStore is working correctly"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from boukensha.logger import Logger
from boukensha.observability.event_store import EventStore

print("Testing EventStore attachment...\n")

# Create a test logger
print("1. Creating logger...")
logger = Logger(session_id="test-event-store-001")
print(f"   Logger created: {logger.session_id}")
print(f"   Log file: {logger.path}\n")

# Create EventStore and attach
print("2. Creating and attaching EventStore...")
try:
    store = EventStore()
    print(f"   EventStore created at: .boukensha/events.db")
    store.attach(logger)
    print(f"   EventStore attached to logger\n")
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# Simulate some events
print("3. Simulating events...")
logger.turn(1)
logger.tool_call("look", {})
logger.tool_result("look", "You are in a test room")
logger.response(
    "I see a test room",
    usage={
        "input_tokens": 500,
        "output_tokens": 100,
    },
    backend=type('Backend', (), {'model': 'test-model'})()
)
print("   Events logged\n")

logger.close()
store.close()

# Check if data was written to database
print("4. Checking database...")
import sqlite3
conn = sqlite3.connect(".boukensha/events.db")
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM events WHERE session_id = ?", ("test-event-store-001",))
count = cursor.fetchone()[0]
print(f"   Events in database: {count}")

cursor.execute("SELECT COUNT(*) FROM events WHERE session_id = ? AND phase = 'response'", ("test-event-store-001",))
response_count = cursor.fetchone()[0]
print(f"   Response events: {response_count}")

if response_count > 0:
    cursor.execute("""
        SELECT input_tokens, output_tokens, cost_usd FROM events
        WHERE session_id = ? AND phase = 'response'
    """, ("test-event-store-001",))
    row = cursor.fetchone()
    print(f"   Token data: input={row[0]}, output={row[1]}, cost={row[2]}")
    print("\n✅ SUCCESS: EventStore is working!")
else:
    print("\n❌ FAILED: No response events found in database!")

conn.close()
